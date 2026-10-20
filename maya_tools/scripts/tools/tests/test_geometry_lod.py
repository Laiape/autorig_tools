"""Native Maya LOD display behavior and persistence for tagged model groups."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.utils import geometry_lod


class GeometryLodTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        self.geo = cmds.group(empty=True, name='geo')
        self.settings = cmds.createNode('transform', name='C_settings_CTL')

    def tagged_model(self):
        for role in ('Low', 'High', 'Shared'):
            group = cmds.group(empty=True, name=role, parent=self.geo)
            mesh = cmds.polyCube(name=role + '_mesh', constructionHistory=False)[0]
            cmds.parent(mesh, group)
            if role != 'Shared':
                cmds.addAttr(group, longName='autorigLodRole', dataType='string')
                cmds.setAttr(group + '.autorigLodRole', role, type='string')

    def assert_modes(self):
        for mode in (0, 1, 0, 1):
            cmds.setAttr(self.settings + '.resolution', mode)
            self.assertEqual(cmds.getAttr('Low.visibility'), mode == 0)
            self.assertEqual(cmds.getAttr('High.visibility'), mode == 1)
            self.assertTrue(cmds.getAttr('Shared.visibility'))

    def test_untagged_asset_has_no_new_controls(self):
        before = set(cmds.ls())
        self.assertEqual(geometry_lod.configure(self.settings, self.geo), {})
        self.assertEqual(set(cmds.ls()), before)
        self.assertFalse(cmds.attributeQuery('resolution', node=self.settings, exists=True))

    def test_shared_geometry_and_existing_mode_survive_reconfigure(self):
        self.tagged_model()
        geometry_lod.configure(self.settings, self.geo)
        self.assert_modes()
        before = set(cmds.ls())
        geometry_lod.configure(self.settings, self.geo)
        self.assertEqual(set(cmds.ls()), before)
        self.assertEqual(cmds.getAttr(self.settings + '.resolution'), 1)
        self.assert_modes()

    def test_native_reopen_preserves_both_resolutions(self):
        self.tagged_model()
        geometry_lod.configure(self.settings, self.geo)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'lod.ma')
            cmds.file(rename=path)
            cmds.file(save=True, type='mayaAscii', force=True)
            cmds.file(path, open=True, force=True, executeScriptNodes=False)
            self.assert_modes()

    def test_basic_structure_preserves_nested_model_groups(self):
        from maya_tools.scripts.utils import basic_structure
        self.tagged_model()
        root = cmds.group(empty=True, name='Girl')
        cmds.parent(self.geo, root)
        self.geo = cmds.rename(self.geo, 'geo_GRP')
        final = cmds.group(empty=True, name='FINAL', parent=self.geo)
        cmds.parent('Low', 'High', 'Shared', final)
        basic_structure._parent_model_under_final(root, self.geo, final, 'Girl')
        for role in ('Low', 'High', 'Shared'):
            self.assertEqual(cmds.listRelatives(role + '_mesh', parent=True), [role])
        geometry_lod.configure(self.settings, self.geo)
        self.assert_modes()


if __name__ == '__main__':
    try:
        result = unittest.main(exit=False).result
        if not result.wasSuccessful():
            raise SystemExit(1)
    finally:
        maya.standalone.uninitialize()
