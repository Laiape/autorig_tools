"""Owned Edward solver A/B builds, quality captures and viewport timings."""
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import numpy as np
from maya import cmds, mel
from maya.api import OpenMaya as om

ROOT = Path(r'C:/proyectos/auto-rig')
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001'
SETTINGS = json.loads((FOLDER / 'launch.json').read_text())
assert os.getpid() == SETTINGS['pid']
RUNTIME = Path(SETTINGS['runtime'])


def write(name, data):
    (FOLDER / name).write_text(json.dumps(data, indent=2, default=str))


def progress(phase, **data):
    write('progress.json', dict(phase=phase, **data))


def cpu(mode='parallel'):
    cmds.evaluator(name='cache', enable=False); cmds.evaluator(name='deformer', enable=False)
    cmds.evaluationManager(mode=mode)


def build(label):
    from maya_tools.scripts.framework import context
    from maya_tools.scripts.utils import create_rig, rig_manager
    assert Path(create_rig.__file__).is_relative_to(RUNTIME), create_rig.__file__
    cmds.file(new=True, force=True)
    context.service().set_asset('Edward'); cmds.optionVar(stringValue=('currentAssetRigName', 'Edward'))
    manifest = json.loads((FOLDER / 'frozen/manifest.json').read_text())
    build_path = RUNTIME / manifest['inputs']['build']
    original = (FOLDER / 'frozen' / manifest['inputs']['build']).read_text()
    settings = json.loads(original); settings['solver_mode'] = int(label == 'custom')
    build_path.write_text(json.dumps(settings, indent=4))
    progress('build', variant=label)
    start = time.perf_counter()
    try:
        report = create_rig.AutoRig().build()
    finally:
        build_path.write_text(original)
    elapsed = time.perf_counter() - start
    cpu('off'); cmds.select(clear=True)
    native = FOLDER / ('Edward_' + label + '.ma')
    assert not native.exists()
    cmds.file(rename=str(native)); cmds.file(save=True, type='mayaAscii', force=False, options='v=0;')
    controls = {}
    for node in cmds.ls('*_CTL', type='transform'):
        attrs = {}
        for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
            plug = node + '.' + attr
            if cmds.getAttr(plug, type=True) in ('double', 'doubleLinear', 'doubleAngle', 'float', 'long', 'short', 'enum', 'bool'):
                attrs[attr] = {'value': cmds.getAttr(plug), 'settable': cmds.getAttr(plug, settable=True),
                               'type': cmds.getAttr(plug, type=True)}
        controls[node] = attrs
    info = {'variant': label, 'scene': str(native), 'scene_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
            'build_seconds': elapsed, 'build_report': report, 'nodes': len(cmds.ls()),
            'joints': cmds.ls(type='joint'), 'skin_nodes': cmds.ls(type='skinCluster'),
            'ik_handles': cmds.ls(type='ikHandle'), 'controls': controls,
            'runtime': create_rig.__file__, 'cycles': cmds.cycleCheck(all=True, list=True) or []}
    write(label + '_build.json', info)
    return {k: v for k, v in info.items() if k not in ('controls', 'joints', 'skin_nodes', 'build_report')}


def open_variant(label):
    cpu('off'); cmds.file(str(FOLDER / ('Edward_' + label + '.ma')), open=True, force=True,
                          prompt=False, executeScriptNodes=False)
    cmds.undoInfo(stateWithoutFlush=False); cmds.autoKeyframe(state=False)
    cpu()


