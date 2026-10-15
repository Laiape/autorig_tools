"""Compare native jaw graphs against a Git revision in a disposable mayapy worker.

Example: mayapy scripts/run_maya_test.py scripts/benchmark_jaw_graph.py
         --baseline-ref a6f81f2 --output <new-directory>
The artist scene and checkout are never replaced. Python builds the graph;
all measured deformation uses Maya nodes. No viewport or mesh FPS is claimed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = 'maya_tools/scripts/biped/autorig/jaw_module_nurbs.py'


def pose_bank():
    cases = [('neutral', {})]
    for angle in (5, 10, 20, 30, 45):
        cases.append(('jaw_' + str(angle), {'C_jaw_CTL.rx': angle}))
    for part in ('upper', 'lower'):
        ctl = 'C_' + part + 'Lip_CTL'
        for axis in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'Roll'):
            values = (.5, 1.5) if axis.startswith('s') else (-20, 20) if axis.startswith('r') or axis == 'Roll' else (-2, 2)
            for value in values:
                cases.append((part + axis + str(value), {ctl + '.' + axis: value, 'C_jaw_CTL.rx': 20}))
    for side in ('L', 'R'):
        for axis in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
            for value in (-1, 1):
                cases.append((side + axis + str(value), {
                    side + '_lipCorner_CTL.' + axis: value * (25 if axis.startswith('r') else 1),
                    'C_jaw_CTL.rx': 20}))
        for part in ('upper', 'lower'):
            for index in range(4):
                for value in (-.5, .5):
                    cases.append((f'{side}_{part}_fine{index}_{value}', {
                        f'{side}_{part}Lip{index:02d}_CTL.tx': value, 'C_jaw_CTL.rx': 20}))
    for angle in (0, 20, 30):
        for amount in (0, .25, .5, 1):
            for sides in (('L',), ('R',), ('L', 'R')):
                case = {'C_jaw_CTL.rx': angle}
                case.update({s + '_lipCorner_CTL.autoNarrow': amount for s in sides})
                case.update({s + '_lipCorner_CTL.tx': 1. for s in sides})
                cases.append((f'narrow_{angle}_{amount}_{"".join(sides)}', case))
        for order in range(6):
            for sticky in (0, .5, 1):
                cases.append((f'combined_{angle}_{order}_{sticky}', {
                    'C_jaw_CTL.rx': angle, 'C_jaw_CTL.stickyLips': sticky,
                    'L_lipCorner_CTL.rotateOrder': order, 'R_lipCorner_CTL.rotateOrder': order,
                    'L_lipCorner_CTL.rx': 17, 'L_lipCorner_CTL.ry': 13, 'L_lipCorner_CTL.rz': 22,
                    'R_lipCorner_CTL.rx': -11, 'R_lipCorner_CTL.ry': 8, 'R_lipCorner_CTL.rz': -19,
                    'L_lipCorner_CTL.autoNarrow': .5, 'R_lipCorner_CTL.autoNarrow': .5,
                    'L_lipCorner_CTL.tx': .7, 'R_lipCorner_CTL.tx': .7,
                    'C_upperLip_CTL.Roll': 12, 'C_lowerLip_CTL.Roll': -15}))
    for side in ('L', 'R'):
        for gain in (0, .5, 1):
            for depth in (.05, .2, .6):
                cases.append((f'wide_{side}_{gain}_{depth}', {
                    'L_lipCorner_CTL.autoNarrow': 1, 'R_lipCorner_CTL.autoNarrow': 1,
                    'L_lipCorner_CTL.tx': -1, 'R_lipCorner_CTL.tx': -1,
                    side + '_lipCorner_CTL.autoWide': gain, side + '_lipCorner_CTL.autoWideDepth': depth}))
    for angle in (0, 10, 20, 30):
        cases.append(('rounded_U_' + str(angle), {
            'C_jaw_CTL.rx': angle, 'L_lipCorner_CTL.tx': 5.2, 'R_lipCorner_CTL.tx': 5.2,
            'L_lipCorner_CTL.ty': 2, 'R_lipCorner_CTL.ty': 2}))
    import random
    rng = random.Random(134)
    for index in range(64):
        case = {'C_jaw_CTL.rx': rng.uniform(0, 30), 'C_jaw_CTL.stickyLips': rng.random(),
                'C_jaw_CTL.mouthHeight': rng.random(), 'C_jaw_CTL.stickyFalloff': rng.uniform(.001, 1)}
        for side in ('L', 'R'):
            for axis in 'xyz':
                case[side + '_lipCorner_CTL.t' + axis] = rng.uniform(-.8, .8)
                case[side + '_lipCorner_CTL.r' + axis] = rng.uniform(-25, 25)
            case[side + '_lipCorner_CTL.autoNarrow'] = rng.random()
            case[side + '_lipCorner_CTL.autoWide'] = rng.random()
        for part in ('upper', 'lower'):
            case['C_' + part + 'Lip_CTL.ty'] = rng.uniform(-1, 1)
            case['C_' + part + 'Lip_CTL.Roll'] = rng.uniform(-20, 20)
            case['L_' + part + 'Lip02_CTL.tx'] = rng.uniform(-.3, .3)
        for axis in 'xyz':
            case['C_mainMouth_CTL.t' + axis] = rng.uniform(-1, 1)
            case['C_mainMouth_CTL.r' + axis] = rng.uniform(-20, 20)
        cases.append(('random_' + str(index), case))
    return cases


def run(args):
    os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
    sys.path.insert(0, str(ROOT / 'maya_tools/scripts/tools/tests'))
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya.api import OpenMaya as om
    import numpy as np
    from fixtures.jaw_scene import build, SOURCE

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    old_text = subprocess.check_output(['git', 'show', args.baseline_ref + ':' + SOURCE_PATH], cwd=ROOT)
    cases = pose_bank()
    report = dict(success=False, baseline_ref=args.baseline_ref,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  cases=len(cases), measurement='Native jaw fixture, DG, all joint/control-group world matrices via MPlug; excludes mesh and viewport cost. Paired ABBA order, one warm-up sweep per build.',
                  maya_version=cmds.about(version=True),
                  created=datetime.now(timezone.utc).isoformat(), samples=[])

    def readers():
        names = sorted(set((cmds.ls(type='joint') or []) + (cmds.ls('*Lip*_GRP', type='transform') or [])))
        plugs = [om.MSelectionList().add(n + '.worldMatrix[0]').getPlug(0) for n in names]
        return names, lambda: np.array([list(om.MFnMatrixData(p.asMObject()).matrix()) for p in plugs])

    def capture():
        names, read = readers()
        defaults = {p: cmds.getAttr(p) for _, case in cases for p in case}
        last, data = {}, []
        for name, values in cases:
            for p in last:
                cmds.setAttr(p, defaults[p])
            for p, value in values.items():
                cmds.setAttr(p, value)
            matrix = read()
            assert np.isfinite(matrix).all(), name
            data.append(matrix)
            last = values
        pairs = cmds.ls(showType=True)
        kinds = Counter(pairs[1::2])
        connections = cmds.listConnections(cmds.ls(), s=True, d=False, c=True, p=True) or []
        return names, data, dict(nodes=len(cmds.ls()), connections=len(connections)//2,
                                node_types=dict(kinds), plugins=sorted(cmds.pluginInfo(q=True, listPlugins=True) or []))

    try:
        with tempfile.TemporaryDirectory(prefix='jaw_baseline_') as folder:
            baseline = Path(folder) / 'jaw.py'
            baseline.write_bytes(old_text)
            build(baseline)
            old_names, old_data, report['before'] = capture()
            build(SOURCE)
            new_names, new_data, report['after'] = capture()
            assert old_names == new_names
            error = np.asarray([np.abs(a-b) for a, b in zip(old_data, new_data)])
            pose, node, component = np.unravel_index(np.argmax(error), error.shape)
            report['maximum_matrix_error'] = float(error.max())
            report['worst'] = dict(pose=cases[pose][0], node=new_names[node], component=int(component))
            report['matrices_per_pose'] = len(new_names)
            assert error.max() < 1e-5, report['worst']
            assert not set(report['after']['plugins']) - set(report['before']['plugins'])
            assert report['after']['nodes'] < report['before']['nodes'] * .9
            print('PASS compatibility: ' + str(len(cases)) + ' poses, max matrix error ' + str(error.max()), flush=True)

            # Repeat fresh builds in ABBA order to reduce order/cache bias.
            for kind in ('before', 'after', 'after', 'before') * args.rounds:
                started = time.perf_counter()
                build(baseline if kind == 'before' else SOURCE)
                build_seconds = time.perf_counter() - started
                _, read = readers()
                timings = {}
                for scenario in ('jaw', 'corner', 'fine', 'mixed'):
                    for p in ('C_jaw_CTL.rx', 'C_jaw_CTL.stickyLips', 'L_lipCorner_CTL.autoNarrow',
                              'R_lipCorner_CTL.autoNarrow', 'L_lipCorner_CTL.ty', 'R_lipCorner_CTL.ty',
                              'L_upperLip02_CTL.tx', 'R_lowerLip02_CTL.tx'):
                        cmds.setAttr(p, 0)
                    for sweep in range(2):
                        started = time.perf_counter()
                        for step in range(24):
                            if scenario in ('jaw', 'mixed'):
                                cmds.setAttr('C_jaw_CTL.rx', step % 31)
                            if scenario in ('corner', 'mixed'):
                                for side in ('L', 'R'):
                                    cmds.setAttr(side + '_lipCorner_CTL.autoNarrow', step % 11 / 10.)
                                cmds.setAttr('L_lipCorner_CTL.ty', (step % 9 - 4) * .2)
                            if scenario == 'fine':
                                cmds.setAttr('L_upperLip02_CTL.tx', (step - 12) * .03)
                                cmds.setAttr('R_lowerLip02_CTL.tx', (12 - step) * .03)
                            if scenario == 'mixed':
                                cmds.setAttr('C_jaw_CTL.stickyLips', step % 7 / 6.)
                            read()
                        timings[scenario] = (time.perf_counter()-started) / 24 * 1000
                report['samples'].append(dict(kind=kind, build_seconds=build_seconds,
                                              ms_per_pose=timings['mixed'], controls_ms=timings))
            for kind in ('before', 'after'):
                samples = [s for s in report['samples'] if s['kind'] == kind]
                report[kind]['median_ms_per_pose'] = statistics.median(s['ms_per_pose'] for s in samples)
                report[kind]['median_build_seconds'] = statistics.median(s['build_seconds'] for s in samples)
                report[kind]['median_controls_ms'] = {scenario: statistics.median(s['controls_ms'][scenario] for s in samples)
                                                     for scenario in ('jaw', 'corner', 'fine', 'mixed')}
            report['success'] = True
            print(json.dumps({k: v for k, v in report.items() if k not in ('before', 'after', 'samples')}), flush=True)
            print('BEFORE', report['before']['nodes'], report['before']['connections'], report['before']['median_ms_per_pose'], flush=True)
            print('AFTER', report['after']['nodes'], report['after']['connections'], report['after']['median_ms_per_pose'], flush=True)
    finally:
        (output / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        maya.standalone.uninitialize()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=3)
    argv = sys.argv[1:]
    if argv and Path(argv[0]).resolve() == Path(__file__).resolve():
        argv = argv[1:]
    run(parser.parse_args(argv))
