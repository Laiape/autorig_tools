"""Native Maya text-controller geometry, undo and persistence regression."""
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
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.framework import registry


def outlines(node):
    return cmds.listRelatives(node, allDescendents=True, type='nurbsCurve',
                              fullPath=True) or []


def points(shape):
    return cmds.xform(shape + '.cv[*]', query=True, worldSpace=True, translation=True)


class TextControllerTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def test_word_matches_native_glyph_layout_and_holes(self):
        native = cmds.textCurves(text='B O Rig', constructionHistory=False)[0]
        bounds = cmds.exactWorldBoundingBox(native)
        center = [(bounds[i] + bounds[i + 3]) / 2 for i in range(3)]
        factor = 3.0 / (bounds[4] - bounds[1])
        expected = []
        for shape in outlines(native):
            values = points(shape)
            expected.append([(value - center[i % 3]) * factor
                             for i, value in enumerate(values)])
        node = curve_tool.create_text_shape('B O Rig', height=3.0)
        actual = [points(shape) for shape in outlines(node)]
        expected.sort(key=lambda values: (len(values), tuple(values)))
        actual.sort(key=lambda values: (len(values), tuple(values)))
        self.assertEqual(len(expected), len(actual))
        for a, b in zip(expected, actual):
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=6)
        self.assertFalse(cmds.listRelatives(node, children=True, type='transform'))
        for attr, value in [('translate', (0, 0, 0)), ('rotate', (0, 0, 0)),
                            ('scale', (1, 1, 1))]:
            self.assertEqual(cmds.getAttr(node + '.' + attr)[0], value)
        self.assertEqual(cmds.ls(selection=True), [node])
        for shape in outlines(node):
            self.assertFalse(cmds.listConnections(shape + '.create', source=True))

    def test_letter_unique_names_and_single_undo_redo(self):
        first = curve_tool.create_text_shape('F')
        second = curve_tool.create_text_shape('A')
        self.assertNotEqual(first, second)
        cmds.undo()
        self.assertTrue(cmds.objExists(first))
        self.assertFalse(cmds.objExists(second))
        cmds.redo()
        self.assertTrue(outlines(second))

    def test_invalid_input_does_not_change_scene_or_selection(self):
        anchor = cmds.createNode('transform', name='anchor')
        cmds.select(anchor)
        before = set(cmds.ls(long=True))
        for text, kwargs in [('', {}), ('   ', {}), (None, {}), ('F', {'height': 0}),
                             ('F', {'height': float('nan')}), ('F', {'name': '|bad'})]:
            with self.assertRaises(ValueError):
                curve_tool.create_text_shape(text, **kwargs)
            self.assertEqual(set(cmds.ls(long=True)), before)
            self.assertEqual(cmds.ls(selection=True), [anchor])

    def test_native_reopen_and_curve_export_import(self):
        node = curve_tool.create_text_shape('Auto Rig', height=2.0)
        expected = [points(shape) for shape in outlines(node)]
        with tempfile.TemporaryDirectory() as directory:
            scene = str(Path(directory) / 'text.mb')
            preset = str(Path(directory) / 'text.curves')
            curve_tool.get_all_ctl_curves_data(path=preset)
            self.assertTrue(Path(preset).is_file())
            cmds.file(rename=scene)
            cmds.file(save=True, type='mayaBinary')
            cmds.file(scene, open=True, force=True)
            self.assertEqual([points(shape) for shape in outlines(node)], expected)
            cmds.delete(cmds.listRelatives(node, shapes=True, fullPath=True))
            curve_tool.load_all_ctl_curves_data(preset)
            self.assertEqual([points(shape) for shape in outlines(node)], expected)

    def test_shared_controllers_entry(self):
        tool = next(t for t in registry.TOOLS if t.id == 'controllers_text')
        self.assertEqual((tool.group, tool.section), ('RIGGING', 'Controllers'))
        self.assertFalse(tool.requirements)


if __name__ == '__main__':
    unittest.main()
