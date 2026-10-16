"""Native Maya regression for the puiastre controller shape adaptation."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'maya_tools' / 'scripts')]
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'

import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import controller_shapes as shapes
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.framework import registry


def curves(node):
    return cmds.listRelatives(node, shapes=True, noIntermediate=True,
                              type='nurbsCurve', fullPath=True) or []


def data(node, world=False):
    result = []
    for shape in curves(node):
        selection = om.MSelectionList()
        selection.add(shape)
        fn = om.MFnNurbsCurve(selection.getDagPath(0))
        result.append({'points': [(p.x, p.y, p.z, p.w) for p in fn.cvPositions(
            om.MSpace.kWorld if world else om.MSpace.kObject)],
            'knots': list(fn.knots()), 'degree': fn.degree, 'form': fn.form})
    return result


class ControllerShapesTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def control(self, name, parent=None):
        node = cmds.circle(name=name, normal=(1, 0, 0), constructionHistory=False)[0]
        return cmds.parent(node, parent)[0] if parent else node

    def multi(self, name='L_arm_CTL', parent=None):
        node = self.control(name, parent)
        extra = cmds.curve(degree=1, point=[(0, 0, 0), (1, 2, 3), (2, 1, 0)])
        cmds.parent(curves(extra)[0], node, shape=True, relative=True)
        cmds.delete(extra)
        cmds.setAttr(node + '.overrideEnabled', True)
        cmds.setAttr(node + '.overrideColor', 6)
        cmds.setAttr(curves(node)[0] + '.lineWidth', 3)
        return node

    def assertGeometry(self, expected, actual):
        self.assertEqual(len(expected), len(actual))
        for a, b in zip(expected, actual):
            for key in ('degree', 'form', 'knots'):
                self.assertEqual(a[key], b[key])
            self.assertEqual(len(a['points']), len(b['points']))
            for p, q in zip(a['points'], b['points']):
                for x, y in zip(p, q):
                    self.assertAlmostEqual(x, y, places=6)

    def test_mirror_preserves_transform_animation_children_and_noncurve_shapes(self):
        left_parent = cmds.createNode('transform', name='leftRig')
        right_parent = cmds.createNode('transform', name='rightRig')
        cmds.setAttr(left_parent + '.rotateY', 29)
        cmds.setAttr(right_parent + '.scaleX', -1)
        source = self.multi(parent=left_parent)
        target = self.control('R_arm_CTL', right_parent)
        cmds.setAttr(source + '.translateX', 4)
        cmds.setAttr(target + '.translateX', -7)
        cmds.setKeyframe(target, attribute='rotateZ', value=17)
        cmds.setAttr(target + '.scaleX', lock=True)
        child = cmds.createNode('transform', name='child', parent=target)
        locator = cmds.createNode('locator', name='locatorShape', parent=target)
        before = cmds.xform(target, query=True, matrix=True, worldSpace=True)
        connections = cmds.listConnections(target, source=True, destination=False, plugs=True)
        cmds.select(source)
        expected = data(source, world=True)
        for curve in expected:
            curve['points'] = [(-p[0], p[1], p[2], p[3]) for p in curve['points']]
        self.assertEqual(len(curve_tool.mirror_shapes()), 1)
        self.assertGeometry(expected, data(target, world=True))
        self.assertEqual(before, cmds.xform(target, query=True, matrix=True, worldSpace=True))
        self.assertEqual(connections, cmds.listConnections(target, source=True, destination=False, plugs=True))
        self.assertTrue(cmds.objExists(child))
        self.assertTrue(cmds.objExists(locator))
        self.assertTrue(cmds.getAttr(target + '.scaleX', lock=True))
        self.assertEqual(cmds.ls(selection=True), [source.rsplit('|', 1)[-1]])
        self.assertEqual(cmds.getAttr(target + '.overrideColor'), 13)
        self.assertEqual(cmds.getAttr(curves(target)[0] + '.lineWidth'), 3)

    def test_replace_multiple_namespaced_targets_and_single_undo_redo(self):
        source = self.multi('source')
        cmds.namespace(add='hero')
        targets = [self.control('hero:' + side + '_hand_CTL') for side in 'LRC']
        before = [data(target) for target in targets]
        cmds.select([source] + targets)
        selection = cmds.ls(selection=True, long=True)
        expected = data(source)
        self.assertEqual(len(curve_tool.replace_shapes()), 3)
        for target, color in zip(targets, (6, 13, 17)):
            self.assertGeometry(expected, data(target))
            self.assertEqual(cmds.getAttr(target + '.overrideColor'), color)
        self.assertEqual(cmds.ls(selection=True, long=True), selection)
        cmds.undo()
        for target, old in zip(targets, before):
            self.assertGeometry(old, data(target))
        cmds.redo()
        for target in targets:
            self.assertGeometry(expected, data(target))
        self.assertGeometry(expected, data(source))

    def test_mirror_namespaces_rgb_and_undo(self):
        cmds.namespace(add='hero')
        source = self.multi('hero:L_hand_CTL')
        target = self.control('hero:R_hand_CTL')
        other = self.control('R_hand_CTL')
        before, other_before = data(target), data(other)
        cmds.setAttr(source + '.overrideRGBColors', True)
        cmds.setAttr(source + '.overrideColorRGB', .2, .4, .8, type='double3')
        self.assertEqual(len(shapes.mirror_shapes()), 1)
        self.assertTrue(cmds.getAttr(target + '.overrideRGBColors'))
        for a, b in zip(cmds.getAttr(target + '.overrideColorRGB')[0], (.2, .4, .8)):
            self.assertAlmostEqual(a, b, places=6)
        self.assertGeometry(other_before, data(other))
        cmds.undo()
        self.assertGeometry(before, data(target))

    def test_shape_color_mapping_intermediate_shapes_and_scoped_mirror(self):
        source = self.multi()
        target = self.control('R_arm_CTL')
        other_source = self.multi('L_leg_CTL')
        other_target = self.control('R_leg_CTL')
        other_before = data(other_target)
        intermediate = cmds.createNode('nurbsCurve', parent=target, name='originalShape')
        cmds.setAttr(intermediate + '.intermediateObject', True)
        for shape in curves(source):
            cmds.setAttr(shape + '.overrideEnabled', True)
            cmds.setAttr(shape + '.overrideColor', 18)
        self.assertEqual(len(shapes.mirror_shapes([source])), 1)
        self.assertTrue(cmds.objExists(intermediate))
        for shape in curves(target):
            self.assertEqual(cmds.getAttr(shape + '.overrideColor'), 4)
        self.assertGeometry(other_before, data(other_target))

    def test_undo_disabled_prevents_partial_edits(self):
        source = self.multi()
        target = self.control('R_arm_CTL')
        before = data(target)
        cmds.select(source, target)
        cmds.undoInfo(state=False)
        try:
            with self.assertRaisesRegex(RuntimeError, 'Enable Maya Undo'):
                shapes.replace_shape_colored()
            self.assertGeometry(before, data(target))
        finally:
            cmds.undoInfo(state=True)

    def test_skip_connected_and_locked_targets_without_deleting_geometry(self):
        source = self.multi()
        target = self.control('R_arm_CTL')
        consumer = cmds.createNode('curveInfo')
        cmds.connectAttr(curves(target)[0] + '.worldSpace[0]', consumer + '.inputCurve')
        before = data(target)
        self.assertEqual(shapes.mirror_shapes(), [])
        self.assertGeometry(before, data(target))
        cmds.select(source, target)
        self.assertEqual(shapes.replace_shape_colored(), [])
        cmds.delete(consumer)
        cmds.lockNode(target, lock=True)
        self.assertEqual(shapes.mirror_shapes(), [])
        self.assertGeometry(before, data(target))

    def test_bad_source_is_noop_and_display_failure_rolls_back_all_targets(self):
        source = cmds.createNode('transform', name='source')
        target = self.control('R_arm_CTL')
        cmds.select(source, target)
        before = data(target)
        self.assertEqual(shapes.replace_shape_colored(), [])
        self.assertGeometry(before, data(target))
        source = self.multi('sourceCurve')
        second = self.control('C_arm_CTL')
        cmds.setAttr(second + '.overrideColor', lock=True)
        cmds.select(source, target, second)
        node_count = len(cmds.ls())
        with self.assertRaises(ValueError):
            shapes.replace_shape_colored()
        self.assertGeometry(before, data(target))
        self.assertEqual(len(cmds.ls()), node_count)
        self.assertEqual(len(cmds.ls(selection=True)), 3)

    def test_rational_closed_and_periodic_curves_survive_native_reopen(self):
        source = cmds.curve(name='source', degree=2,
                            pointWeight=[(0, 0, 0, 1), (1, 2, 0, .5), (2, 0, 0, 1)])
        closed = cmds.curve(degree=1, point=[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0)])
        cmds.closeCurve(closed, constructionHistory=False, replaceOriginal=True, preserveShape=True)
        periodic = self.control('periodic')
        for extra in (closed, periodic):
            cmds.parent(curves(extra)[0], source, shape=True, relative=True)
            cmds.delete(extra)
        target = self.control('C_test_CTL')
        expected = data(source)
        cmds.select(source, target)
        shapes.replace_shape_colored()
        self.assertGeometry(expected, data(target))
        with tempfile.TemporaryDirectory() as folder:
            cmds.file(rename=str(Path(folder) / 'shapes.mb'))
            cmds.file(save=True, type='mayaBinary')
            cmds.file(str(Path(folder) / 'shapes.mb'), open=True, force=True)
            self.assertGeometry(expected, data(target))
            self.assertFalse(cmds.listConnections(curves(target)[0] + '.create', source=True, destination=False))
            cmds.file(new=True, force=True)

    def test_catalogue_uses_existing_menu_adapters(self):
        self.assertIn('controllers_replace', registry.BY_ID)
        for tool_id in ('controllers_mirror', 'controllers_replace'):
            tool = registry.BY_ID[tool_id]
            self.assertEqual(tool.section, 'Controllers')
            self.assertEqual(tool.kind, 'action')
        self.assertTrue(callable(curve_tool.replace_shape_colored))
        self.assertTrue(callable(curve_tool.mirror_curves))


if __name__ == '__main__':
    unittest.main()
