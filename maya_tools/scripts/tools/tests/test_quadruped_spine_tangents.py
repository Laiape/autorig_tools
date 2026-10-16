"""Three primary spine controls and two hidden endpoint tangents in Maya."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'

import maya.standalone
import maya.cmds as cmds
from test_quadruped_guide_paths import setup, module, close, functions, SCRIPTS


class SpineTangentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        maya.standalone.initialize(name='python')
        cmds.loadPlugin('lookdevKit', quiet=True)
        cmds.loadPlugin('matrixNodes', quiet=True)
        cls.helpers = setup()
        path = ROOT / 'maya_tools/assets/chihuahua/guides/chihuahua_v009.guides'
        asset = json.loads(path.read_text())['chihuahua']
        names = ['C_spine00_JNT'] + asset['C_spine00_JNT']['children']
        cls.positions = [asset[name]['joint_matrix'][12:15] for name in names]

    def test_neutral_matches_five_controls_and_tangents_follow_endpoints(self):
        baseline = module('spine', self.positions, 5, self.helpers)
        candidate = module('spine', self.positions, 3, self.helpers, spine_tangents=True)
        self.assertEqual(len(candidate['primary_controls']), 3)
        self.assertEqual(len(candidate['tangent_controls']), 2)
        close([v for m in baseline['neutral'] for v in m],
              [v for m in candidate['neutral'] for v in m], 1e-6)
        for tangent, endpoint in zip(candidate['tangent_controls'],
                                     (candidate['controls'][0], candidate['controls'][-1])):
            self.assertFalse(cmds.ls(tangent, visible=True))
            root = tangent.replace('_CTL', '_GRP')
            self.assertEqual(cmds.listRelatives(root, parent=True), [endpoint])
            before = cmds.xform(tangent, query=True, worldSpace=True, translation=True)
            rotation = cmds.getAttr(endpoint + '.rotateY')
            cmds.setAttr(endpoint + '.rotateY', rotation + 25)
            after = cmds.xform(tangent, query=True, worldSpace=True, translation=True)
            self.assertGreater(max(abs(a-b) for a, b in zip(before, after)), .01)
            cmds.setAttr(endpoint + '.rotateY', rotation)
        cmds.setAttr(candidate['controls'][0] + '.tanVisibility', True)
        for tangent in candidate['tangent_controls']:
            self.assertTrue(cmds.ls(tangent, visible=True))

    def test_reproducible_builds_and_native_reopen(self):
        first = module('spine', self.positions, 3, self.helpers, spine_tangents=True)
        second = module('spine', self.positions, 3, self.helpers, spine_tangents=True)
        close(first['state'], second['state'], 1e-6)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'spine.mb')
            cmds.file(rename=path)
            cmds.file(save=True, type='mayaBinary', force=True)
            cmds.file(path, open=True, force=True)
            state = [v for joint in second['joints']
                     for v in cmds.xform(joint, query=True, worldSpace=True, matrix=True)]
            state += cmds.xform(second['mesh'] + '.vtx[*]', query=True, worldSpace=True, translation=True)
            close(second['state'], state, 1e-6)
            for tangent in second['tangent_controls']:
                self.assertFalse(cmds.ls(tangent, visible=True))
            cmds.file(new=True, force=True)

    def test_build_settings_survive_guide_attribute_roundtrip(self):
        cmds.file(new=True, force=True)
        config = json.loads((ROOT / 'maya_tools/assets/chihuahua/build/chihuahua_v001.build').read_text())
        self.assertEqual(config['spine_controllers'], 3)
        self.assertEqual(config['spine_tangents'], 1)
        scope = dict(cmds=cmds, LEG_SOLVER_OPTIONS=('spring', 'rp'),
                     om=self.helpers[0].sample_chain_matrices.__globals__['om'])
        api = functions(SCRIPTS / 'utils/rig_manager.py',
                        {'create_rig_settings', 'load_rig_settings'}, scope)
        node = cmds.createNode('transform', name='C_guides_GRP')
        api.create_rig_settings(node)
        self.assertEqual(cmds.getAttr(node + '.spine_tangents'), 0)
        cmds.setAttr(node + '.spine_controllers', 3)
        cmds.setAttr(node + '.spine_tangents', 1)
        settings = api.load_rig_settings(node)
        self.assertEqual(settings['spine_controllers'], 3)
        self.assertEqual(settings['spine_tangents'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