def cases():
    fk = {s + '_' + limb + 'Settings_CTL.Ik_Fk': 1 for s in ('L', 'R') for limb in ('arm', 'leg')}
    ik = {k: 0 for k in fk}
    out = [('fk_neutral', dict(fk)), ('ik_neutral', dict(ik))]
    for side, sign in (('L', 1), ('R', -1)):
        out += [
            (side + '_fk_bend', dict(fk, **{side + '_shoulderFk_CTL.rotateZ': 65,
              side + '_elbowFk_CTL.rotateY': 80, side + '_hipFk_CTL.rotateZ': 50, side + '_kneeFk_CTL.rotateZ': 80})),
            (side + '_fk_twist', dict(fk, **{side + '_shoulderFk_CTL.rotateX': 55,
              side + '_wristFk_CTL.rotateX': 45, side + '_hipFk_CTL.rotateX': 35, side + '_ankleFk_CTL.rotateY': 25})),
            (side + '_ik_bend', dict(ik, **{side + '_armIkWrist_CTL.translateX': -sign * 12,
              side + '_armIkWrist_CTL.translateY': 15, side + '_legIk_CTL.translateY': 12,
              side + '_legIk_CTL.translateZ': 10})),
            (side + '_pv', dict(ik, **{side + '_armPv_CTL.translateZ': 18, side + '_legPv_CTL.translateX': sign * 15})),
            (side + '_reach', dict(ik, **{side + '_armIkWrist_CTL.translateX': sign * 35,
              side + '_legIk_CTL.translateY': -25})),
            (side + '_stretch', dict(ik, **{side + '_armIkWrist_CTL.translateX': sign * 35,
              side + '_armIkWrist_CTL.Stretch': 1, side + '_legIk_CTL.translateY': -25, side + '_legIk_CTL.Stretch': 1})),
            (side + '_soft', dict(ik, **{side + '_armIkWrist_CTL.translateX': sign * 12,
              side + '_armIkWrist_CTL.Soft': .5, side + '_legIk_CTL.translateY': -8, side + '_legIk_CTL.Soft': .5})),
            (side + '_pin', dict(ik, **{side + '_armPv_CTL.Pin': .7, side + '_legPv_CTL.Pin': .7})),
            (side + '_roll30', dict(ik, **{side + '_legIk_CTL.Roll': 30})),
            (side + '_roll70', dict(ik, **{side + '_legIk_CTL.Roll': 70})),
            (side + '_roll_negative', dict(ik, **{side + '_legIk_CTL.Roll': -25})),
            (side + '_foot_twist', dict(ik, **{side + '_legIk_CTL.Ball_Twist': 25, side + '_legIk_CTL.Toe_Twist': 20})),
            (side + '_blend', {**fk, side + '_armSettings_CTL.Ik_Fk': .5, side + '_legSettings_CTL.Ik_Fk': .5,
                 side + '_shoulderFk_CTL.rotateZ': 45, side + '_armIkWrist_CTL.translateY': 20,
                 side + '_hipFk_CTL.rotateZ': 40, side + '_legIk_CTL.translateZ': 15})]
    out += [('ik_combined', dict(ik, **{'L_armIkWrist_CTL.translateY': 25, 'R_armIkWrist_CTL.translateZ': 20,
                 'L_legIk_CTL.translateY': 18, 'R_legIk_CTL.translateZ': -15, 'C_localChest_CTL.rotateY': 25})),
            ('ik_global', dict(ik, **{'C_masterwalk_CTL.globalScale': 1.2, 'C_masterwalk_CTL.rotateY': 25,
                 'C_masterwalk_CTL.translateX': 15, 'L_armIkWrist_CTL.translateY': 20, 'L_legIk_CTL.Roll': 35}))]
    return [(name, {p.replace('_legIk_CTL', '_ankleIk_CTL'): value for p, value in values.items()})
            for name, values in out]


