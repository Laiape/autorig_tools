"""Real Maya / Qt regression. Run with mayapy; uses a disposable standalone scene."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ["MAYA_SKIP_USERSETUP_PY"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
# Standalone creates a QGuiApplication if one is absent; construct the widget
# application first so the native tool can be exercised in the same process.
from PySide6 import QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
import maya.standalone
maya.standalone.initialize(name="python")
from maya import cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.tools import model_checker_core as qc
from maya_tools.scripts.tools import model_checker as ui


class ModelCheckerTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)
        cmds.upAxis(axis="y")
        self.mesh = cmds.polyCube(name="body", constructionHistory=False)[0]

    def context(self, roots=None, **options):
        return qc.Context(roots, qc.Options(**options))

    def check(self, check_id, roots=None, **options):
        result = qc.run_check(self.context(roots, **options), check_id)
        self.assertNotEqual(result.status, "ERROR", result.message)
        return result

    def test_all_registered_checks_execute(self):
        context = self.context()
        selected = cmds.ls(selection=True, long=True)
        for check in qc.CHECKS:
            result = qc.run_check(context, check.id)
            self.assertNotEqual(result.status, "ERROR", (check.id, result.message))
        self.assertEqual(cmds.ls(selection=True, long=True), selected)

    def test_intermediate_shapes_excluded_and_empty_scope_rejected(self):
        shape = cmds.listRelatives(self.mesh, shapes=True, fullPath=True)[0]
        intermediate = cmds.createNode("mesh", parent=self.mesh)
        cmds.setAttr(intermediate + ".intermediateObject", True)
        self.assertEqual(self.context().meshes, [shape])
        self.assertFalse(self.check("multishapes").issues)
        with self.assertRaises(ValueError):
            self.context([])
        cmds.delete(self.mesh)
        with self.assertRaises(ValueError):
            self.context()

    def test_selection_pins_descendants_and_skips_scene_cleanup(self):
        root = cmds.group(self.mesh, name="asset")
        other = cmds.polyCube(name="other", constructionHistory=False)[0]
        context = self.context(["|asset"])
        self.assertEqual(len(context.meshes), 1)
        self.assertTrue(context.meshes[0].startswith("|asset|"))
        for key in ("unusedshaders", "unusedtex", "namespaces"):
            self.assertEqual(qc.run_check(context, key).status, "SKIP")
        cmds.select(other)
        self.assertEqual(qc.run_check(context, "ngons").status, "PASS")
        cmds.select(root + "|body.vtx[0]")
        self.assertTrue(qc.selection_roots())

    def test_ngons_and_duplicate_names_have_full_paths(self):
        cmds.group(self.mesh, name="assetA")
        ngon = cmds.polyCreateFacet(name="body", point=[(0, 0, 0), (2, 0, 0), (3, 1, 0), (1, 2, 0), (0, 1, 0)], constructionHistory=False)[0]
        cmds.group(ngon, name="assetB")
        cmds.rename("|assetB|" + ngon, "body")
        result = self.check("ngons", ["|assetB"])
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(result.issues[0].selection[0].startswith("|assetB|body|"))
        cmds.select(result.issues[0].selection)
        duplicates = self.check("dupenames", ["|assetB"])
        self.assertTrue(duplicates.issues)
        self.assertTrue(all(node.startswith("|assetB|") for issue in duplicates.issues for node in issue.selection))

    def test_nonmanifold_and_lamina_components(self):
        fn = om.MFnMesh()
        fn.create([om.MPoint(*p) for p in [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)]],
                  [3, 3, 3], [0, 1, 2, 1, 0, 3, 0, 1, 4])
        result = self.check("nonmanifold")
        self.assertTrue(result.issues)
        self.assertTrue(all(cmds.objExists(node) for issue in result.issues for node in issue.selection))
        fn = om.MFnMesh()
        fn.create([om.MPoint(*p) for p in [(0, 0, 0), (1, 0, 0), (0, 1, 0)]], [3, 3], [0, 1, 2, 0, 1, 2])
        self.assertTrue(self.check("lamina").issues)

    def test_symmetry_uses_positions_not_vertex_counts(self):
        self.assertEqual(self.check("t_symmetry").status, "PASS")
        cmds.move(0.2, 0, 0, self.mesh + ".vtx[0]", relative=True)
        self.assertEqual(self.check("t_symmetry").status, "WARN")
        cmds.move(5, 0, 0, self.mesh, relative=True)
        self.assertEqual(self.check("t_symmetry").status, "SKIP")

    def test_overlap_checks_adjacent_spatial_bins(self):
        cmds.xform(self.mesh + ".vtx[0]", objectSpace=True, translation=(0.000999, 0, 0))
        cmds.xform(self.mesh + ".vtx[1]", objectSpace=True, translation=(0.001001, 0, 0))
        result = self.check("overlap", tolerance=0.001)
        self.assertTrue(result.issues)
        self.assertTrue(any(node.endswith(".vtx[0]") for node in result.issues[0].selection))

    def test_sparse_mesh_tweaks_keep_real_vertex_indices(self):
        shape = cmds.listRelatives(self.mesh, shapes=True, fullPath=True)[0]
        cmds.setAttr(shape + ".pnts[7]", 0.1, 0, 0)
        result = self.check("tweaks")
        self.assertIn(shape + ".vtx[7]", result.issues[0].selection)

    def test_world_pivots_group_transforms_and_deep_parenting(self):
        root = cmds.group(self.mesh, name="asset")
        cmds.setAttr(root + ".tx", 4)
        self.assertTrue(any("asset" in issue.label for issue in self.check("frozen").issues))
        self.assertTrue(self.check("pivots").issues)
        parent_mesh = cmds.polyCube(name="parentMesh", constructionHistory=False)[0]
        cmds.parent(root, parent_mesh)
        self.assertTrue(any("body" in issue.label for issue in self.check("meshparent").issues))

    def test_ground_honors_maya_up_axis(self):
        cmds.upAxis(axis="z")
        cmds.setAttr(self.mesh + ".tz", 1)
        result = self.check("t_ground", ground_tolerance=0.01)
        self.assertIn("Z", result.issues[0].label)
        cmds.setAttr(self.mesh + ".tz", 0.5)
        self.assertEqual(self.check("t_ground", ground_tolerance=0.01).status, "PASS")

    def test_gpu_advisory_and_vertex_set_comparison(self):
        self.assertEqual(self.check("gpu").status, "INFO")
        self.assertEqual(self.check("gpu", gpu_min_vertices=5).status, "PASS")
        first = [self.mesh + ".vtx[0]", self.mesh + ".vtx[1]"]
        self.assertFalse(qc.compare_vertex_sets(first, first)["unmatched"])
        data = qc.compare_vertex_sets(first, [self.mesh + ".vtx[6]"])
        self.assertFalse(data["equal_count"])
        self.assertEqual(len(data["unmatched"]), 3)

    def test_repair_has_undo_and_protects_deformers_and_locks(self):
        cmds.setAttr(self.mesh + ".tx", 3)
        finding = self.check("frozen").issues[0]
        qc.repair("frozen", finding)
        self.assertEqual(cmds.getAttr(self.mesh + ".tx"), 0)
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.mesh + ".tx"), 3)
        cmds.lockNode(self.mesh, lock=True)
        with self.assertRaises(ValueError):
            qc.repair("frozen", finding)
        cmds.lockNode(self.mesh, lock=False)
        joint = cmds.createNode("joint")
        skin = cmds.skinCluster(joint, self.mesh, toSelectedBones=True)[0]
        with self.assertRaisesRegex(ValueError, "deformers"):
            qc.repair("history", qc.Issue("skin", [self.mesh]))
        self.assertTrue(cmds.objExists(skin))
        group = cmds.group(self.mesh, name="skinnedGroup")
        cmds.setAttr(group + ".tx", 2)
        with self.assertRaisesRegex(ValueError, "deformers"):
            qc.repair("frozen", qc.Issue("skinned hierarchy", [group]))

    def test_zero_area_and_complete_report_findings(self):
        cmds.scale(0, 0, 0, self.mesh)
        self.assertTrue(self.check("zeroarea").issues)
        for index in range(20):
            cmds.createNode("transform", name="empty{}".format(index))
        result = self.check("emptygroups")
        self.assertEqual(len(result.issues), 20)
        report = qc.build_report({"emptygroups": result}, {}, None, qc.Options())
        text = qc.report_text(report)
        self.assertTrue(all(issue.selection[0] in text for issue in result.issues))

    def test_repair_revalidates_connections_and_preserves_history_shape(self):
        cube = cmds.polyCube(name="withHistory")[0]
        before = cmds.xform(cube + ".vtx[*]", query=True, worldSpace=True, translation=True)
        qc.repair("history", qc.Issue("history", [cube]))
        self.assertEqual(before, cmds.xform(cube + ".vtx[*]", query=True, worldSpace=True, translation=True))
        self.assertFalse(qc.history(cmds.listRelatives(cube, shapes=True)[0]))
        texture = cmds.shadingNode("file", asTexture=True)
        finding = qc.Issue("unused texture", [texture])
        shader = cmds.shadingNode("lambert", asShader=True)
        cmds.connectAttr(texture + ".outColor", shader + ".color")
        with self.assertRaisesRegex(ValueError, "connected"):
            qc.repair("unusedtex", finding)
        self.assertTrue(cmds.objExists(texture))

    def test_errors_pending_skips_and_exceptions_never_pass(self):
        results = {check.id: qc.Result(check.id, "PASS") for check in qc.CHECKS}
        manual = {row[0]: {"state": "Pass", "note": ""} for row in qc.MANUAL_CHECKS}
        self.assertEqual(qc.build_report(results, manual, None, qc.Options())["verdict"], "PASS")
        self.assertEqual(qc.build_report(results, {}, None, qc.Options())["verdict"], "INCOMPLETE")
        with mock.patch.object(qc, "inspect_check", side_effect=RuntimeError("fixture error")):
            results["ngons"] = qc.run_check(self.context(), "ngons")
        self.assertEqual(results["ngons"].status, "ERROR")
        self.assertEqual(qc.build_report(results, manual, None, qc.Options())["verdict"], "INCOMPLETE")
        results["ngons"] = qc.Result("ngons", "SKIP")
        self.assertEqual(qc.build_report(results, manual, None, qc.Options())["verdict"], "INCOMPLETE")
        results["ngons"] = qc.Result("ngons", "PASS")
        manual["sole_topo"] = dict(state="N/A", note="")
        self.assertEqual(qc.build_report(results, manual, None, qc.Options())["verdict"], "INCOMPLETE")
        manual["sole_topo"]["note"] = "No shoes in this asset"
        self.assertEqual(qc.build_report(results, manual, None, qc.Options())["verdict"], "PASS")

    def test_ui_scan_review_roundtrip_filter_and_stale(self):
        import faulthandler
        faulthandler.dump_traceback_later(25)
        app = ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
        parent = ui.QtWidgets.QWidget()
        window = ui.ModelCheckerWindow(parent)
        try:
            window.show(); app.processEvents(); window.run_all()
            self.assertEqual(len(window.results), len(qc.CHECKS))
            self.assertFalse([r.message for r in window.results.values() if r.status == "ERROR"])
            self.assertFalse(window.stale)
            self.assertEqual(window.run_btn.property("arActionRole"), "primary")
            self.assertFalse(window.run_btn.icon().isNull())
            self.assertFalse(window.query.styleSheet())
            state, note = window._review_widgets["sole_topo"]
            state.setCurrentText("N/A"); note.setText("No shoes in fixture")
            with tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "review.json")
                window.save_report(path)
                window._reset_review(); window.load_review(path)
                self.assertEqual(state.currentText(), "N/A")
                self.assertEqual(note.text(), "No shoes in fixture")
                self.assertEqual(len(json.loads(Path(path).read_text())["automatic"]), len(qc.CHECKS))
            window.query.setText("non-manifold")
            self.assertFalse(window._check_items["nonmanifold"].isHidden())
            self.assertTrue(window._check_items["gpu"].isHidden())
            cmds.setAttr(self.mesh + ".tx", 3); app.processEvents()
            self.assertTrue(window.stale)
            self.assertEqual(window.report()["verdict"], "STALE")
            window.query.clear()
            window.run_all()
            window._check_items["frozen"].setSelected(True)
            item = window.issue_tree.topLevelItem(0)
            self.assertIsNotNone(item)
            item.setSelected(True)
            self.assertTrue(window.fix_btn.isEnabled())
            window._repair()
            self.assertEqual(cmds.getAttr(self.mesh + ".tx"), 0)
            self.assertFalse(window.stale)
            # A failed check remains a diagnostic; the UI never hides it as a pass.
            window.check_tree.clearSelection()
            with mock.patch.object(qc, "inspect_check", side_effect=RuntimeError("UI fixture")):
                window._run(["ngons"])
            self.assertEqual(window._check_items["ngons"].text(2), "ERROR")
            self.assertIn("UI fixture", window.issue_tree.topLevelItem(0).text(0))
            window._check_items["frozen"].setSelected(False)
            window.check_tree.clearSelection()
            QtCore = ui.QtCore
            QtCore.QTimer.singleShot(0, window._cancel)
            window.run_all()
            self.assertLess(len(window.results), len(qc.CHECKS))
            self.assertEqual(window.report()["verdict"], "INCOMPLETE")
            window.resize(640, 520); app.processEvents()
            screenshot = os.environ.get("MODEL_CHECKER_SCREENSHOT")
            if screenshot:
                window.query.clear(); window.resize(920, 760); app.processEvents()
                window.grab().save(screenshot)
        finally:
            window.close(); window.deleteLater(); app.processEvents(); parent.deleteLater()
        self.assertFalse(window._callbacks)
        self.assertFalse(window._watchers)
        faulthandler.cancel_dump_traceback_later()

    def test_show_after_module_reload_releases_old_callbacks(self):
        from importlib import reload
        first = ui.show()
        try:
            self.assertTrue(first._callbacks)
            reload(ui)
            second = ui.show()
            self.assertFalse(first._callbacks)
            self.assertIsNot(second, first)
            second.close(); second.deleteLater()
        finally:
            first.close(); first.deleteLater()

    def test_review_rejects_a_different_untitled_scene(self):
        parent = ui.QtWidgets.QWidget()
        window = ui.ModelCheckerWindow(parent)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "review.json")
                window.save_report(path)
                cmds.file(new=True, force=True)
                cmds.polyCube(name="body", constructionHistory=False)
                with self.assertRaisesRegex(ValueError, "another scene"):
                    window.load_review(path)
        finally:
            window.close(); window.deleteLater(); parent.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
