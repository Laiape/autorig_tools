"""Real Qt capture-dialog and native mesh sculpt workflow in mayapy."""
import os
import sys
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import maya.standalone
from maya import cmds


def run():
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from maya_tools.scripts.ui import pose_blendshapes_UI as ui
    from maya_tools.scripts.tools import pose_blendshapes as tool
    app = ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
    qt_gui = __import__(ui.QtCore.__name__.rsplit(".", 1)[0] + ".QtGui", fromlist=["QFont"])
    qt_gui.QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(qt_gui.QFont("Arial", 9))
    maya.standalone.initialize(name="python")
    try:
        cmds.undoInfo(state=True)
        mesh = cmds.polySphere(name="shoulder_mesh", subdivisionsX=16, subdivisionsY=12)[0]
        root = cmds.createNode("transform", name="Character")
        cmds.parent(mesh, root)
        control = cmds.createNode("transform", name="L_shoulder_CTL", parent=root)
        right_control = cmds.createNode("transform", name="R_shoulder_CTL", parent=root)
        joint = cmds.createNode("joint", name="L_upperArm_JNT")
        cmds.connectAttr(control + ".rotate", joint + ".rotate")
        cmds.skinCluster(joint, mesh, toSelectedBones=True)
        cmds.select(mesh, replace=True)
        window = ui.PoseBlendshapesUI()
        assert window.mesh.text().endswith(mesh)
        window.create_blendshape()
        assert window.blendshapes.count() == 1
        assert not window.live.isChecked() and not window.live.isEnabled()
        bs = window.current_blendshape()
        cmds.setAttr(control + ".rotateZ", 45)
        cmds.select(control, replace=True)
        dialog = ui.CaptureDialog(window)
        assert dialog.add.isEnabled()
        assert dialog.name.text() == "L_shoulder_RZ45_BLS"
        assert dialog.channels.rowCount() == 1
        folder = Path("C:/GIT/tmp/pose_blendshapes_validation")
        folder.mkdir(parents=True, exist_ok=True)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(folder / "capture_dialog.png"))
        dialog.create()
        assert window.targets.count() == 1
        assert window.save.isEnabled()
        assert window.live.isChecked() and "#c83232" in window.live.styleSheet()
        assert not window.mirror.isEnabled()
        assert not window.targets.isEnabled()
        cmds.move(0, .3, 0, mesh + ".vtx[50]", relative=True, worldSpace=True)
        sculpt = cmds.pointPosition(mesh + ".vtx[50]", world=True)
        window.finish(True)
        assert not window.save.isEnabled()
        assert window.targets.isEnabled()
        assert not window.live.isChecked() and not window.live.styleSheet()
        assert window.mirror.isEnabled()
        assert window.targets.contextMenuPolicy() == ui.QtCore.Qt.CustomContextMenu
        entries = tool.targets(bs)
        record = tool.pose_record(bs, 0)
        sdk = cmds.connectionInfo(bs + ".weight[0]", sourceFromDestination=True)
        menu = window.target_menu(window.targets.currentItem())
        assert len(menu.actions()) == 1
        assert all("same target" in action.text() for action in menu.actions())
        menu.actions()[0].trigger()
        assert window.status.text().startswith("Mirrored shape in "), window.status.text()
        assert tool.targets(bs) == entries and tool.pose_record(bs, 0) == record
        assert cmds.connectionInfo(bs + ".weight[0]", sourceFromDestination=True) == sdk
        window.mirror.click()
        assert window.targets.count() == 2
        right_index = window.current_target()
        assert dict(tool.targets(bs))[right_index].startswith("R_shoulder_")
        assert tool.linked(tool.pose_record(bs, right_index), "controller") == right_control
        assert not window.mirror.isEnabled()
        window.refresh_targets(0)
        window.go_pose(True)
        assert cmds.getAttr(control + ".rotateZ") == 0
        assert cmds.getAttr(bs + ".weight[0]") == 0
        window.go_pose(False)
        assert cmds.getAttr(control + ".rotateZ") == 45
        window.live.click()
        assert window.live.isChecked() and window.save.isEnabled()
        cmds.move(0, 5, 0, mesh + ".vtx[50]", relative=True, worldSpace=True)
        window.finish(False)
        assert tool.targets(bs) == entries[:1] + [(right_index, dict(tool.targets(bs))[right_index])]
        restored = cmds.pointPosition(mesh + ".vtx[50]", world=True)
        assert all(abs(a-b) < 1e-5 for a,b in zip(sculpt, restored)), (sculpt, restored)
        cmds.setAttr(right_control + ".translateY", 7)
        window.neutral.click()
        assert window.status.text().startswith("Neutral pose:"), window.status.text()
        assert cmds.getAttr(control + ".rotateZ") == 0
        assert cmds.getAttr(right_control + ".translateY") == 0
        cmds.undo()
        window.show()
        app.processEvents()
        window.grab().save(str(folder / "pose_blendshapes_ui.png"))
        cmds.file(rename=str(folder / "shoulder_pose_blendshapes_demo.ma"))
        cmds.file(save=True, type="mayaAscii")
        # Reopen the UI during an edit: Save/Cancel must remain available.
        window.edit_target()
        recovered = ui.PoseBlendshapesUI()
        assert recovered.save.isEnabled()
        assert recovered.live.isChecked() and "#c83232" in recovered.live.styleSheet()
        assert recovered.current_target() == 0
        recovered.finish(False)
        recovered.close()
        window.sync_edit()
        window.delete_target()
        assert window.targets.count() == 1
        window.close()
        print("PASS: Qt lists, LIVE toggle/red state, same-target context mirror, R mirror/driver, capture, sculpt/save/cancel, recovered red edit, poses and delete")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