def capture_quality(label):
    open_variant(label)
    info = json.loads((FOLDER / (label + '_build.json')).read_text())
    base = {node + '.' + attr: data['value'] for node, attrs in info['controls'].items()
            for attr, data in attrs.items() if data['settable']}
    base = {k: v for k, v in base.items() if cmds.objExists(k) and cmds.getAttr(k, settable=True)}
    shapes = cmds.ls('Edward', dag=True, type='mesh', noIntermediate=True, long=True) or []
    shapes = sorted(s for s in shapes if '|geo_GRP|' in s and not any(t in s for t in ('Orig', 'poseTarget', 'Sculpt')))
    joints = sorted(n for n in cmds.ls(type='joint') if 'Skinning' in n and ('arm' in n.lower() or 'leg' in n.lower() or 'wrist' in n.lower()))
    data = {}; metadata = {'variant': label, 'meshes': {}, 'joints': joints, 'cases': [], 'missing': []}
    bindings = {}
    for index, shape in enumerate(shapes):
        selection = om.MSelectionList(); selection.add(shape); path = selection.getDagPath(0); fn = om.MFnMesh(path)
        counts, verts = fn.getVertices()
        bindings[str(index)] = (path, fn)
        metadata['meshes'][str(index)] = {'shape': shape, 'vertices': fn.numVertices,
            'topology_sha256': hashlib.sha256(np.asarray(counts).tobytes() + np.asarray(verts).tobytes()).hexdigest()}
    for direction, sequence in (('forward', cases()), ('reverse', list(reversed(cases())))):
        for case_index, (name, values) in enumerate(sequence):
            progress('quality', variant=label, direction=direction, pose=name)
            for plug, value in base.items():
                cmds.setAttr(plug, value)
            missing = [p for p in values if p not in base]
            metadata['missing'] += [{'case': name, 'plug': p} for p in missing]
            for plug, value in values.items():
                if plug in base:
                    cmds.setAttr(plug, value)
            case_id = direction + '_' + name
            metadata['cases'].append({'id': case_id, 'name': name, 'direction': direction, 'channels': values})
            for index, (path, fn) in bindings.items():
                cmds.dgeval(path.fullPathName() + '.outMesh')
                data[case_id + '_p_' + index] = np.asarray(fn.getPoints(om.MSpace.kWorld))[:, :3].copy()
                data[case_id + '_n_' + index] = np.asarray(fn.getFaceVertexNormals(om.MSpace.kWorld))[:, :3].copy()
            data[case_id + '_j'] = np.asarray([cmds.xform(j, q=True, ws=True, matrix=True) for j in joints])
    np.savez_compressed(FOLDER / (label + '_quality.npz'), **data)
    write(label + '_quality.json', metadata)
    return {'variant': label, 'poses': len(metadata['cases']), 'meshes': len(shapes), 'missing': metadata['missing']}


