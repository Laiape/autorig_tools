"""Exact compact halos, one displayed mesh, primary consumers and serialization."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from maya_tools.scripts.tools import bifrost_wrinkles as bw, rig_performance as rp


def positions(mesh):
    shape, path, fn = bw._mesh_fn(mesh)
    cmds.dgeval(shape + '.outMesh')
    fn = bw._mesh_fn(shape)[2]
    return np.asarray([[p.x, p.y, p.z] for p in fn.getPoints()])


try:
    source = cmds.polyPlane(w=12, h=12, sx=30, sy=30, ch=False, name='Head')[0]
    rest = positions(source)
    cluster, handle = cmds.cluster(source + '.vtx[*]', name='PrimaryCluster')
    control = cmds.createNode('transform', name='Local_CTL')
    patterns = {r: [0.] * len(rest) for r in bw.REGIONS}
    for i, p in enumerate(rest):
        if abs(p[0]) < 2 and abs(p[2]) < 2:
            patterns['Forehead'][i] = math.cos(p[0] * 3)
        if 1 < p[0] < 3 and abs(p[2]) < 1:
            patterns['Cheeks'][i] = .4
    fields = [{'controller': control, 'masks': {'Forehead': [float(p[0] < 1) for p in rest]}}]
    dense = bw.build(source, 'Dense', patterns, control_fields=fields)
    compact = bw.build(source, 'Compact', patterns, control_fields=fields, compact=True)
    sink = cmds.createNode('transform', name='PrimaryConsumer')
    sink_shape = cmds.createNode('mesh', parent=sink)
    cmds.connectAttr(bw._mesh_fn(source)[0] + '.worldMesh[0]', sink_shape + '.inMesh')
    meshes_before = len(cmds.ls(type='mesh'))
    local = bw.build(source, 'Local', patterns, control_fields=fields, compact=True, in_place=True)
    assert len(cmds.ls(type='mesh')) == meshes_before, 'A full head mesh was duplicated.'
    assert local['output'] == bw._mesh_fn(source)[1].fullPathName().rsplit('|', 1)[0]
    assert not cmds.objExists('Local_Face')
    assert local['regional_support']['active_fraction'] < .25
    assert local['regional_support']['compression_fraction'] < .4
    maximum_error = 0.
    for method in ('off', 'serial', 'parallel'):
        cmds.evaluationManager(mode=method)
        for scale, manual, depth, value in ((1., 0., 1., 1.), (.9, 0., 1., 1.),
                                            (.7, 0., 2., .5), (1.2, 0., 1., 1.),
                                            (.9, .5, 1.5, .25), (1., 1., 1., 0.)):
            cmds.setAttr(handle + '.scaleX', scale)
            cmds.setAttr(handle + '.scaleZ', scale)
            cmds.setAttr(control + '.wrinkleDepth', depth)
            cmds.setAttr(control + '.wrinkleValue', value)
            for setup in (dense, compact, local):
                cmds.setAttr(setup['settings'] + '.ManualActivation', manual)
            expected = positions(dense['output'])
            for candidate in (compact['output'], source):
                error = float(np.max(np.linalg.norm(positions(candidate) - expected, axis=1)))
                maximum_error = max(maximum_error, error)
                assert error < 1e-4, (method, scale, candidate, error)
            cmds.setAttr(dense['settings'] + '.Envelope', 0)
            base = positions(dense['output'])
            assert np.allclose(positions(sink), base, atol=2e-5), 'Final detail leaked into primary consumers.'
            inactive = sorted(set(range(len(rest))) - set(local['regional_support']['active']))
            assert np.allclose(positions(source)[inactive], base[inactive], atol=2e-5)
            cmds.setAttr(dense['settings'] + '.Envelope', 1)
    cmds.setAttr(handle + '.translateX', 3)
    cmds.setAttr(handle + '.rotateY', 25)
    assert np.allclose(positions(source), positions(dense['output']), atol=3e-5)
    for setup in (dense, compact, local):
        cmds.setAttr(setup['settings'] + '.ManualActivation', 1)
    cmds.setAttr(control + '.wrinkleValue', 1)
    expected = positions(source)
    cmds.setAttr(local['settings'] + '.Envelope', 0)
    assert np.max(np.abs(positions(source) - expected)) > .01
    cmds.setAttr(local['settings'] + '.Envelope', 1)
    record = next(r for r in bw.export_setups() if r['prefix'] == 'Local')
    assert record['compact'] and record['in_place']
    for repeat in range(3):
        bw.import_setups([record], replace_existing=True)
        assert len(cmds.ls(type='mesh')) == meshes_before
        assert np.allclose(positions(source), expected, atol=3e-5)
    with tempfile.TemporaryDirectory() as directory:
        scene = str(Path(directory) / 'regional.mb')
        cmds.file(rename=scene); cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(new=True, force=True); cmds.file(scene, open=True, force=True)
        assert np.allclose(positions(source), expected, atol=3e-5)
        assert not cmds.objExists('Local_Face')
    before_remove = len(cmds.ls(type='transformGeometry'))
    bw.remove_setup('Local_Settings')
    assert len(cmds.ls(type='transformGeometry')) < before_remove
    assert cmds.connectionInfo(sink_shape + '.inMesh', sourceFromDestination=True).endswith('.worldMesh[0]')
    assert not cmds.ls(type='expression')
    print('PASS regional native wrinkles: exact halos, %d active/%d source vertices, max error %.9g, one head mesh, primary consumers, replacement and reopen'
          % (len(compact['regional_support']['active']), len(rest), maximum_error), flush=True)
finally:
    maya.standalone.uninitialize()
