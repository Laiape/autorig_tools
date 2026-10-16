"""Native authored joint axes, guide curve transforms and solver adapters."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
_CACHE = tempfile.TemporaryDirectory()
os.environ['AUTORIG_BUILD_CACHE_DIR'] = _CACHE.name

import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import guides_manager, guide_frames, rig_manager


class AuthoredGuideTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.optionVar(stringValue=('currentAssetRigName', 'chihuahua'))
        guides_manager.clear_guides_cache()

    def assertMatrix(self, actual, expected, places=6):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=places)

    def test_native_joint_import_preserves_saved_world_axes_and_branching(self):
        _, document = guides_manager._load_guides_file('chihuahua')
        data = document['chihuahua']
        roots = [name for name, value in data.items()
                 if value.get('isJoint') and value.get('parent') == 'C_guides_GRP']
        self.assertIn('C_localHip_JNT', roots)
        for root in roots:
            chain = guides_manager.get_guides(root)
            for joint in chain:
                self.assertMatrix(cmds.xform(joint, query=True, worldSpace=True, matrix=True),
                                  data[joint]['joint_matrix'])
                parent = data[joint]['parent']
                if parent != 'C_guides_GRP':
                    self.assertEqual(cmds.listRelatives(joint, parent=True), [parent])

    def test_sampler_keeps_authored_axes_and_terminal_orientation(self):
        chain = guides_manager.get_guides('C_tail00_JNT')
        matrices = guides_manager.sample_chain_matrices(chain, 5, preserve_orientation=True)
        for joint in chain:
            expected = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
            candidates = [matrix for matrix in matrices
                          if max(abs(a-b) for a, b in zip(matrix[12:15], expected[12:15])) < 1e-7]
            self.assertEqual(len(candidates), 1)
            self.assertMatrix(candidates[0], expected)

    def test_transformed_curve_exports_and_reimports_in_the_same_world_space(self):
        cmds.createNode('transform', name='C_guides_GRP')
        curve = cmds.curve(name='testGuide_CRV', degree=1,
                           point=[(0, 0, 0), (1, 2, 0), (2, 0, 1)])
        cmds.parent(curve, 'C_guides_GRP')
        cmds.setAttr(curve + '.translate', 3, 5, 7)
        cmds.setAttr(curve + '.rotate', 21, -37, 45)
        cmds.setAttr(curve + '.scale', 1.2, .8, 1.5)
        shape_name = cmds.listRelatives(curve, shapes=True)[0]
        expected = cmds.xform(curve + '.cv[*]', query=True, worldSpace=True, translation=True)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'assets/chihuahua/guides/test.guides'
            path.parent.mkdir(parents=True)
            with patch.object(rig_manager, 'get_rig_data', return_value=None):
                guides_manager.get_guides_info(str(path))
            document = json.loads(path.read_text())
            self.assertIn('world_matrix', document['chihuahua'][shape_name]['curve_data'])
            cmds.file(new=True, force=True)
            with patch.object(guides_manager, '_load_guides_file', return_value=(str(path), document)):
                shape = guides_manager.get_guides(shape_name)
            actual = cmds.xform(shape + '.cv[*]', query=True, worldSpace=True, translation=True)
            self.assertMatrix(actual, expected)

    def test_solver_adapter_retains_authored_controls_and_calibrates_residual_scale(self):
        ctl = cmds.createNode('transform', name='authoredControl')
        cmds.setAttr(ctl + '.translate', 3, 4, 5)
        cmds.setAttr(ctl + '.rotate', 14, -31, 67)
        authored = cmds.xform(ctl, query=True, worldSpace=True, matrix=True)
        solver = list(om.MMatrix.kIdentity)
        solver[12:15] = authored[12:15]
        driver = guide_frames.control_drivers([ctl], [authored], [solver], 'test')[0]
        self.assertMatrix(cmds.getAttr(driver + '.matrixSum'), solver)
        self.assertMatrix(cmds.xform(ctl, query=True, worldSpace=True, matrix=True), authored)
        scale = cmds.createNode('transform', name='global')
        cmds.addAttr(scale, longName='globalScale', attributeType='double', defaultValue=1)
        target = list(solver)
        target[12] += .25
        corrected = guide_frames.calibrated_output(driver + '.matrixSum', target, 'residual',
                                                   scale_plug=scale + '.globalScale')
        self.assertMatrix(cmds.getAttr(corrected), target)
        cmds.setAttr(scale + '.globalScale', 2)
        self.assertAlmostEqual(cmds.getAttr(corrected)[12], solver[12] + .5)
        cmds.setAttr(ctl + '.rotateZ', 74)
        self.assertTrue(all(math.isfinite(x) for x in cmds.getAttr(corrected)))
        self.assertFalse(cmds.cycleCheck(all=True, list=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
