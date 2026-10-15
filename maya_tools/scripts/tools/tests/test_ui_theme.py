"""Real native Qt hierarchy, dynamic controls and editor coverage; run in mayapy."""
import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ["MAYA_SKIP_USERSETUP_PY"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / "maya_tools" / "scripts")]
from PySide6 import QtCore, QtGui, QtWidgets, QtTest
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
QtGui.QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
APP.setFont(QtGui.QFont("Arial", 9))
import maya.standalone
maya.standalone.initialize(name="python")
from maya import cmds
from maya_tools.scripts.utils import ui_utils


class ThemeTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        self.windows = []

    def tearDown(self):
        for window in reversed(self.windows):
            window.close(); window.deleteLater()
        APP.processEvents()

    def own(self, window):
        self.windows.append(window)
        return window

    def test_primary_fill_is_visible_and_disabled_state_keeps_behavior(self):
        window = self.own(QtWidgets.QWidget())
        box = QtWidgets.QVBoxLayout(window)
        main = QtWidgets.QPushButton("Run"); box.addWidget(main)
        secondary = QtWidgets.QPushButton("Browse"); box.addWidget(secondary)
        field = QtWidgets.QLineEdit("Native field"); box.addWidget(field)
        ui_utils.action(main, "primary", "model")
        ui_utils.apply_maya_style(window)
        window.show(); APP.processEvents()
        main_image = main.grab().toImage()
        plain_image = secondary.grab().toImage()
        self.assertNotEqual(main_image.pixelColor(4, 4), plain_image.pixelColor(4, 4))
        self.assertFalse(field.styleSheet())
        self.assertEqual(field.palette().color(QtGui.QPalette.Base), APP.palette().color(QtGui.QPalette.Base))
        clicks = QtTest.QSignalSpy(main.clicked)
        QtTest.QTest.mouseClick(main, QtCore.Qt.LeftButton)
        self.assertEqual(clicks.count(), 1)
        main.setEnabled(False)
        ui_utils.apply_maya_style(window)
        self.assertFalse(main.isEnabled())
        QtTest.QTest.mouseClick(main, QtCore.Qt.LeftButton)
        self.assertEqual(clicks.count(), 1)

    def test_vendor_subtree_and_functional_swatch_survive_reapplication(self):
        window = self.own(QtWidgets.QWidget()); box = QtWidgets.QVBoxLayout(window)
        vendor = QtWidgets.QWidget(); vendor_box = QtWidgets.QVBoxLayout(vendor)
        field = QtWidgets.QSlider(); field.setValue(32); vendor_box.addWidget(field)
        vendor.setStyleSheet("QSlider {background:#694899;}")
        ui_utils.preserve_style(vendor, subtree=True); box.addWidget(vendor)
        swatch = QtWidgets.QPushButton(); swatch.setStyleSheet("background:#ff7a00;")
        ui_utils.preserve_style(swatch); box.addWidget(swatch)
        for _ in range(3):
            ui_utils.apply_maya_style(window)
        self.assertIn("#694899", vendor.styleSheet())
        self.assertEqual(field.value(), 32)
        self.assertIn("#ff7a00", swatch.styleSheet())

    def test_actual_editors_have_primary_actions_and_native_inputs(self):
        from maya_tools.scripts.tools import model_checker, curve_library, rig_tools
        from maya_tools.scripts.ui import (tool_framework_UI, corrective_curve_UI,
            deboor_tools_UI, joint_correctives_UI, pose_blendshapes_UI, pose_tester_UI,
            proximity_bake_UI, rig_package_UI, skin_transfer_UI, wrinkle_regions_UI)
        factories = (
            (model_checker.ModelCheckerWindow, "Run all checks"),
            (tool_framework_UI.ToolFramework, "Open tool"),
            (corrective_curve_UI.CorrectiveCurveUI, "Create / Add pose"),
            (deboor_tools_UI.DeBoorToolsUI, "Create De Boor Ribbon"),
            (joint_correctives_UI.JointCorrectivesUI, "Create region"),
            (pose_blendshapes_UI.PoseBlendshapesUI, "Add"),
            (pose_tester_UI.PoseTesterUI, "Full Body ROM"),
            (proximity_bake_UI.DeformationBakeUI, "Bake selection to Skin"),
            (rig_package_UI.RigPackageUI, "Validate candidate in isolated Maya"),
            (skin_transfer_UI.SkinTransferUI, "TRANSFER SKINNING"),
            (wrinkle_regions_UI.WrinkleRegionsUI, "Assign selected vertices"),
            (rig_tools.RigToolsUI, "TRACE ARC"),
            (curve_library.CurveLibraryUI, "APPLY TO SELECTED"),
        )
        screenshot_dir = os.environ.get("AUTORIG_UI_SCREENSHOTS")
        parent = self.own(QtWidgets.QWidget())
        for factory, label in factories:
            with self.subTest(editor=factory.__name__):
                window = self.own(factory(parent=parent))
                matches = [button for button in window.findChildren(QtWidgets.QPushButton)
                           if ui_utils.key(button.text()) == ui_utils.key(label)]
                self.assertTrue(matches, label)
                self.assertEqual(matches[0].property("arActionRole"), "primary")
                self.assertFalse(matches[0].icon().isNull())
                self.assertFalse(window.windowIcon().isNull())
                for field in window.findChildren(QtWidgets.QLineEdit):
                    self.assertFalse(field.styleSheet())
                before = len(window.findChildren(QtWidgets.QWidget, "arToolHeader"))
                for _ in range(2):
                    ui_utils.apply_maya_style(window)
                self.assertEqual(before, len(window.findChildren(QtWidgets.QWidget, "arToolHeader")))
                if screenshot_dir:
                    window.show(); APP.processEvents()
                    window.grab().save(str(Path(screenshot_dir) / (factory.__name__ + ".png")))
                window.hide()

    def test_character_manager_dynamic_version_actions_and_curve_tabs(self):
        from maya_tools.scripts.utils import character_manager
        from maya_tools.scripts.tools import curve_library
        with tempfile.TemporaryDirectory() as directory:
            parent = self.own(QtWidgets.QWidget())
            with mock.patch.object(character_manager, "get_assets_path", return_value=directory), mock.patch.object(character_manager.AssetManagerUI, "_restore_session"):
                manager = self.own(character_manager.AssetManagerUI(parent=parent))
            version = character_manager.VersionTab(directory, "models")
            manager.tabs.addTab(version, "Models")
            ui_utils.apply_maya_style(manager)
            self.assertEqual(manager.btn_build.property("arActionRole"), "primary")
            self.assertEqual(version.btn_save.property("arActionRole"), "success")
            self.assertEqual(version.btn_qc_run.property("arActionRole"), "primary")
            self.assertFalse(version.btn_save.icon().isNull())
        library = self.own(curve_library.CurveLibraryUI(parent=parent))
        color = library.color_btn.styleSheet()
        library._switch_tab(False)
        ui_utils.apply_maya_style(library)
        self.assertTrue(library.tab_library.isChecked())
        self.assertFalse(library.tab_builtin.isChecked())
        self.assertEqual(library.color_btn.styleSheet(), color)

    def test_late_loaded_loop_panel_and_action_semantics(self):
        from maya_tools.scripts.ui import facial_loop_skinning_UI
        owner = QtWidgets.QWidget(); owner.owner = owner
        owner.run_action = lambda callback: callback()
        self.own(owner)
        panel = facial_loop_skinning_UI.LoopRiggerPanel(owner)
        self.assertEqual(panel.create.property("arActionRole"), "primary")
        self.assertFalse(panel.create.icon().isNull())
        self.assertEqual(ui_utils.key("Mirror L -> R"), ui_utils.key("Mirror L / R"))

    def test_generated_picker_uses_theme_and_stays_portable(self):
        from maya_tools.scripts.tools import character_picker_runtime as runtime
        import builtins
        parent = self.own(QtWidgets.QWidget())
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "picker_config.json").write_text(json.dumps(dict(character="ThemeTest", panels=[])))
            (folder / "picker.json").write_text(json.dumps(dict(shapes=[])))
            with mock.patch.object(runtime, "ROOT", folder):
                picker = self.own(runtime.CharacterPicker(parent=parent))
                main = next(button for button in picker.findChildren(QtWidgets.QPushButton) if button.text() == "Use Selection")
                self.assertEqual(main.property("arActionRole"), "primary")
                original_import = builtins.__import__
                def portable_import(name, *args, **kwargs):
                    if name == "maya_tools.scripts.utils":
                        raise ImportError("Portable installation without AutoRig")
                    return original_import(name, *args, **kwargs)
                with mock.patch("builtins.__import__", portable_import):
                    portable = self.own(runtime.CharacterPicker(parent=parent))
                portable_main = next(button for button in portable.findChildren(QtWidgets.QPushButton) if button.text() == "Use Selection")
                self.assertIn("#356581", portable_main.styleSheet())
                self.assertFalse(portable.namespace.styleSheet())

    def test_skinning_manager_and_its_embedded_editors_stay_native(self):
        class SkinningManager(QtWidgets.QWidget):
            pass
        manager = self.own(SkinningManager())
        layout = QtWidgets.QVBoxLayout(manager)
        tabs = QtWidgets.QTabWidget(); layout.addWidget(tabs)
        content = QtWidgets.QWidget(); tabs.addTab(content, ui_utils.icon("skin"), "Skinning")
        box = QtWidgets.QVBoxLayout(content)
        button = QtWidgets.QPushButton("Apply"); box.addWidget(button)
        # Simulate a previously accented editor. Restore the existing widget,
        # including vendor controls, without replacing its runtime state.
        button.setProperty("arActionRole", "success")
        vendor = QtWidgets.QWidget(); vendor.setStyleSheet("background:#484848;")
        vendor_box = QtWidgets.QVBoxLayout(vendor)
        field = QtWidgets.QSlider(); field.setValue(37); vendor_box.addWidget(field)
        ui_utils.preserve_style(vendor, subtree=True); box.addWidget(vendor)
        ui_utils.apply_maya_style(manager)
        ui_utils.action(button, "primary", "skin")
        ui_utils.apply_maya_style(content)
        self.assertFalse(manager.styleSheet())
        self.assertIsNone(button.property("arActionRole"))
        self.assertTrue(tabs.tabIcon(0).isNull())
        self.assertEqual(field.value(), 37)
        self.assertIn("#484848", vendor.styleSheet())


if __name__ == "__main__":
    unittest.main(verbosity=2)
