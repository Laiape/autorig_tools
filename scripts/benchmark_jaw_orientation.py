"""Validate an in-place jaw upgrade and time animated head geometry in Parallel.

Run through scripts/run_maya_test.py in a disposable mayapy process. The scene
is read only; all keys, upgrades and undo operations exist only in the worker.
Timings include currentTime plus CPU geometry queries, without a viewport/GPU.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'maya_tools/scripts')]
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'


def run(scene, output, steps=16):
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya.api import OpenMaya as om
    import numpy as np
    from maya_tools.scripts.tools import jaw_graph_optimizer

    output.mkdir(parents=True, exist_ok=False)
    report = {'success': False, 'scene': str(scene),
              'scene_sha256': hashlib.sha256(scene.read_bytes()).hexdigest(),
              'measurement': 'Parallel currentTime + world-space CPU mesh queries; no viewport/GPU timing.',
              'samples': [], 'geometry_tolerance_cm': 2e-5,
              'matrix_tolerance': 2e-5, 'rotation_tolerance': 1e-5}
    try:
        cmds.file(str(scene), open=True, force=True, prompt=False, executeScriptNodes=False)
        cmds.evaluationManager(mode='off')
        for evaluator in ('cache', 'gpuOverride'):
            if evaluator in (cmds.evaluator(query=True) or []):
                cmds.evaluator(name=evaluator, enable=False)
        meshes = []
        for mesh in ('cabeza_low', 'EdwardWrinkles_Face', 'cabeza_high', 'cuerpo_base'):
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) if cmds.objExists(mesh) else []
            if shapes and cmds.nodeType(shapes[0]) == 'mesh':
                meshes.append((mesh, om.MFnMesh(om.MSelectionList().add(shapes[0]).getDagPath(0))))
        assert any(n == 'cabeza_low' for n, _ in meshes), meshes
        assert any(n in ('EdwardWrinkles_Face', 'cabeza_high') for n, _ in meshes), meshes
        report['meshes'] = [n for n, _ in meshes]
        report['maya'] = cmds.about(version=True)
        nodes = sorted(cmds.listRelatives('C_lipsSkinning_GRP', allDescendents=True, type='joint'))
        matrix_plugs = [om.MSelectionList().add(n + '.worldMatrix[0]').getPlug(0) for n in nodes]

        def read():
            return {name: np.array(fn.getPoints(om.MSpace.kWorld))[:, :3] for name, fn in meshes}

        def matrices():
            return np.array([list(om.MFnMatrixData(p.asMObject()).matrix()) for p in matrix_plugs])

        channels = ('C_jaw_CTL.rx', 'C_jaw_CTL.stickyLips', 'L_lipCorner_CTL.tx',
                    'R_lipCorner_CTL.tx', 'L_lipCorner_CTL.ty',
                    'L_upperLip02_CTL.tx', 'R_lowerLip02_CTL.tx',
                    'C_upperLip_CTL.Roll', 'C_lowerLip_CTL.Roll')
        defaults = {p: cmds.getAttr(p) for p in channels}
        frames = {}
        for scenario in ('jaw', 'corner', 'fine', 'mixed'):
            frames[scenario] = []
            for sample in range(steps):
                step = round(sample * 15 / (steps - 1))
                values = dict(defaults)
                if scenario in ('jaw', 'mixed'):
                    values['C_jaw_CTL.rx'] = step * 2.
                if scenario in ('corner', 'mixed'):
                    values['L_lipCorner_CTL.tx'] = (step % 9 - 4) * .2
                    values['R_lipCorner_CTL.tx'] = (step % 7 - 3) * .2
                    values['L_lipCorner_CTL.ty'] = (step % 9 - 4) * .2
                if scenario in ('fine', 'mixed'):
                    values['L_upperLip02_CTL.tx'] = (step - 8) * .03
                    values['R_lowerLip02_CTL.tx'] = (8 - step) * .03
                if scenario == 'mixed':
                    values['C_jaw_CTL.stickyLips'] = step % 7 / 6.
                    values['C_upperLip_CTL.Roll'] = step - 8
                    values['C_lowerLip_CTL.Roll'] = 8 - step
                frame = 1000 + len(frames[scenario]) + steps * (len(frames) - 1)
                frames[scenario].append(frame)
                for plug, value in values.items():
                    assert cmds.getAttr(plug, settable=True), plug
                    cmds.setKeyframe(plug, time=frame, value=value)
        cmds.keyTangent(list(channels), time=(1000, 1063), inTangentType='linear', outTangentType='linear')
        report['animated_channels'] = list(channels)
        report['frames'] = frames
        # Keep the upgrade as the latest undo item while time/EM changes run.
        cmds.undoInfo(stateWithoutFlush=False)
        optimized = False

        def switch(enabled):
            nonlocal optimized
            if enabled == optimized:
                return
            if enabled:
                report['upgrade'] = jaw_graph_optimizer.optimize()
            else:
                cmds.undoInfo(stateWithoutFlush=True)
                cmds.undo()
                cmds.undoInfo(stateWithoutFlush=False)
            optimized = enabled
            cmds.dgdirty(allPlugs=True)

        geometry_errors, matrix_errors, rotation_errors = {}, {}, {}
        baseline = {}
        for mode in ('off', 'parallel'):
            cmds.evaluationManager(mode=mode)
            for enabled in (False, True):
                switch(enabled)
                for scenario, row in frames.items():
                    for frame in row:
                        cmds.currentTime(frame, update=True)
                        points, matrix = read(), matrices()
                        assert all(np.isfinite(v).all() for v in points.values())
                        key = (scenario, frame)
                        if mode == 'off' and not enabled:
                            baseline[key] = (points, matrix)
                        else:
                            reference, ref_matrix = baseline[key]
                            label = mode + ('_optimized' if enabled else '_original')
                            geometry_errors[label] = max(geometry_errors.get(label, 0.),
                                max(float(np.abs(points[n] - reference[n]).max()) for n in points))
                            matrix_errors[label] = max(matrix_errors.get(label, 0.), float(np.abs(matrix-ref_matrix).max()))
                            rotation_errors[label] = max(rotation_errors.get(label, 0.),
                                float(np.abs(matrix[:, :12] - ref_matrix[:, :12]).max()))
        report['geometry_errors'] = geometry_errors
        report['matrix_errors'] = matrix_errors
        report['rotation_errors'] = rotation_errors
        # Native mesh positions at head height (~190 cm) are quantized to
        # float32. Permit one 1.5259e-5 cm ULP while checking rotation separately.
        assert max(geometry_errors.values()) < report['geometry_tolerance_cm'], geometry_errors
        assert max(matrix_errors.values()) < report['matrix_tolerance'], matrix_errors
        assert max(rotation_errors.values()) < report['rotation_tolerance'], rotation_errors
        assert any(float(np.max(np.abs(baseline[('jaw', 1000)][0][name] -
                                       baseline[('jaw', 1000 + steps - 1)][0][name]))) > 1e-5
                   for name, _ in meshes), 'No temporal deformation'
        print('PASS full-scene geometry and DG/Parallel compatibility', flush=True)
        cmds.evaluationManager(mode='parallel')
        for enabled in (False, True, True, False):
            switch(enabled)
            for iteration in range(4):
                timings = {}
                for scenario, row in frames.items():
                    elapsed = []
                    for frame in row:
                        started = time.perf_counter()
                        cmds.currentTime(frame, update=True)
                        read()
                        elapsed.append((time.perf_counter() - started) * 1000)
                    if iteration:
                        timings[scenario] = elapsed[2:] if len(elapsed) > 4 else elapsed
                if iteration:
                    report['samples'].append({'optimized': enabled, 'ms': timings})
            print('TIMED', 'optimized' if enabled else 'original', flush=True)
        for enabled in (False, True):
            kind = 'after' if enabled else 'before'
            report[kind] = {scenario: statistics.median(v for sample in report['samples']
                if sample['optimized'] == enabled for v in sample['ms'][scenario]) for scenario in frames}
        report['success'] = True
    finally:
        (output / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('samples', 'upgrade')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=16, choices=range(2, 17))
    args = parser.parse_args()
    run(args.scene.resolve(), args.output.resolve(), args.steps)
