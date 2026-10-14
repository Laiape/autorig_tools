"""Real Qt interaction checks with a simulated Maya scene (Maya not required).

Run with a Python environment containing PySide6. This is not Maya runtime QA.
"""
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtWidgets, QtTest

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT/"maya_tools/assets/Edward/picker/reference_workflow"
NAMES = {c["name"] for c in json.loads((BUNDLE/"controls_manifest.json").read_text())}


class Scene:
    def __init__(self):
        self.nodes = {"|Edward|controls|edward:"+name for name in NAMES}
        self.selection, self.jobs, self.warnings = set(), {}, []
        self.counter = 0

    def ls(self, *args, **kwargs):
        if kwargs.get("selection"):
            return list(self.selection)
        patterns = args[0] if len(args)==1 and isinstance(args[0],list) else args
        return [n for n in self.nodes if any(fnmatch.fnmatchcase(n.rsplit("|",1)[-1],p) for p in patterns)]

    def select(self, nodes, **kwargs):
        if kwargs.get("toggle"):
            self.selection.symmetric_difference_update(nodes)
        elif kwargs.get("add"):
            self.selection.update(nodes)
        else:
            self.selection = set(nodes)

    def scriptJob(self, **kwargs):
        if "exists" in kwargs:
            return kwargs["exists"] in self.jobs
        if "kill" in kwargs:
            self.jobs.pop(kwargs["kill"],None)
            return
        self.counter += 1
        self.jobs[self.counter] = kwargs["event"]
        return self.counter


class PickerInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        font_file = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts/arial.ttf"
        if font_file.is_file():
            QtGui.QFontDatabase.addApplicationFont(str(font_file))
            cls.app.setFont(QtGui.QFont("Arial",9))

    def setUp(self):
        self.scene = Scene()
        cmds = types.ModuleType("maya.cmds")
        cmds.ls, cmds.select, cmds.scriptJob = self.scene.ls,self.scene.select,self.scene.scriptJob
        cmds.about = lambda **kw: 20250000
        cmds.warning = self.scene.warnings.append
        omui = types.ModuleType("maya.OpenMayaUI")
        omui.MQtUtil = types.SimpleNamespace(mainWindow=lambda:None)
        maya = types.ModuleType("maya")
        maya.cmds,maya.OpenMayaUI = cmds,omui
        sys.modules.update({"maya":maya,"maya.cmds":cmds,"maya.OpenMayaUI":omui})
        spec = importlib.util.spec_from_file_location("edward_picker_qa",BUNDLE/"edward_maya_picker.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.window = self.module.show()
        self.app.processEvents()

    def tearDown(self):
        for window in self.app.topLevelWidgets():
            if window.objectName() == "EdwardMayaPicker":
                window.close()
        self.app.processEvents()
        self.assertFalse(self.scene.jobs,"Maya scene callbacks must be removed on close")

    def click(self, name, modifier=QtCore.Qt.KeyboardModifier.NoModifier):
        item = next(i for i in self.window.items if i.options["action.targets"] == [name])
        view = self.window.views[item.options["panel"]]
        point = view.mapFromScene(item.mapToScene(item.path().boundingRect().center()))
        QtTest.QTest.mouseClick(view.viewport(),QtCore.Qt.MouseButton.LeftButton,modifier,point)
        self.app.processEvents()
        return item

    def test_eye_click_add_toggle_and_selection_highlight(self):
        self.assertEqual(self.window.namespace.text(),"edward")
        self.assertEqual(len(self.window.resolved),len(NAMES))
        right = self.click("R_eye_CTL")
        self.assertTrue(right.selected_in_maya)
        self.click("L_eye_CTL",QtCore.Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual({n.rsplit(":",1)[-1] for n in self.scene.selection},{"R_eye_CTL","L_eye_CTL"})
        self.click("R_eye_CTL",QtCore.Qt.KeyboardModifier.ControlModifier)
        self.assertEqual({n.rsplit(":",1)[-1] for n in self.scene.selection},{"L_eye_CTL"})
        self.assertFalse(right.selected_in_maya)

    def test_current_export_target_coverage(self):
        curves = json.loads((ROOT/"maya_tools/assets/Edward/curves/Edward_v001.curves").read_text())
        exported = {entry["transform"]["name"] for entry in curves.values()}
        self.assertEqual(NAMES, exported)
        self.assertEqual(len(self.window.resolved), len(exported))

    def test_all_selector_and_layer_visibility(self):
        fine = [i for i in self.window.items if i.options.get("visibility_layer")=="Fine eyelids"]
        self.assertEqual(len(fine),84)
        self.assertFalse(any(i.isVisible() for i in fine))
        self.window.fine.setChecked(True)
        self.assertTrue(all(i.isVisible() for i in fine))
        self.window.secondary.setChecked(False)
        self.assertFalse(any(i.isVisible() for i in self.window.items if i.options.get("visibility_layer")=="Secondary"))
        item = next(i for i in self.window.items if i.options["panel"]==0 and i.options["text.content"]=="Select All")
        view = self.window.views[0]
        point = view.mapFromScene(item.mapToScene(item.path().boundingRect().center()))
        QtTest.QTest.mouseClick(view.viewport(),QtCore.Qt.MouseButton.LeftButton,QtCore.Qt.KeyboardModifier.NoModifier,point)
        self.assertEqual(len(self.scene.selection),len(NAMES))
        self.scene.selection.clear()
        self.window.update_selection()
        self.window.secondary.setChecked(True)
        self.window.fine.setChecked(False)
        self.window.status.setText("Offline Qt preview - live Maya scene not tested")
        self.window.grab().save(str(BUNDLE/"04_maya_picker_preview.png"))

    def test_missing_namespace_does_not_change_selection(self):
        self.click("L_eye_CTL")
        before = self.scene.selection.copy()
        self.window.namespace.setText("absent")
        self.window.refresh_targets()
        self.assertFalse(self.window.resolved)
        self.click("R_eye_CTL")
        self.assertEqual(self.scene.selection,before)
        self.assertTrue(self.scene.warnings)

    def test_installer_relaunch_after_closed_window_is_idempotent(self):
        cmds = sys.modules["maya.cmds"]
        shelves, buttons, saves = set(),set(),[]
        labels = {}
        def shelf_layout(name, **kw):
            if kw.get("query") and kw.get("childArray"):
                return [button for button in buttons if button.startswith(name+"|")]
            if kw.get("exists"):
                return name in shelves
            full = kw.get("parent","")+"|"+name
            shelves.add(full)
            return full
        def shelf_button(name, **kw):
            if kw.get("query") and kw.get("label"):
                return labels[name]
            if kw.get("exists"):
                return name in buttons
            full = kw["parent"]+"|"+name
            buttons.add(full)
            labels[full] = kw["label"]
            return full
        cmds.shelfLayout,cmds.shelfButton = shelf_layout,shelf_button
        cmds.objectTypeUI = lambda _: "shelfButton"
        cmds.deleteUI = lambda name: buttons.discard(name)
        cmds.saveShelf = lambda *args: saves.append(args)
        mel = types.ModuleType("maya.mel")
        mel.eval = lambda _: "ShelfTop"
        sys.modules["maya.mel"] = mel
        sys.modules["maya"].mel = mel
        spec = importlib.util.spec_from_file_location("edward_installer_qa",BUNDLE/"install_edward_picker.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        base = Path(tempfile.gettempdir()).resolve()
        with tempfile.TemporaryDirectory(prefix="edward-picker-test-",dir=str(base)) as directory:
            install_root = Path(directory).resolve()
            self.assertTrue(install_root.is_relative_to(base))
            cmds.internalVar = lambda **kw: (str(install_root/"studio_shelves")+";"+str(install_root/"shelves") if kw.get("userShelfDir") else str(install_root))
            shelves.add("ShelfTop|AutoRig")
            buttons.add("ShelfTop|AutoRig|repository_picker")
            labels["ShelfTop|AutoRig|repository_picker"] = "EdwardPicker"
            destination = Path(installer.install())
            self.assertTrue((destination/"backgrounds/face.png").is_file())
            self.assertTrue((install_root/"scripts/edward_picker_launcher.py").is_file())
            sys.modules["edward_maya_picker"]._WINDOW.close()
            self.app.processEvents()
            installer.install()
            self.assertEqual(len(buttons),1)
            self.assertEqual(len(saves),2)
            self.assertTrue(all(path == str(install_root/"shelves/shelf_AutoRig") for _,path in saves))
            sys.modules["edward_maya_picker"]._WINDOW.close()
            self.app.processEvents()
            sys.path.remove(str(install_root/"scripts"))
            sys.modules.pop("edward_picker_launcher",None)
            sys.modules.pop("edward_maya_picker",None)


if __name__ == "__main__":
    unittest.main()
