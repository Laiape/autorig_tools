"""Native quadruped root spaces, movable body pivot, chest and pinned head."""
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import maya.standalone
import maya.cmds as cmds
import maya.api.OpenMaya as om
from test_quadruped_guide_paths import setup, module, close


def matrix(node):
    return cmds.getAttr(node + '.worldMatrix[0]')


def reset(row):
    for ctl in row['controls']:
        cmds.setAttr(ctl + '.translate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotate', 0, 0, 0)
    cmds.setAttr('masterwalk_ctl.globalScale', 1)


class QuadrupedBodySpacesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        maya.standalone.initialize(name='python')
        for plugin in ('lookdevKit', 'matrixNodes'):
            cmds.loadPlugin(plugin, quiet=True)
        cls.helpers = setup()

    def build(self, kind='spine'):
        row = module(kind, [(0, 10, 0), (10, 10, 0)], 3, self.helpers,
                     spine_tangents=kind == 'spine')
        reset(row)
        return row

    def switch(self, target, sources, names):
        from maya_tools.scripts.utils import matrix_manager
        data = SimpleNamespace(get_data=lambda *args: 'masterwalk_ctl')
        with patch.object(matrix_manager.data_manager, 'DataExportBiped', return_value=data):
            matrix_manager.space_switches(target, sources, sources_names=names,
                                          default_translate=1, default_rotate=1)

    def test_spine_hierarchy_and_three_spaces(self):
        row = self.build()
        root = row['controls'][0]
        before = [om.MMatrix(matrix(ctl)) for ctl in row['controls']]
        root_rest = om.MMatrix(matrix(root))
        cmds.setAttr(root + '.translateY', 2)
        cmds.setAttr(root + '.rotateZ', 19)
        delta = root_rest.inverse() * om.MMatrix(matrix(root))
        for ctl, original in zip(row['controls'], before):
            close(matrix(ctl), list(original * delta), 1e-6)
        reset(row)
        self.switch('C_pelvis_CTL', ['C_body_CTL'], ['body'])
        self.switch(root, ['C_body_CTL', 'C_pelvis_CTL', 'masterwalk_ctl'],
                    ['body', 'localHip', 'masterWalk'])
        self.assertEqual(cmds.attributeQuery('SpaceFollow', node=root, listEnum=True),
                         ['body:localHip:masterWalk'])
        self.assertEqual(cmds.getAttr(root + '.TranslateValue'), 1)
        self.assertEqual(cmds.getAttr(root + '.RotateValue'), 1)
        for choice, driver in enumerate(('C_body_CTL', 'C_pelvis_CTL', 'masterwalk_ctl')):
            cmds.setAttr(root + '.SpaceFollow', choice)
            original = matrix(root)
            cmds.setAttr(driver + '.translateZ', .8)
            self.assertAlmostEqual(matrix(root)[14] - original[14], .8, places=6)
            cmds.setAttr(driver + '.translateZ', 0)
        self.assertFalse(cmds.cycleCheck(all=True, list=True))

    def test_movable_body_pivot(self):
        self.build()
        body = 'C_body_CTL'
        pivot = 'C_bodyPivot_CTL'
        original = matrix(body)
        cmds.setAttr(pivot + '.translate', 2, 1, -3)
        close(matrix(body), original, 1e-6)
        close(matrix('C_body_GRP'), matrix(pivot), 1e-6)
        cmds.setAttr(body + '.rotateZ', 35)
        rotation = om.MEulerRotation(0, 0, math.radians(35)).asMatrix()
        before = om.MTransformationMatrix()
        after = om.MTransformationMatrix()
        before.setTranslation(om.MVector(-2, -1, 3), om.MSpace.kWorld)
        after.setTranslation(om.MVector(2, 1, -3), om.MSpace.kWorld)
        expected = before.asMatrix() * rotation * after.asMatrix() * om.MMatrix(original)
        close(matrix(body), list(expected), 1e-6)
        cmds.setAttr('masterwalk_ctl.globalScale', 1.7)
        self.assertTrue(all(math.isfinite(v) for v in matrix(body)))
        self.assertFalse(cmds.cycleCheck(all=True, list=True))

    def test_each_secondary_control_has_local_and_global_follow(self):
        for kind in ('spine', 'neck'):
            row = self.build(kind)
            root = row['controls'][0]
            for ctl in row['controls'][1:]:
                self.assertEqual(cmds.attributeQuery('follow', node=ctl, listEnum=True), ['Local:Global'])
                cmds.setAttr(ctl + '.follow', 0)
                before = matrix(ctl)
                cmds.setAttr(root + '.translateY', 1)
                self.assertAlmostEqual(matrix(ctl)[13] - before[13], 1, places=6)
                cmds.setAttr(root + '.translateY', 0)
                cmds.setAttr(ctl + '.follow', 1)
                before = matrix(ctl)
                cmds.setAttr(root + '.translateY', 1)
                close(matrix(ctl), before, 1e-6)
                cmds.setAttr('masterwalk_ctl.translateZ', .7)
                self.assertAlmostEqual(matrix(ctl)[14] - before[14], .7, places=6)
                cmds.setAttr('masterwalk_ctl.translateZ', 0)
                cmds.setAttr(root + '.translateY', 0)
                cmds.setAttr(ctl + '.follow', 0)
            self.assertFalse(cmds.cycleCheck(all=True, list=True))

    def test_chest_translation_scale_rotation_and_volume(self):
        row = self.build()
        cmds.setAttr('C_body_CTL.Stretch_Activate', 1)
        baseline = cmds.getAttr('C_spineVolumeRatio_MDV.outputX')
        self.assertAlmostEqual(baseline, 1, places=6)
        for attribute, value, direction in (('translateX', 1, 1), ('translateX', -1, -1),
                                             ('scaleX', 1.2, 1), ('scaleX', .8, -1)):
            cmds.setAttr('C_localChest_CTL.' + attribute, value)
            ratio = cmds.getAttr('C_spineVolumeRatio_MDV.outputX')
            width = cmds.getAttr('C_spineVolume_BTA.output')
            self.assertGreater((ratio - 1) * direction, .01)
            self.assertLess((width - 1) * direction, -.001)
            cmds.setAttr('C_body_CTL.volumePreservation', 0)
            self.assertAlmostEqual(cmds.getAttr('C_spineVolume_BTA.output'), 1)
            cmds.setAttr('C_body_CTL.volumePreservation', 1)
            cmds.setAttr('C_localChest_CTL.' + attribute, 1 if attribute.startswith('scale') else 0)
        before = cmds.getAttr('C_spineVolumeRatio_MDV.outputX')
        cmds.setAttr('C_localChest_CTL.rotateY', 30)
        self.assertAlmostEqual(cmds.getAttr('C_spineVolumeRatio_MDV.outputX'), before, places=6)
        close(matrix('C_localChest_CTL')[12:15],
              cmds.getAttr('C_localChest_BLM.outputMatrix')[12:15], 1e-6)
        cmds.setAttr('C_localChest_CTL.rotateY', 0)
        cmds.setAttr('C_localChest_CTL.scaleY', 1.5)
        tip = cmds.getAttr('C_spineVolume07_MMX.matrixSum')
        self.assertAlmostEqual(om.MVector(tip[4:7]).length(), 1.5, places=6)
        cmds.setAttr('C_localChest_CTL.scaleY', 1)
        for scale in (.5, 2):
            cmds.setAttr('masterwalk_ctl.globalScale', scale)
            self.assertAlmostEqual(cmds.getAttr('C_spineVolumeRatio_MDV.outputX'), 1, places=6)
        self.assertFalse(cmds.cycleCheck(all=True, list=True))

    def test_head_pins_position_orientation_and_skin(self):
        row = self.build('neck')
        root, head = row['controls'][0], 'C_head_CTL'
        local = matrix(head)
        cmds.setAttr(root + '.translateY', 1)
        self.assertAlmostEqual(matrix(head)[13], local[13] + 1, places=6)
        cmds.setAttr(root + '.translateY', 0)
        cmds.setAttr(head + '.SpaceFollow', 1)
        before = matrix(head)
        skin = matrix('C_headSkinning_JNT')
        cmds.setAttr(root + '.translateY', 2)
        cmds.setAttr(root + '.rotateZ', 22)
        close(matrix(head), before, 1e-6)
        close(matrix('C_headSkinning_JNT'), skin, 1e-6)
        self.assertGreater(abs(cmds.getAttr('C_neckVolumeRatio_MDV.outputX') - 1), .01)
        cmds.setAttr(root + '.volumePreservation', 0)
        self.assertAlmostEqual(cmds.getAttr('C_neckVolume_BTA.output'), 1)
        cmds.setAttr(head + '.translateZ', 1)
        self.assertAlmostEqual(matrix('C_headSkinning_JNT')[14] - skin[14], 1, places=6)
        self.assertFalse(cmds.cycleCheck(all=True, list=True))

    def test_modes_and_native_reopen(self):
        row = self.build('neck')
        cmds.setAttr('C_head_CTL.SpaceFollow', 1)
        cmds.setAttr(row['controls'][0] + '.translateY', 1.5)
        signatures = []
        for mode in ('off', 'serial', 'parallel'):
            cmds.evaluationManager(mode=mode)
            cmds.dgdirty(allPlugs=True)
            signatures.append([v for joint in row['joints'] for v in matrix(joint)] +
                              cmds.xform(row['mesh'] + '.vtx[*]', query=True, worldSpace=True, translation=True))
        for actual in signatures[1:]:
            close(actual, signatures[0], 1e-6)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'head_spaces.mb')
            cmds.file(rename=path)
            cmds.file(save=True, type='mayaBinary', force=True)
            cmds.file(path, open=True, force=True)
            actual = [v for joint in row['joints'] for v in matrix(joint)] + cmds.xform(
                row['mesh'] + '.vtx[*]', query=True, worldSpace=True, translation=True)
            close(actual, signatures[0], 1e-6)
            cmds.file(new=True, force=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
