"""Run with mayapy: shared native orientation, legacy upgrade and safety guards.

AUTORIG_JAW_BASELINE may name an exact pre-change jaw source for comparison.
"""
import os
from pathlib import Path
import tempfile

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from fixtures.jaw_scene import build, SOURCE
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.tools import jaw_graph_optimizer


def matrices():
    return np.array([cmds.xform(n, query=True, worldSpace=True, matrix=True)
                     for n in sorted(cmds.ls(type='joint'))])


def sample():
    values = []
    for angle in (0, 20, 30):
        for sticky in (0, .5, 1):
            for sign in (-1, 0, 1):
                cmds.setAttr('C_jaw_CTL.rx', angle)
                cmds.setAttr('C_jaw_CTL.stickyLips', sticky)
                for side in ('L', 'R'):
                    cmds.setAttr(side + '_lipCorner_CTL.tx', sign)
                    cmds.setAttr(side + '_lipCorner_CTL.ty', abs(sign))
                values.append(matrices())
    return np.array(values)


try:
    baseline = os.environ.get('AUTORIG_JAW_BASELINE')
    if baseline:
        build(Path(baseline))
        before = sample()
        upgrade = jaw_graph_optimizer.optimize()
        # Restore matching neutral inputs before comparing the complete pose bank.
        after = sample()
        assert upgrade['removed'], upgrade
        assert np.allclose(before, after, atol=1e-5, rtol=0), np.abs(before-after).max()
        assert not jaw_graph_optimizer.optimize()['rewired']
        # The upgrade can be undone as one operation when it is the latest edit.
        build(Path(baseline))
        neutral = matrices()
        jaw_graph_optimizer.optimize()
        cmds.undo()
        assert np.allclose(matrices(), neutral, atol=1e-8, rtol=0)

    jaw = build(SOURCE)
    aims = cmds.ls('*Lip*Vector_AMX', type='aimMatrix')
    assert len(aims) == 50
    for aim in aims:
        pin = cmds.connectionInfo(aim + '.inputMatrix', sourceFromDestination=True)
        assert cmds.nodeType(pin.split('.')[0]) == 'uvPin', aim
    assert not cmds.ls('*Lip*Position_CMX', type='composeMatrix')
    assert len(cmds.ls('C_lipCorner*Frame_MMX', type='multMatrix')) == 2
    assert not jaw_graph_optimizer.optimize()['rewired']
    # uvPin keeps orthonormal axes even when its surface collapses. This is
    # required by the direct input path; generic singular matrices use compose.
    scale_locks = {axis: cmds.getAttr('C_upperLip_NURB.scale' + axis, lock=True) for axis in 'XYZ'}
    for axis in 'XYZ':
        cmds.setAttr('C_upperLip_NURB.scale' + axis, lock=False)
    for scale in (1e-9, 0.):
        cmds.setAttr('C_upperLip_NURB.scale', scale, scale, scale)
        for i in range(25):
            pin = np.array(cmds.getAttr('C_upperLipAimVector_UVP.outputMatrix[%d]' % i)).reshape(4, 4)
            assert np.allclose(pin[:3, :3] @ pin[:3, :3].T, np.eye(3), atol=1e-6, rtol=0)
        assert np.isfinite(matrices()).all()
    cmds.setAttr('C_upperLip_NURB.scale', 1, 1, 1)
    for axis, locked in scale_locks.items():
        cmds.setAttr('C_upperLip_NURB.scale' + axis, lock=locked)
    expected = sample()
    assert np.isfinite(expected).all()
    assert not (cmds.cycleCheck(all=True, list=True) or [])
    for mode in ('serial', 'parallel'):
        cmds.evaluationManager(mode=mode)
        assert np.allclose(sample(), expected, atol=1e-5, rtol=0), mode
    cmds.evaluationManager(mode='off')
    with tempfile.TemporaryDirectory(prefix='jaw_orientation_') as folder:
        scene = Path(folder) / 'shared_orientation.mb'
        cmds.file(rename=str(scene))
        cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(new=True, force=True)
        cmds.file(str(scene), open=True, force=True)
        assert np.allclose(sample(), expected, atol=1e-5, rtol=0)

    # Generic callers retain the translation-only input and the original guards.
    cmds.file(new=True, force=True)
    pin = cmds.createNode('fourByFourMatrix')
    up = cmds.createNode('composeMatrix')
    corner = cmds.createNode('composeMatrix')
    for preserve in (False, True):
        _, output = jaw._stable_lip_aim(
            'Guard' + str(preserve), pin + '.output', up + '.outputMatrix',
            corner + '.outputMatrix', (0, 0, 0), preserve_up_direction=preserve)
        for primary in (0., 1.):
            cmds.setAttr(pin + '.in22', primary)
            for position in ((0, 0, 0), (0, 0, 1), (0, 1e-12, 1), (0, .1, 1), (0, 1, 0)):
                cmds.setAttr(up + '.inputTranslate', *position)
                matrix = np.array(cmds.getAttr(output)).reshape(4, 4)
                assert np.isfinite(matrix).all(), (preserve, primary, position)
                assert np.allclose(matrix[:3, :3] @ matrix[:3, :3].T,
                                   np.eye(3), atol=1e-5, rtol=0)
    print('PASS native jaw orientation: shared frames, upgrade, undo, guards, EM and reopen', flush=True)
finally:
    maya.standalone.uninitialize()
