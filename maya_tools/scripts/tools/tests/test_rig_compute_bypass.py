"""Native owned bypass, fresh re-enable, idempotent restoration and reopen."""
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
from maya_tools.scripts.tools import bifrost_wrinkles as bw, rig_performance as rp, rig_benchmark


def points(mesh):
    shape, _, fn = bw._mesh_fn(mesh)
    cmds.dgeval(shape + '.outMesh')
    fn = bw._mesh_fn(shape)[2]
    return np.asarray([[p.x, p.y, p.z] for p in fn.getPoints()])


try:
    root = cmds.createNode('transform', name='Character')
    high = cmds.polyPlane(w=8, h=8, sx=12, sy=12, ch=False)[0]
    low = cmds.polyCube()[0]
    cmds.parent(high, low, root)
    _, handle = cmds.cluster(high + '.vtx[*]')
    rest = points(high)
    patterns = {r: [1. if r == 'Forehead' else 0. for _ in rest] for r in bw.REGIONS}
    setup = bw.build(high, 'WrinkleTrial', patterns, compact=True, in_place=True)
    rp.create_detail_modes(root, [high], [low], [setup['settings']])
    cmds.setAttr(setup['settings'] + '.ManualActivation', 1)
    rp.install_compute_bypass(root)
    assert np.allclose(points(high) - rest, [0, .3, 0], atol=2e-5)
    owned_before = {kind: sorted(cmds.ls(type=kind) or []) for kind in
                    ('network', 'condition', 'multiplyDivide', 'bifrostGraphShape', 'bifrostGeoToMaya', 'mesh')}
    for repeat in range(4):
        rp.restore_detail_modes(rp.export_detail_modes())
        assert {kind: sorted(cmds.ls(type=kind) or []) for kind in owned_before} == owned_before
    rp.set_detail_mode(root, 0)
    primary = cmds.connectionInfo(setup['graph'] + '.AnimatedFace', sourceFromDestination=True)
    assert cmds.connectionInfo(setup['output_shape'] + '.inMesh', sourceFromDestination=True) == primary
    cmds.setAttr(handle + '.scaleX', .8)
    cmds.setAttr(setup['settings'] + '.Depth', .6)
    rp.set_detail_mode(root, 1)
    assert cmds.connectionInfo(setup['output_shape'] + '.inMesh', sourceFromDestination=True) == setup['converter'] + '.mayaMesh[0]'
    assert np.allclose(points(high)[:, 0], rest[:, 0] * .8, atol=2e-5)
    assert np.allclose(points(high)[:, 1], .6, atol=2e-5), 'Re-enabled output was stale.'
    expected = points(high)
    with tempfile.TemporaryDirectory() as folder:
        scene = str(Path(folder) / 'bypass.mb')
        cmds.file(rename=scene); cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(new=True, force=True); cmds.file(scene, open=True, force=True)
        assert np.allclose(points(high), expected, atol=2e-5)
        assert bw._indices(setup['graph'], 'ActiveIndices') == list(range(len(rest)))
        rp.restore_detail_modes(rp.export_detail_modes())
        assert {kind: sorted(cmds.ls(type=kind) or []) for kind in owned_before} == owned_before
    try:
        rig_benchmark.run_state(root, 'unused.performance.json')
        raise AssertionError('A batch process certified interactive performance.')
    except ValueError:
        pass
    print('PASS compute bypass, fresh re-enable, stable restore counts, native reopen and batch guard', flush=True)
finally:
    maya.standalone.uninitialize()
