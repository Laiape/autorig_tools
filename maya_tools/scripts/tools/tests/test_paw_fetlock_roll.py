"""A lifted paw keeps its foot-controlled roll when the lower IK bone turns."""
import ast
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import guide_frames


class PawRollTests(unittest.TestCase):
    def test_lift_and_solver_roll_do_not_flip_either_paw(self):
        path = ROOT / 'maya_tools/scripts/quadruped/autorig/leg_module_self.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == 'paw_attach')
        scope = dict(cmds=cmds, om=om, guide_frames=guide_frames)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
        Paw = type('PawFixture', (), {'paw_attach': scope['paw_attach']})
        file = sorted((ROOT / 'maya_tools/assets/chihuahua/guides').glob('chihuahua_v*.guides'))[-1]
        data = json.loads(file.read_text())['chihuahua']
        for side in ('L', 'R'):
            cmds.file(new=True, force=True)
            names = [side + '_frontLeg' + part + '_JNT' for part in
                     ('Shoulder', 'Elbow', 'Carpus', 'Fetlock', 'Pastern', 'Tip')]
            authored = [data[name]['joint_matrix'] for name in names]
            source = cmds.createNode('transform', name='solverEnd')
            cmds.xform(source, worldSpace=True, matrix=authored[3])
            foot = cmds.createNode('transform', name='footControl')
            cmds.xform(foot, worldSpace=True, translation=authored[3][12:15])
            master = cmds.createNode('transform', name='master')
            cmds.addAttr(master, longName='globalScale', attributeType='double', defaultValue=1)
            guides = []
            for index, matrix in enumerate(authored):
                node = cmds.createNode('transform', name='guide%d' % index)
                cmds.xform(node, worldSpace=True, matrix=matrix)
                guides.append(node + '.worldMatrix[0]')
            blends = [cmds.createNode('blendMatrix', name='blend%d' % i) for i in range(5)]
            leg = SimpleNamespace(side=side, LEG_PREFIX='frontLeg', ik_ctl={'ball': foot},
                                  authored_orientation=True, authored_guide_matrices=authored,
                                  guides_matrices=guides, leg_end_index=3, plant_index=4,
                                  nodes_ik_world=[source + '.worldMatrix[0]'] * 5,
                                  blend_matrices=blends, masterwalk_ctl=master,
                                  primary_axis=(1, 0, 0) if side == 'L' else (-1, 0, 0),
                                  lateral_axis=(0, 0, 1))
            Paw().paw_attach(leg)
            source_rotation = cmds.getAttr(source + '.rotate')[0]
            foot_inverse = om.MMatrix(cmds.getAttr(foot + '.worldInverseMatrix[0]'))
            for height in (0, 2, 4, 4.1, 4.15, 5, 7.4, 8):
                cmds.setAttr(source + '.translateY', authored[3][13] + height)
                cmds.setAttr(foot + '.translateY', authored[3][13] + height)
                for foot_angle in (-25, 0, 30):
                    cmds.setAttr(foot + '.rotateZ', foot_angle)
                    for angle in (-179, -90, -45, 0, 45, 90, 179):
                        cmds.setAttr(source + '.rotate', source_rotation[0] + angle,
                                     source_rotation[1], source_rotation[2])
                        expected = (om.MMatrix(authored[3]) * foot_inverse *
                                    om.MMatrix(cmds.getAttr(foot + '.worldMatrix[0]')))
                        actual = cmds.getAttr(blends[3] + '.outputMatrix')
                        self.assertLess(max(abs(a-b) for a, b in zip(actual, expected)), 1e-6,
                                        (side, height, foot_angle, angle))
            self.assertFalse(cmds.cycleCheck(all=True, list=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
