"""Real offscreen Qt authoring workflow on a synthetic Maya mesh."""
import os
import sys
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import maya.standalone
from maya import cmds


def run():
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from maya_tools.scripts.ui import joint_correctives_UI as ui
    from maya_tools.scripts.tools import joint_correctives as jc
    # Maya standalone otherwise creates only QGuiApplication, which cannot
    # host widgets. Establish QApplication before initializing standalone.
    app = ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
    qt_gui = __import__(ui.QtCore.__name__.rsplit(".", 1)[0] + ".QtGui", fromlist=["QFont"])
    qt_gui.QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(qt_gui.QFont("Arial", 9))
    maya.standalone.initialize(name="python")
    try:
        mesh = cmds.polySphere(name="shoulder_mesh", subdivisionsX=16, subdivisionsY=12)[0]
        clavicle = cmds.createNode("joint", name="clavicle")
        arm = cmds.createNode("joint", name="upper_arm", parent=clavicle)
        cmds.skinCluster(arm, mesh, toSelectedBones=True)
        window = ui.JointCorrectivesUI()
        window.mesh.setText(mesh)
        window._create()
        window.parent_joint.setText(arm)
        window.patch_name.setText("deltoid")
        vertices = [v for v in cmds.ls(mesh + ".vtx[*]", flatten=True)
                    if cmds.pointPosition(v, world=True)[1] > .1]
        cmds.select(vertices, replace=True)
        window._add_joint()
        window._add_pose()
        system, pose = window._system(), window._pose()
        assert cmds.getAttr(system + ".editing")
        handle = jc.linked(system, "handles", 0)
        cmds.setAttr(handle + ".translateY", .5)
        window._finish(True)
        window.weight.setValue(.5)
        joint = jc.linked(system, "joints", 0)
        assert abs(cmds.getAttr(joint + ".translateY") - .25) < 1e-6
        window.reference.setText(clavicle)
        window._swing()
        window.start.setValue(0)
        window.end.setValue(90)
        window.smooth.setChecked(False)
        window._configure()
        cmds.setAttr(arm + ".rotateZ", 45)
        assert abs(cmds.getAttr(pose + ".effectiveWeight") - .5) < 1e-6
        cmds.setAttr(arm + ".rotateZ", 90)
        assert abs(cmds.getAttr(joint + ".translateY") - .5) < 1e-6
        window._preview(pose)
        window._edit()
        cmds.setAttr(handle + ".translateY", 7)
        window._finish(False)
        assert abs(cmds.getAttr(joint + ".translateY") - .5) < 1e-6
        window._preview(None)
        # Save an isolated, editable example without changing an open Maya scene.
        folder = Path("C:/GIT/tmp/joint_correctives_validation")
        folder.mkdir(parents=True, exist_ok=True)
        cmds.file(rename=str(folder / "shoulder_joint_targets_demo.ma"))
        cmds.file(save=True, type="mayaAscii")
        window.show()
        app.processEvents()
        window.grab().save(str(folder / "joint_targets_ui.png"))
        window._delete()
        assert not cmds.objExists(pose)
        window.close()
        print("PASS: Qt create region, vertex patch, edit/save, manual weight, shoulder driver, solo/cancel, delete; example and UI capture saved")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
