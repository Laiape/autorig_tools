"""Native Maya regressions. Run in a disposable mayapy, never an artist scene."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'maya_tools/scripts'))

from maya import cmds, mel
from maya.api import OpenMaya as om
from ng_nurbs_bridge import core, topology, brush


def fixture(kind='open', method=0, degree=3, sparse=False, rational=False):
    joints = [cmds.createNode('joint', name='joint%s' % i) for i in range(3)]
    cmds.setAttr(joints[0]+'.tx', -2)
    cmds.setAttr(joints[2]+'.tx', 2)
    if kind == 'closed_u':
        surface = cmds.createNode('transform', name='surface')
        shape = cmds.createNode('nurbsSurface', parent=surface)
        ring = [(1,0), (0,1), (-1,0), (0,-1), (1,0)]
        coords = ' '.join('%s %s %s' % (ring[u][0], v, ring[u][1]) for u in range(5) for v in range(3))
        mel.eval('setAttr "%s.cached" -type "nurbsSurface" 1 1 1 0 no 5 0 1 2 3 4 3 0 1 2 15 %s;' % (shape, coords))
        assert topology.signature(shape)['fu'] == om.MFnNurbsSurface.kClosed
    elif kind == 'open':
        surface = cmds.nurbsPlane(name='surface', patchesU=3, patchesV=5, degree=degree,
                                 width=4, axis=(0, 1, 0), constructionHistory=False)[0]
    elif kind == 'periodic_v':
        surface = cmds.cylinder(name='surface', sections=8, spans=3, constructionHistory=False)[0]
    else:
        surface = cmds.torus(name='surface', sections=8, spans=6, constructionHistory=False)[0]
        if kind == 'periodic_u':
            # Swap parameter axes of the cylinder, rather than relabeling V.
            cmds.delete(surface)
            surface = cmds.cylinder(name='surface', sections=8, spans=3, constructionHistory=False)[0]
            cmds.reverseSurface(surface, direction=3, replaceOriginal=True, constructionHistory=False)
    shape = topology.surface_shape(surface)
    if rational:
        fn = om.MFnNurbsSurface(topology.dag(shape))
        points = fn.cvPositions()
        index = fn.numCVsInV+1
        point = points[index]; point.w = .7; points[index] = point
        parent = cmds.createNode('transform', name='rationalSurface')
        om.MFnNurbsSurface().create(points, fn.knotsInU(), fn.knotsInV(), fn.degreeInU,
            fn.degreeInV, fn.formInU, fn.formInV, True, om.MSelectionList().add(parent).getDependNode(0))
        cmds.delete(surface)
        surface = cmds.rename(parent, 'surface')
        shape = topology.surface_shape(surface)
    cmds.group([surface]+joints, name='fixtureRoot')
    shape = topology.surface_shape(surface)
    skin = cmds.skinCluster(joints, surface, toSelectedBones=True, skinMethod=method,
                            normalizeWeights=1, obeyMaxInfluences=False)[0]
    if sparse:
        cmds.skinCluster(skin, edit=True, removeInfluence=joints[1])
    spec = topology.signature(shape)
    active = core.membership(shape, skin)
    infs = core.influences(skin)
    for index in active:
        a = 0.15+0.5*(index % 7)/7
        values = [a, 1-a] if sparse else [a, 0.15, 0.85-a]
        for inf, value in zip(infs, values):
            cmds.setAttr(skin+'.weightList[%s].weights[%s]' % (index, inf['logical']), value)
        if method == 2:
            cmds.setAttr(skin+'.blendWeights[%s]' % index, (index % 9)/8)
    return surface, skin, joints


def geometry(shape):
    fn = om.MFnNurbsSurface(topology.dag(shape))
    points = fn.cvPositions(om.MSpace.kWorld)
    for u in (.05, .3, .5, .75, .95):
        for v in (.05, .4, .9):
            spec = topology.signature(shape)
            a = spec['domain_u'][0]+u*(spec['domain_u'][1]-spec['domain_u'][0])
            b = spec['domain_v'][0]+v*(spec['domain_v'][1]-spec['domain_v'][0])
            points.append(fn.getPointAtParam(a, b, om.MSpace.kWorld))
    return [(p.x, p.y, p.z) for p in points]


def maximum_error(a, b):
    return max((om.MPoint(x)-om.MPoint(y)).length() for x,y in zip(a,b))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        brush.stop()
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        brush.stop()

    def test_open_periodic_and_sparse_weight_equivalence(self):
        for kind in ('open', 'closed_u', 'periodic_u', 'periodic_v', 'periodic_uv'):
            for sparse in (False, True):
                with self.subTest(kind=kind, sparse=sparse):
                    cmds.file(new=True, force=True)
                    surface, skin, joints = fixture(kind, sparse=sparse)
                    before = core.sparse_weights(skin)
                    shape = topology.surface_shape(surface)
                    poses = []
                    for angle in (0, 23, -38, 61, 0):
                        cmds.setAttr(joints[2]+'.ry', angle)
                        cmds.setAttr(joints[0]+'.ty', angle/30)
                        poses.append(geometry(shape))
                    bridge = core.create(surface)
                    for pose, angle in zip(poses, (0, 23, -38, 61, 0)):
                        cmds.setAttr(joints[2]+'.ry', angle)
                        cmds.setAttr(joints[0]+'.ty', angle/30)
                        self.assertLessEqual(maximum_error(pose, geometry(shape)), 1e-4)
                    for row in before:
                        for index, value in before[row].items():
                            self.assertAlmostEqual(core.sparse_weights(skin)[row][index], value, places=8)
                    bridge.detach(restore=True)
                    self.assertEqual(core.sparse_weights(skin), before)

    def test_create_redo_keeps_proxy_cage_and_layers(self):
        surface, skin, _ = fixture()
        baseline = set(cmds.ls(uuid=True))
        bridge = core.create(surface)
        proxy = core.node_for(bridge.data['proxy_uuid'])
        positions = om.MFnMesh(topology.dag(proxy)).getPoints()
        snapshot = core.layer_snapshot(bridge, bridge.layers().list()[0].id)
        cmds.undo()
        self.assertEqual(set(cmds.ls(uuid=True)), baseline)
        cmds.redo()
        bridge = core.find(surface)
        bridge.validate()
        after = om.MFnMesh(topology.dag(core.node_for(bridge.data['proxy_uuid']))).getPoints()
        self.assertLessEqual(max((a-b).length() for a,b in zip(positions,after)), 1e-10)
        self.assertEqual(snapshot, core.layer_snapshot(bridge, bridge.layers().list()[0].id))

    def test_dq_modes_global_scale_and_initialization(self):
        for method in (1, 2):
            with self.subTest(method=method):
                cmds.file(new=True, force=True)
                surface, skin, joints = fixture('periodic_uv', method=method)
                cmds.setAttr('fixtureRoot.scale', -1.5, 2, .7, type='double3')
                before = geometry(topology.surface_shape(surface))
                old_blend = cmds.getAttr(skin+'.blendWeights', multiIndices=True) or []
                blends = {i: core.plug(skin+'.blendWeights[%s]' % i).asDouble() for i in old_blend}
                bridge = core.create(surface)
                self.assertLessEqual(maximum_error(before, geometry(bridge.shape)), 1e-4)
                self.assertEqual(blends, {i: core.plug(skin+'.blendWeights[%s]' % i).asDouble() for i in old_blend})
                bridge.detach(restore=True)
                self.assertEqual(blends, {i: core.plug(skin+'.blendWeights[%s]' % i).asDouble() for i in old_blend})

    def test_stroke_masks_dq_locks_and_undo(self):
        surface, skin, joints = fixture(method=2)
        bridge = core.create(surface)
        layer = bridge.layers().list()[0]
        for target in (0, 'mask', 'dq'):
            with self.subTest(target=target):
                before = core.layer_snapshot(bridge, layer.id)
                brush.Controller(bridge, layer.id, target, intensity=1, value=.7).flood()
                after = core.layer_snapshot(bridge, layer.id)
                self.assertNotEqual(before, after)
                cmds.undo()
                self.assertEqual(before, core.layer_snapshot(bridge, layer.id))
                cmds.redo()
                self.assertEqual(after, core.layer_snapshot(bridge, layer.id))
        layer.locked_influences = [1]
        locked = list(layer.get_weights(1))
        brush.Controller(bridge, layer.id, 0, intensity=1, value=1).flood()
        self.assertEqual(locked, layer.get_weights(1))
        cmds.setAttr(joints[2]+'.liw', True)
        locked = list(layer.get_weights(2))
        brush.Controller(bridge, layer.id, 0, intensity=1, value=.2).flood()
        self.assertEqual(locked, layer.get_weights(2))
        with self.assertRaisesRegex(ValueError, 'locked'):
            brush.Controller(bridge, layer.id, 2).flood()

    def test_added_layer_mask_opacity_and_disable(self):
        surface, skin, _ = fixture()
        bridge = core.create(surface)
        original = core.sparse_weights(skin)
        layer = bridge.layers().add('Paint layer', force_empty=True)
        brush.Controller(bridge, layer.id, 0, intensity=1, value=.9).flood()
        painted = core.sparse_weights(skin)
        self.assertNotEqual(original, painted)
        layer.opacity = 0
        for row in original:
            for index, value in original[row].items():
                self.assertAlmostEqual(value, core.sparse_weights(skin)[row][index], places=8)
        layer.opacity = 1
        brush.Controller(bridge, layer.id, 'mask', intensity=1, value=0).flood()
        layer.enabled = False
        for row in original:
            for index, value in original[row].items():
                self.assertAlmostEqual(value, core.sparse_weights(skin)[row][index], places=8)

    def test_replace_value_preserves_base_layer_normalization(self):
        surface, skin, _ = fixture()
        bridge = core.create(surface)
        layer = bridge.layers().list()[0]
        brush.Controller(bridge, layer.id, 0, intensity=1, value=.25).flood()
        for row in bridge.data['active']:
            self.assertAlmostEqual(core.sparse_weights(skin)[str(row)]['0'], .25, places=8)

    def test_smooth_can_remove_a_fully_weighted_spike(self):
        surface, skin, _ = fixture()
        bridge = core.create(surface)
        layer = bridge.layers().list()[0]
        count = bridge.data['topology']['nu']*bridge.data['topology']['nv']
        center = bridge.data['topology']['nv']+1
        state = core.layer_snapshot(bridge, layer.id)
        state['0'] = [0.0]*count
        state['0'][center] = 1.0
        state['1'] = [0.0]*count
        state['2'] = [1.0]*count
        state['2'][center] = 0.0
        core.apply_snapshot(bridge, layer.id, state)
        controller = brush.Controller(bridge, layer.id, 0, mode='Smooth', intensity=1)
        controller.apply({center:1})
        self.assertAlmostEqual(layer.get_weights(0)[center], 0, places=8)
        self.assertAlmostEqual(layer.get_weights(2)[center], 1, places=8)
        controller.cancel()

    def test_closed_seam_can_deform_without_becoming_a_topology_error(self):
        surface, skin, joints = fixture('closed_u')
        bridge = core.create(surface)
        self.assertEqual(bridge.data['topology']['fu'], 2)
        brush.Controller(bridge, bridge.layers().list()[0].id, 0, intensity=.5, value=.9).flood()
        cmds.setAttr(joints[2]+'.ty', 1)
        bridge.validate()
        self.assertEqual(bridge.data['topology']['fu'], 2)

    def test_tiny_weights_namespace_and_rename_survive(self):
        surface, skin, joints = fixture(sparse=True)
        cmds.setAttr(skin+'.weightList[0].weights[0]', 1e-12)
        cmds.setAttr(skin+'.weightList[0].weights[2]', 1-1e-12)
        before = core.sparse_weights(skin)
        bridge = core.create(surface)
        self.assertGreater(core.sparse_weights(skin)['0']['0'], 0)
        cmds.namespace(add='renamed')
        surface = cmds.rename(surface, 'renamed:surface')
        cmds.rename(joints[0], 'renamed:influence')
        cmds.rename(bridge.proxy_skin, 'renamed:proxySkin')
        bridge.validate()
        bridge.detach(restore=True)
        self.assertEqual(core.sparse_weights(skin), before)

    def test_bridge_created_inside_namespace_is_discoverable_from_root(self):
        cmds.namespace(add='character')
        cmds.namespace(set=':character')
        try:
            surface, skin, _ = fixture()
            bridge = core.create(surface)
        finally:
            cmds.namespace(set=':')
        found = core.find(surface)
        self.assertIsNotNone(found)
        self.assertEqual(found.identity, bridge.identity)
        found.validate()

    def test_dg_serial_parallel_and_baked_output_agree(self):
        surface, skin, joints = fixture('periodic_uv', method=2)
        original_mode = cmds.evaluationManager(query=True, mode=True)[0]
        try:
            cmds.evaluationManager(mode='off')
            reference = []
            for angle in (0, 27, -39, 12, 0):
                cmds.setAttr(joints[2]+'.rz', angle)
                reference.append(geometry(topology.surface_shape(surface)))
            bridge = core.create(surface)
            for mode in ('off', 'serial', 'parallel'):
                cmds.evaluationManager(mode=mode)
                for angle, expected in zip((0, 27, -39, 12, 0), reference):
                    cmds.setAttr(joints[2]+'.rz', angle)
                    self.assertLessEqual(maximum_error(expected, geometry(bridge.shape)), 1e-4)
            brush.Controller(bridge, bridge.layers().list()[0].id, 0, intensity=1, value=.4).flood()
            candidate = geometry(bridge.shape)
            bridge.detach()
            for mode in ('off', 'serial', 'parallel'):
                cmds.evaluationManager(mode=mode)
                self.assertLessEqual(maximum_error(candidate, geometry(topology.surface_shape(surface))), 1e-4)
        finally:
            cmds.evaluationManager(mode=original_mode)

    def test_smooth_sharpen_and_periodic_aliases(self):
        surface, skin, _ = fixture('periodic_uv')
        bridge = core.create(surface)
        data = bridge.data
        layer = bridge.layers().list()[0]
        graph = topology.neighbors(data['topology'], data['active'])
        nu = data['topology']['nu']-data['topology']['du']
        nv = data['topology']['nv']-data['topology']['dv']
        self.assertIn((nu-1)*data['topology']['nv'], graph[0])
        self.assertIn(nv-1, graph[0])
        # Closed endpoint CVs remain distinct in the graph.
        closed = dict(data['topology'], fu=2, fv=1, nu=4, nv=3, du=1, dv=1)
        self.assertIn(9, topology.neighbors(closed, list(range(12)))[0])
        for mode in ('Smooth', 'Sharpen', 'Add', 'Scale'):
            brush.Controller(bridge, layer.id, 0, mode=mode, intensity=.35).flood()
        values = layer.get_weights(0)
        for i, value in enumerate(values):
            self.assertAlmostEqual(value, values[topology.canonical(i, data['topology'])], places=8)
        self.assertTrue(all(0 <= v <= 1 for v in values))

    def test_exact_surface_hit_transform_and_dab_cancel(self):
        surface, skin, _ = fixture()
        cmds.setAttr('fixtureRoot.translate', 4, 3, -2, type='double3')
        cmds.setAttr('fixtureRoot.rotate', 17, -30, 11, type='double3')
        cmds.setAttr('fixtureRoot.scale', -1.5, 2.0, .6, type='double3')
        bridge = core.create(surface)
        fn = om.MFnNurbsSurface(topology.dag(bridge.shape))
        center = fn.getPointAtParam(.5, .5, om.MSpace.kWorld)
        normal = fn.normal(.5, .5, om.MSpace.kWorld)
        hit = topology.ray_hit(bridge.shape, center+normal*10, -normal)
        self.assertIsNotNone(hit)
        self.assertLessEqual((hit[0]-center).length(), 1e-5)
        self.assertIsNone(topology.ray_hit(bridge.shape, center+normal*10, normal))
        before = core.layer_snapshot(bridge, bridge.layers().list()[0].id)
        controller = brush.Controller(bridge, bridge.layers().list()[0].id, 0, radius=5, intensity=.7)
        self.assertTrue(controller.dab(center+normal*10, -normal))
        self.assertEqual(len(controller.display[0]), 625)
        controller.cancel()
        self.assertEqual(before, core.layer_snapshot(bridge, bridge.layers().list()[0].id))

    def test_bake_restore_reopen_and_owned_cleanup(self):
        surface, skin, _ = fixture('periodic_v', method=2, sparse=True)
        baseline = set(cmds.ls(uuid=True))
        bridge = core.create(surface)
        layer = bridge.layers().list()[0]
        brush.Controller(bridge, layer.id, 0, intensity=.8, value=.9).flood()
        brush.Controller(bridge, layer.id, 'dq', intensity=1, value=.4).flood()
        path = Path(tempfile.gettempdir())/'ng_nurbs_bridge_native_test.ma'
        cmds.file(rename=str(path)); cmds.file(save=True, type='mayaAscii')
        cmds.file(str(path), open=True, force=True, executeScriptNodes=False)
        bridge = core.find(surface)
        bridge.validate()
        before = geometry(bridge.shape)
        weights = core.sparse_weights(skin)
        bridge.detach()
        self.assertEqual(weights, core.sparse_weights(skin))
        self.assertLessEqual(maximum_error(before, geometry(topology.surface_shape(surface))), 1e-4)
        # Maya itself adds these standard state script nodes during save.
        self.assertLessEqual(set(cmds.ls(uuid=True))-baseline,
                             {'uiConfigurationScriptNode', 'sceneConfigurationScriptNode'})
        self.assertTrue(baseline.issubset(set(cmds.ls(uuid=True))))
        cmds.undo(); core.find(surface).validate()
        cmds.redo(); self.assertIsNone(core.find(surface))

    def test_validation_rejects_changes_and_preserves_existing_drivers(self):
        surface, skin, joints = fixture()
        source = cmds.createNode('addDoubleLinear')
        cmds.connectAttr(source+'.output', skin+'.weightList[0].weights[0]')
        baseline = set(cmds.ls(uuid=True))
        with self.assertRaisesRegex(ValueError, 'incoming'):
            core.create(surface)
        self.assertEqual(set(cmds.ls(uuid=True)), baseline)
        self.assertTrue(cmds.isConnected(source+'.output', skin+'.weightList[0].weights[0]'))
        cmds.undo()
        bridge = core.create(surface)
        cmds.skinCluster(skin, edit=True, addInfluence=cmds.createNode('joint'), weight=0)
        with self.assertRaisesRegex(ValueError, 'influences changed'):
            bridge.validate()

    def test_rational_degree_one_and_basis_partition(self):
        for degree in (1, 3):
            with self.subTest(degree=degree):
                cmds.file(new=True, force=True)
                surface, skin, _ = fixture(degree=degree, rational=True)
                before = geometry(topology.surface_shape(surface))
                bridge = core.create(surface)
                self.assertLessEqual(maximum_error(before, geometry(bridge.shape)), 1e-4)
                spec = bridge.data['topology']
                for t in (0, .01, .5, .99, 1):
                    self.assertAlmostEqual(sum(topology.basis(t, spec['nu'], spec['du'], spec['ku'])), 1, places=10)
                points, values, triangles = topology.surface_samples(bridge.shape, spec, [1]* (spec['nu']*spec['nv']))
                self.assertTrue(all(abs(v-1) < 1e-10 for v in values))


def run():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BridgeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return dict(tests=result.testsRun, failures=[str(t)+': '+text for t,text in result.failures],
                errors=[str(t)+': '+text for t,text in result.errors], success=result.wasSuccessful())


if __name__ == '__main__':
    os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    try:
        ng = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData'))/'Autodesk/ApplicationPlugins/ngskintools2/Contents'
        sys.path.insert(0, str(ng/'scripts'))
        cmds.loadPlugin(str(ng/'plug-ins'/cmds.about(version=True)/'ngSkinTools2.mll'), quiet=True)
        results = run()
        if len(sys.argv)>1:
            Path(sys.argv[1]).write_text(json.dumps(results, indent=2))
    finally:
        maya.standalone.uninitialize()
    sys.exit(0 if results['success'] else 1)
