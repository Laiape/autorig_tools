"""Integration tests: run with Maya's mayapy (no interactive scene required)."""
import importlib.util
import json
import os
import tempfile
import unittest

os.environ["MAYA_SKIP_USERSETUP_PY"] = "1"
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

spec = importlib.util.spec_from_file_location(
    "skin_manager_api", os.path.join(os.path.dirname(__file__), "..", "skin_manager_api.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SkinSurfaceImportTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "weights.skc")
        self.manager = module.SkinManager.__new__(module.SkinManager)
        self.manager.k_skin_attrs = ["skinningMethod", "normalizeWeights",
                                     "maintainMaxInfluences", "maxInfluences", "weightDistribution"]
        self.manager.tolerance = 1e-5
        self.create_joints()
        self.create_mesh([(0, 0, 0), (2, 0, 0), (0, 2, 0)], [3], [0, 1, 2])
        skin = cmds.skinCluster(["left", "right"], "body", name="bodySkin",
                                toSelectedBones=True)[0]
        skin_fn = self.skin_fn(skin)
        path = self.manager._get_dag_path("bodyShape")
        comp = self.component(3)
        skin_fn.setWeights(path, comp, om.MIntArray([0, 1]),
                           om.MDoubleArray([1, 0, 0, 1, 0, 1]), False)
        skin_fn.setBlendWeights(path, comp, om.MDoubleArray([0, 0.4, 0.8]))
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def create_joints():
        for name in ("left", "right"):
            cmds.select(clear=True)
            cmds.joint(name=name)

    @staticmethod
    def create_mesh(points, counts, connects):
        transform = om.MFnMesh().create([om.MPoint(*p) for p in points], counts, connects)
        name = cmds.rename(om.MFnDagNode(transform).fullPathName(), "body")
        cmds.rename(cmds.listRelatives(name, shapes=True)[0], "bodyShape")

    @staticmethod
    def component(count):
        fn = om.MFnSingleIndexedComponent()
        comp = fn.create(om.MFn.kMeshVertComponent)
        fn.setCompleteData(count)
        return comp

    @staticmethod
    def skin_fn(name="bodySkin"):
        sel = om.MSelectionList()
        sel.add(name)
        return oma.MFnSkinCluster(sel.getDependNode(0))

    def replace_mesh(self, changed=True):
        cmds.file(new=True, force=True)
        self.create_joints()
        points = [(0, 0, 0), (2, 0, 0), (0, 2, 0)]
        if changed:
            points.append((0.5, 0.5, 0.2))
            self.create_mesh(points, [3, 3, 3], [0, 1, 3, 1, 2, 3, 2, 0, 3])
        else:
            self.create_mesh(points, [3], [0, 1, 2])

    def weights(self):
        path = self.manager._get_dag_path("bodyShape")
        fn = self.skin_fn()
        count = om.MFnMesh(path).numVertices
        weights, stride = fn.getWeights(path, self.component(count))
        blend = fn.getBlendWeights(path, self.component(count))
        return list(weights), stride, list(blend)

    def test_auto_projects_weights_and_blend_on_changed_mesh(self):
        self.replace_mesh()
        self.manager.import_skins(in_path=self.path)
        weights, stride, blend = self.weights()
        self.assertEqual(stride, 2)
        self.assertAlmostEqual(weights[6], 0.5)
        self.assertAlmostEqual(weights[7], 0.5)
        self.assertAlmostEqual(blend[3], 0.3)
        self.assertEqual(weights[:6], [1, 0, 0, 1, 0, 1])

    def test_identical_topology_keeps_index_weights(self):
        self.replace_mesh(changed=False)
        # Same connectivity with moved vertices still supports exact index import.
        cmds.move(0.5, 0.5, 0.2, "body.vtx[0]", absolute=True, objectSpace=True)
        self.manager.import_skins(in_path=self.path)
        self.assertEqual(self.weights()[0], [1, 0, 0, 1, 0, 1])

    def test_forced_projection_with_same_vertex_count(self):
        self.replace_mesh(changed=False)
        cmds.move(0.5, 0.5, 0.2, "body.vtx[0]", absolute=True, objectSpace=True)
        self.manager.import_skins(in_path=self.path, import_method="closestPoint")
        self.assertAlmostEqual(self.weights()[0][0], 0.5)

    def test_auto_detects_changed_connectivity_with_same_vertex_count(self):
        self.replace_mesh(changed=False)
        cmds.delete("body")
        self.create_mesh([(0.5, 0.5, 0.2), (2, 0, 0), (0, 2, 0)], [3], [0, 2, 1])
        self.manager.import_skins(in_path=self.path)
        self.assertAlmostEqual(self.weights()[0][0], 0.5)

    def test_index_rejects_changed_mesh_without_creating_skin(self):
        self.replace_mesh()
        self.manager.import_skins(in_path=self.path, import_method="index")
        self.assertFalse(cmds.objExists("bodySkin"))

    def test_legacy_files_keep_index_import_and_skip_changed_mesh(self):
        with open(self.path) as stream:
            data = json.load(stream)
        del data["bodyShape"][0]["geometry"]
        with open(self.path, "w") as stream:
            json.dump(data, stream)
        self.replace_mesh(changed=False)
        self.manager.import_skins(in_path=self.path)
        self.assertEqual(self.weights()[0], [1, 0, 0, 1, 0, 1])
        self.replace_mesh()
        self.manager.import_skins(in_path=self.path)
        self.assertFalse(cmds.objExists("bodySkin"))

    def test_replace_existing_projects_and_default_skips(self):
        self.replace_mesh()
        cmds.skinCluster(["left", "right"], "body", name="bodySkin", toSelectedBones=True)
        before = self.weights()[0]
        self.manager.import_skins(in_path=self.path)
        self.assertEqual(self.weights()[0], before)
        self.manager.import_skins(in_path=self.path, replace_existing=True)
        self.assertAlmostEqual(self.weights()[0][6], 0.5)
        self.assertAlmostEqual(self.weights()[2][3], 0.3)

    def test_stacked_skins_share_surface_mapping_and_preserve_corrective(self):
        with open(self.path) as stream:
            data = json.load(stream)
        second = dict(data["bodyShape"][0])
        second.pop("geometry")
        second["name"] = "secondSkin"
        second["sparse_weights"] = {
            "left": {"ix": [1, 2], "vw": [1, 1]},
            "right": {"ix": [0], "vw": [1]},
        }
        data["bodyShape"].append(second)
        with open(self.path, "w") as stream:
            json.dump(data, stream)
        self.replace_mesh()
        cmds.skinCluster(["left", "right"], "body", name="correctiveSkin",
                         toSelectedBones=True)
        path = self.manager._get_dag_path("bodyShape")
        comp = self.component(4)
        corrective_before = list(self.skin_fn("correctiveSkin").getWeights(path, comp)[0])
        self.manager.import_skins(in_path=self.path)
        first = list(self.skin_fn().getWeights(path, comp)[0])
        second = list(self.skin_fn("secondSkin").getWeights(path, comp)[0])
        self.assertEqual(second[:6], [0, 1, 1, 0, 1, 0])
        self.assertAlmostEqual(first[6], 0.5)
        self.assertAlmostEqual(second[6], 0.5)
        self.assertEqual(list(self.skin_fn("correctiveSkin").getWeights(path, comp)[0]),
                         corrective_before)
        self.assertEqual(self.manager._get_skin_clusters(path),
                         ["bodySkin", "secondSkin", "correctiveSkin"])

    def test_export_includes_unselected_deformers_and_sparse_weights(self):
        other = cmds.polyPlane(name="unselected", subdivisionsX=1, subdivisionsY=1)[0]
        cluster, handle = cmds.cluster(other, name="unselectedCluster")
        cmds.setAttr(cluster + ".envelope", 0.35)
        cmds.percent(cluster, other + ".vtx[0]", value=0.2)
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)
        with open(self.path) as stream:
            data = json.load(stream)
        snapshot = data[module.SkinManager.SCENE_DEFORMERS_KEY]
        nodes = {entry["name"]: entry for entry in snapshot["nodes"]}
        self.assertEqual(nodes[cluster]["type"], "cluster")
        self.assertAlmostEqual(nodes[cluster]["attributes"]["envelope"]["value"], 0.35)
        self.assertAlmostEqual(
            nodes[cluster]["attributes"]["weightList[0].weights[0]"]["value"], 0.2)
        self.assertTrue(nodes[cluster]["geometries"])
        self.assertIn(nodes[cluster]["membership_mode"], ("component_tags", "object_set"))
        if nodes[cluster]["membership_mode"] == "object_set":
            self.assertTrue(nodes[cluster]["members"])
        self.assertIn("bodySkin", nodes)
        self.assertIn("bodyShape", data)
        # Metadata must not be interpreted as a mesh by the skin importer.
        self.replace_mesh(changed=False)
        self.manager.import_skins(in_path=self.path)
        self.assertEqual(self.weights()[0], [1, 0, 0, 1, 0, 1])

    def test_export_proximity_wrap_settings_multiple_drivers_and_stack(self):
        belt = cmds.polyPlane(name="belt", subdivisionsX=1, subdivisionsY=1)[0]
        other = cmds.polyPlane(name="driverTwo", subdivisionsX=1, subdivisionsY=1)[0]
        wrap = cmds.deformer(belt, type="proximityWrap", name="belt_PRX")[0]
        cmds.setAttr(wrap + ".smoothInfluences", 20)
        cmds.setAttr(wrap + ".smoothNormals", 5)
        driver_shapes = [cmds.listRelatives(node, shapes=True, noIntermediate=True)[0]
                         for node in ("body", other)]
        cmds.proximityWrap(wrap, edit=True, addDrivers=driver_shapes, applyUserDefaults=False)
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)
        with open(self.path) as stream:
            snapshot = json.load(stream)[module.SkinManager.SCENE_DEFORMERS_KEY]
        entry = next(node for node in snapshot["nodes"] if node["name"] == wrap)
        self.assertEqual(entry["attributes"]["smoothInfluences"]["value"], 20)
        self.assertEqual(entry["attributes"]["smoothNormals"]["value"], 5)
        connections = [item for item in entry["connections"]
                       if item["destination"].endswith(".driverGeometry")]
        self.assertEqual(len(connections), 2)
        belt_shape = cmds.ls(cmds.listRelatives(belt, shapes=True,
                                               noIntermediate=True)[0], long=True)[0]
        self.assertEqual(snapshot["geometry_stacks"][belt_shape], [wrap])

    def test_export_deformer_only_scene_without_skin(self):
        cmds.file(new=True, force=True)
        mesh = cmds.polyPlane(name="cloth")[0]
        bend, handle = cmds.nonLinear(mesh, type="bend")
        cmds.setAttr(bend + ".curvature", 0.5)
        cmds.select(clear=True)
        self.manager.export_skins(in_path=self.path)
        with open(self.path) as stream:
            data = json.load(stream)
        self.assertEqual(list(data), [module.SkinManager.SCENE_DEFORMERS_KEY])
        entry = data[module.SkinManager.SCENE_DEFORMERS_KEY]["nodes"][0]
        self.assertEqual(entry["name"], bend)
        self.assertEqual(entry["type"], "nonLinear")
        auxiliary = data[module.SkinManager.SCENE_DEFORMERS_KEY]["auxiliary_nodes"]
        handle_shape = next(node for node in auxiliary if node["type"] == "deformBend")
        self.assertAlmostEqual(handle_shape["attributes"]["curvature"]["value"], 0.5)

    def test_import_wrap_roundtrip_multiple_drivers_renamed_shape_and_no_duplicates(self):
        belt = cmds.polyPlane(name="belt", subdivisionsX=1, subdivisionsY=1)[0]
        driver = cmds.polyPlane(name="driverTwo", subdivisionsX=1, subdivisionsY=1)[0]
        wrap = cmds.deformer(belt, type="proximityWrap", name="belt_PRX")[0]
        cmds.setAttr(wrap + ".smoothInfluences", 20)
        cmds.setAttr(wrap + ".smoothNormals", 5)
        shapes = [cmds.listRelatives(node, shapes=True, noIntermediate=True)[0]
                  for node in ("body", driver)]
        cmds.proximityWrap(wrap, edit=True, addDrivers=shapes, applyUserDefaults=False)
        output = cmds.listRelatives(belt, shapes=True, noIntermediate=True)[0]
        cmds.rename(output, "beltShapeDeformed")
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)
        cmds.move(0.4, 0.8, 0, "left", "right", relative=True)
        cmds.move(0, 0.6, 0, driver + ".vtx[*]", relative=True)
        expected = cmds.xform(belt + ".vtx[*]", query=True, worldSpace=True, translation=True)
        cmds.move(-0.4, -0.8, 0, "left", "right", relative=True)
        cmds.move(0, -0.6, 0, driver + ".vtx[*]", relative=True)
        cmds.delete(wrap)
        output = cmds.listRelatives(belt, shapes=True, noIntermediate=True)[0]
        cmds.rename(output, "beltShape")
        self.manager.import_skins(in_path=self.path)
        self.assertTrue(cmds.objExists(wrap))
        self.assertEqual(cmds.proximityWrap(wrap, query=True, driverIndices=True), [0, 1])
        self.assertEqual(cmds.getAttr(wrap + ".smoothInfluences"), 20)
        self.assertEqual(cmds.getAttr(wrap + ".smoothNormals"), 5)
        cmds.move(0.4, 0.8, 0, "left", "right", relative=True)
        cmds.move(0, 0.6, 0, driver + ".vtx[*]", relative=True)
        actual = cmds.xform(belt + ".vtx[*]", query=True, worldSpace=True, translation=True)
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=5)
        self.manager.import_skins(in_path=self.path)
        self.assertEqual(cmds.ls(type="proximityWrap"), [wrap])

    def test_import_wrap_missing_driver_does_not_create_broken_filter(self):
        belt = cmds.polyPlane(name="belt")[0]
        driver = cmds.polyPlane(name="driverTwo")[0]
        wrap = cmds.deformer(belt, type="proximityWrap", name="belt_PRX")[0]
        shape = cmds.listRelatives(driver, shapes=True)[0]
        cmds.proximityWrap(wrap, edit=True, addDrivers=[shape], applyUserDefaults=False)
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)
        cmds.delete(wrap, driver)
        self.manager.import_skins(in_path=self.path)
        self.assertFalse(cmds.objExists(wrap))

    def test_import_cluster_weights_and_bend_handle(self):
        mesh = cmds.polyPlane(name="cloth", subdivisionsX=1, subdivisionsY=1)[0]
        cluster, handle = cmds.cluster(mesh, name="clothCluster")
        cmds.percent(cluster, mesh + ".vtx[0]", value=0.2)
        cmds.move(0, 0.7, 0, handle, relative=True)
        bend, bend_handle = cmds.nonLinear(mesh, type="bend")
        cmds.setAttr(bend + ".curvature", 0.5)
        expected = cmds.xform(mesh + ".vtx[*]", query=True, worldSpace=True, translation=True)
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)
        cmds.delete(cluster, bend, handle, bend_handle)
        self.manager.import_skins(in_path=self.path)
        self.assertTrue(cmds.objExists(cluster))
        self.assertTrue(cmds.objExists(bend))
        self.assertAlmostEqual(cmds.percent(cluster, mesh + ".vtx[0]", query=True, value=True)[0], 0.2)
        self.assertAlmostEqual(cmds.getAttr(bend + ".curvature"), 0.5)
        actual = cmds.xform(mesh + ".vtx[*]", query=True, worldSpace=True, translation=True)
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=5)

    def test_import_baked_blendshape_delta_and_alias(self):
        mesh = cmds.polyPlane(name="cloth", subdivisionsX=1, subdivisionsY=1)[0]
        target = cmds.duplicate(mesh, name="raisedTarget")[0]
        cmds.move(0, 1, 0, target + ".vtx[0]", relative=True)
        blend = cmds.blendShape(target, mesh, name="clothBlend")[0]
        cmds.delete(target)
        cmds.setAttr(blend + ".weight[0]", 0.6)
        expected = cmds.xform(mesh + ".vtx[*]", query=True, worldSpace=True, translation=True)
        cmds.select("body")
        self.manager.export_skins(in_path=self.path)
        cmds.delete(blend)
        self.manager.import_skins(in_path=self.path)
        self.assertEqual(cmds.aliasAttr(blend, query=True), ["raisedTarget", "weight[0]"])
        actual = cmds.xform(mesh + ".vtx[*]", query=True, worldSpace=True, translation=True)
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=5)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        maya.standalone.uninitialize()