def benchmark(label, block, scenario, detail, mode='B'):
    from maya_tools.scripts.tools import rig_benchmark as rb
    open_variant(label)
    assert not cmds.about(batch=True)
    # Preserve authored wrinkle settings in the file. The owned test scene
    # explicitly routes primary/final head output for comparable detail cohorts.
    destination = 'cabeza_high_Shape.inMesh'
    source = 'EdwardWrinkles_ToMaya.mayaMesh[0]' if detail else 'cabeza_high_poseCorrectives_BLS.outputGeometry[0]'
    cpu('off'); cmds.connectAttr(source, destination, force=True); cpu()
    wrinkle_values = {}
    if detail:
        for plug in cmds.ls('*.wrinkleDepth') or []:
            if cmds.getAttr(plug, settable=True):
                cmds.setAttr(plug, 1)
                if plug.split('.')[0].endswith('_CTL'):
                    wrinkle_values[plug] = 1
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    # Lock the closing reference to the original viewport cohort. A window
    # resize during the initial A2 block invalidated that whole reference block.
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
    from maya import OpenMayaUI
    window = wrapInstance(int(OpenMayaUI.MQtUtil.mainWindow()), QtWidgets.QWidget)
    window.setMinimumSize(0, 0); window.setMaximumSize(16777215, 16777215)
    window.showNormal(); QtWidgets.QApplication.processEvents()
    for _ in range(5):
        width = cmds.control('modelPanel4', q=True, width=True)
        height = cmds.control('modelPanel4', q=True, height=True)
        if (width, height) == (879, 686):
            break
        window.resize(window.width() + 879 - width, window.height() + 686 - height)
        QtWidgets.QApplication.processEvents()
    window.setFixedSize(window.size())
    dimensions = (cmds.control('modelPanel4', q=True, width=True), cmds.control('modelPanel4', q=True, height=True))
    assert dimensions == (879, 686), dimensions
    cmds.modelEditor('modelPanel4', edit=True, rendererName='vp2Renderer', displayAppearance='smoothShaded',
                     displayTextures=False, shadows=False, grid=False, selectionHiliteDisplay=False)
    camera_file = FOLDER / 'benchmark_camera.json'
    if camera_file.exists():
        camera = json.loads(camera_file.read_text())
        cmds.xform('persp', ws=True, matrix=camera['matrix'])
        cmds.setAttr('perspShape.focalLength', camera['focalLength'])
    else:
        cmds.select('cuerpo_base', 'cabeza_high'); cmds.viewFit('persp', fitFactor=.8, animate=False)
        write('benchmark_camera.json', {'matrix': cmds.xform('persp', q=True, ws=True, matrix=True),
                                        'focalLength': cmds.getAttr('perspShape.focalLength')})
    cmds.select(clear=True)
    visible = {}
    for mesh in ('cuerpo_base', 'cabeza_high'):
        selection = om.MSelectionList(); selection.add(mesh)
        visible[mesh] = selection.getDagPath(0).isVisible()
    assert all(visible.values()), visible
    definition = cases()
    if scenario == 'FK':
        selected = [p for p in definition if p[0] in ('fk_neutral', 'L_fk_bend', 'R_fk_twist', 'R_fk_bend', 'L_fk_twist')]
    else:
        selected = [p for p in definition if p[0] in ('ik_neutral', 'L_ik_bend', 'R_ik_bend', 'ik_combined', 'L_roll30', 'R_roll30')]
    selected = [(name, dict(values, **wrinkle_values,
                 **{'C_jaw_CTL.rotateX': 22 * math.sin(math.pi * i / (len(selected) - 1)),
                    'L_eyebrowIn_CTL.translateY': 1.5 * math.sin(math.pi * i / (len(selected) - 1))}))
                for i, (name, values) in enumerate(selected)]
    path = FOLDER / ('timing_%s_%s_%s_detail%d_%s.json' % (block, label, scenario, detail, mode))
    progress('benchmark', variant=label, block=block, scenario=scenario, detail=detail, mode=mode)
    raw_passes = []
    play_once = rb._play_once
    def collect_samples(frames):
        samples = play_once(frames)
        raw_passes.append(samples)
        return samples
    rb._play_once = collect_samples
    try:
        result = rb.run_state('Edward', str(path), state=mode, cases=selected, frames=(1, 48), repeats=3,
                              warmup_frames=8, allow_unsaved=True)
    finally:
        rb._play_once = play_once
    result['raw_passes_ms'] = raw_passes
    result['raw_passes_scope'] = 'Warmup followed by three full passes; timing summaries discard the first 8 frames of measured passes.'
    result['end_viewport_dimensions'] = [cmds.control('modelPanel4', q=True, width=True), cmds.control('modelPanel4', q=True, height=True)]
    assert result['end_viewport_dimensions'] == [879, 686], result['end_viewport_dimensions']
    if detail:
        cmds.setAttr('C_jaw_CTL.rotateX', 20); cmds.setAttr('L_eyebrowIn_CTL.translateY', 1.5)
        for plug, value in wrinkle_values.items():
            cmds.setAttr(plug, value)
        def plug_points(plug):
            cmds.dgeval(plug)
            selection = om.MSelectionList(); selection.add(plug)
            return np.asarray(om.MFnMesh(selection.getPlug(0).asMObject()).getPoints())[:, :3]
        before = plug_points('cabeza_high_poseCorrectives_BLS.outputGeometry[0]')
        after = plug_points('EdwardWrinkles_ToMaya.mayaMesh[0]')
        result['verified_wrinkle_displacement_cm'] = float(np.linalg.norm(after - before, axis=1).max())
        assert result['verified_wrinkle_displacement_cm'] > 1e-4, 'No active wrinkle displacement'
    path.write_text(json.dumps(result, indent=2))
    return {'path': str(path), 'timing': result['timing'], 'run_medians': [r['median_ms'] for r in result['runs']],
            'viewport': result['environment']['viewports'], 'missing': result['skipped_channels'],
            'verified_wrinkle_displacement_cm': result.get('verified_wrinkle_displacement_cm')}


args = globals().get('TRIAL_ARGUMENTS', {})
action = args.get('action', 'build')
if action == 'build':
    result = build(args['variant'])
elif action == 'quality':
    result = capture_quality(args['variant'])
elif action == 'benchmark':
    result = benchmark(args['variant'], args['block'], args['scenario'], int(args['detail']), args.get('mode', 'B'))
