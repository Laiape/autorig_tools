"""Repair saved v3 primary-roll zeros without losing curves, joints or weights."""
from pathlib import Path
import sys
import tempfile
from unittest import mock

import maya.standalone
from maya import cmds
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'maya_tools/scripts')]
from test_eyelid_blink import build, sample
from maya_tools.scripts.tools import eyelid_contact, eyelid_corners, eyelid_rotation


def legacy_zero(prefix, label):
    """Reproduce the former v3 graph, including its unsaved zero array element."""
    for node in cmds.ls(prefix+'_eyelid'+label+'Rotation00Z_MUL*', type='multiply') or []:
        plug = node+'.input[0]'
        source = cmds.connectionInfo(plug, sourceFromDestination=True)
        if source:
            cmds.disconnectAttr(source, plug)
        cmds.setAttr(plug, 0)


def run():
    maya.standalone.initialize(name='python')
    for plugin in ('matrixNodes', 'lookdevKit'):
        cmds.loadPlugin(plugin, quiet=True)
    for side in ('L', 'R'):
        with mock.patch.object(eyelid_rotation, '_remove_secondary_primary_z', legacy_zero), \
                mock.patch.object(eyelid_corners, 'VERSION', 3):
            eye = build(side, True)
        cmds.evaluationManager(mode='off')
        cmds.setAttr(side+'_eyelidUp_CTL.rz', 25)
        cmds.setAttr(side+'_eyelidDown_CTL.rz', -15)
        for attr in ('Upper_Blink', 'Lower_Blink'):
            cmds.setAttr(eye.eye_direct_ctl+'.'+attr, .7)
        joints = sorted(cmds.ls(side+'_*Eyelid*Skinning_JNT', type='joint'))
        expected_curves = sample(eye)
        expected_matrices = np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joints])
        skins = [side+'_'+label+'Eyelid_SKIN' for label in ('upper', 'lower')]

        def weights():
            return {skin: [cmds.skinPercent(skin, side+'_eyelid'+label+'Pose_CRV.cv[%d]' % i,
                                           query=True, value=True) for i in range(7)]
                    for skin, label in zip(skins, ('Up', 'Down'))}

        expected_weights = weights()
        with tempfile.TemporaryDirectory() as folder:
            legacy = str(Path(folder)/'legacy_v3.ma')
            cmds.file(rename=legacy)
            cmds.file(save=True, type='mayaAscii', force=True)
            cmds.file(legacy, open=True, force=True, executeScriptNodes=False)
            assert np.max(np.abs(sample(eye)-expected_curves)) > 1e-5
            cmds.undoInfo(state=True)
            assert eyelid_contact.upgrade([eye.eye_direct_ctl]) == [side]
            assert eyelid_corners.current(side)

            def equivalent():
                assert np.allclose(sample(eye), expected_curves, atol=1e-6, rtol=0)
                actual = np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joints])
                assert np.allclose(actual, expected_matrices, atol=1e-6, rtol=0)
                assert weights() == expected_weights

            equivalent()
            nodes = set(cmds.ls())
            assert not eyelid_contact.upgrade([eye.eye_direct_ctl])
            assert set(cmds.ls()) == nodes
            cmds.undo()
            assert not eyelid_corners.current(side)
            cmds.redo()
            equivalent()
            for kind, extension in (('mayaAscii', 'ma'), ('mayaBinary', 'mb')):
                path = str(Path(folder)/('repaired.'+extension))
                cmds.file(rename=path)
                cmds.file(save=True, type=kind, force=True)
                cmds.file(path, open=True, force=True, executeScriptNodes=False)
                equivalent()
    print('PASS v3 eyelid persistence repair: L/R curves, joints, exact weights, undo/redo, idempotence, MA/MB reopen')


if __name__ == '__main__':
    run()
