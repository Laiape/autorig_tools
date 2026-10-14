"""Run with mayapy: module ownership and unchanged NURBS evaluation spaces."""
import ast
import os
from pathlib import Path
import runpy
import unittest

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import maya.api.OpenMaya as om

SCRIPTS = Path(__file__).resolve().parents[2]
UTILITY = runpy.run_path(str(SCRIPTS / 'utils/module_nurbs.py'))
organize = UTILITY['organize_nurbs']
decorate = UTILITY['organize_module_nurbs']


def world_points(shape):
    sel = om.MSelectionList(); sel.add(shape)
    dag = sel.getDagPath(0)
    if dag.node().hasFn(om.MFn.kTransform):
        dag.extendToShape()
    fn = om.MFnNurbsSurface(dag) if dag.node().hasFn(om.MFn.kNurbsSurface) else om.MFnNurbsCurve(dag)
    return [(p.x, p.y, p.z) for p in fn.cvPositions(om.MSpace.kWorld)]


class ModuleNurbsTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        self.module = cmds.createNode('transform', name='C_testModule_GRP')
        cmds.setAttr(self.module + '.translate', 20, -7, 11)
        cmds.setAttr(self.module + '.rotateY', 30)

    def assertPointsEqual(self, expected, actual):
        self.assertEqual(len(expected), len(actual))
        self.assertLess(max(abs(a - b) for p, q in zip(expected, actual) for a, b in zip(p, q)), 1e-8)

    def test_root_curve_connected_opm_and_locked_channels(self):
        curve = cmds.curve(name='C_driver_CRV', degree=1, point=[(0, 0, 0), (2, 3, 4)])
        compose = cmds.createNode('composeMatrix')
        cmds.connectAttr(compose + '.outputMatrix', curve + '.offsetParentMatrix')
        cmds.setAttr(curve + '.tx', lock=True)
        shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        before = world_points(curve)
        moved = organize(self.module, [shape])
        self.assertEqual(len(moved), 1)
        self.assertTrue(cmds.ls(curve, long=True)[0].startswith('|' + self.module + '|'))
        self.assertPointsEqual(before, world_points(curve))
        cmds.setAttr(compose + '.inputTranslateY', 5)
        self.assertPointsEqual([(0, 5, 0), (2, 8, 4)], world_points(curve))
        self.assertTrue(cmds.getAttr(curve + '.tx', lock=True))
        self.assertEqual(cmds.connectionInfo(curve + '.offsetParentMatrix', sourceFromDestination=True), compose + '.outputMatrix')

    def test_surface_preserves_animated_parent_space_and_uv_output(self):
        original = cmds.createNode('transform', name='surfaceSpace_GRP')
        surface = cmds.nurbsPlane(name='C_driver_NURBS', constructionHistory=False)[0]
        cmds.parent(surface, original, relative=True)
        cmds.setAttr(surface + '.translate', 3, 2, -4)
        shape = cmds.listRelatives(surface, shapes=True, fullPath=True)[0]
        pin = cmds.createNode('pointOnSurfaceInfo')
        cmds.connectAttr(surface + 'Shape.worldSpace[0]', pin + '.inputSurface')
        cmds.setAttr(pin + '.parameterU', .35); cmds.setAttr(pin + '.parameterV', .65)
        for frame, value in [(1, 0), (12, 25)]:
            cmds.setKeyframe(original, attribute='rotateY', time=frame, value=value)
            cmds.setKeyframe(original, attribute='translateX', time=frame, value=value / 2)
        before = {}
        for frame in [1, 5, 12]:
            cmds.currentTime(frame)
            before[frame] = (world_points(surface), cmds.getAttr(pin + '.position')[0], cmds.getAttr(surface + '.parentMatrix[0]'))
        organize(self.module, [shape])
        for frame in before:
            cmds.currentTime(frame)
            self.assertPointsEqual(before[frame][0], world_points(surface))
            self.assertPointsEqual([before[frame][1]], [cmds.getAttr(pin + '.position')[0]])
            self.assertPointsEqual([before[frame][2]], [cmds.getAttr(surface + '.parentMatrix[0]')])

    def test_preserves_skin_and_inherits_transform_false(self):
        curve = cmds.curve(name='C_skinned_CRV', degree=1, point=[(0, 0, 0), (0, 3, 0), (0, 6, 0)])
        cmds.setAttr(curve + '.inheritsTransform', False)
        joint = cmds.createNode('joint', name='C_driver_JNT')
        skin = cmds.skinCluster(joint, curve, toSelectedBones=True)[0]
        shape = cmds.listRelatives(curve, shapes=True, noIntermediate=True, fullPath=True)[0]
        def evaluated():
            return [cmds.pointPosition(curve + '.cv[%d]' % i, world=True) for i in range(3)]
        cmds.setAttr(joint + '.tx', 2); expected = evaluated()
        organize(self.module, cmds.listRelatives(curve, shapes=True, fullPath=True))
        self.assertPointsEqual(expected, evaluated())
        cmds.setAttr(joint + '.tx', 4)
        self.assertPointsEqual([(4, 0, 0), (4, 3, 0), (4, 6, 0)], evaluated())
        self.assertEqual(cmds.listConnections(shape.rsplit('|', 1)[-1] + '.create', source=True, destination=False), [skin])

    def test_decorator_handles_subclass_build_controls_and_existing_shapes(self):
        existing = cmds.curve(name='Existing_CRV', degree=1, point=[(0, 0, 0), (0, 1, 0)])
        module = self.module
        class Base:
            @decorate
            def make(self):
                self.module_trn = module
                self.first = cmds.curve(name='Base_CRV', degree=1, point=[(0, 0, 0), (0, 1, 0)])
                self.control = cmds.circle(name='C_anim_CTL', constructionHistory=False)[0]
        class Child(Base):
            @decorate
            def make(self):
                super().make()
                self.last = cmds.nurbsPlane(name='Child_NURBS', constructionHistory=False)[0]
                return self.last
        obj = Child(); self.assertEqual(obj.make(), obj.last)
        for node in [obj.first, obj.last]:
            self.assertTrue(cmds.ls(node, long=True)[0].startswith('|' + module + '|'))
        self.assertEqual(cmds.listRelatives(existing, parent=True), None)
        self.assertEqual(cmds.listRelatives(obj.control, parent=True), None)
        self.assertEqual(obj._module_nurbs_build_depth, 0)

    def test_every_module_with_a_module_group_uses_the_decorator(self):
        count = 0
        for kind in ['biped', 'quadruped']:
            for path in (SCRIPTS / kind / 'autorig').glob('*.py'):
                text = path.read_text(encoding='utf-8')
                if 'self.module_trn' not in text:
                    continue
                for cls in ast.parse(text).body:
                    if not isinstance(cls, ast.ClassDef):
                        continue
                    for method in cls.body:
                        if isinstance(method, ast.FunctionDef) and method.name == 'make':
                            self.assertTrue(any(isinstance(d, ast.Name) and d.id == 'organize_module_nurbs' for d in method.decorator_list), str(path))
                            count += 1
        self.assertGreaterEqual(count, 27)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ModuleNurbsTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    cmds.file(new=True, force=True)
    maya.standalone.uninitialize()
    import sys
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
