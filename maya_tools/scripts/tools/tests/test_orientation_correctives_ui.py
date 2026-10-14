"""Real Qt: create a neutral region, convert a saved sculpt and capture another."""
import os, sys
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
from maya import cmds
from maya_tools.scripts.ui import pose_blendshapes_UI as ui
app = ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
qt_gui = __import__(ui.QtCore.__name__.rsplit(".", 1)[0] + ".QtGui", fromlist=["QFont"])
qt_gui.QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
app.setFont(qt_gui.QFont("Arial", 9))
maya.standalone.initialize(name="python")
try:
    from maya_tools.scripts.tools import pose_blendshapes as poses, orientation_correctives as orient
    cmds.undoInfo(state=True)
    root = cmds.createNode("transform", name="Character")
    reference = cmds.createNode("transform", name="torso", parent=root)
    joint = cmds.createNode("joint", name="L_arm_JNT", parent=reference)
    ctl = cmds.createNode("transform", name="L_shoulder_CTL", parent=root)
    cmds.connectAttr(ctl + ".rotate", joint + ".rotate")
    mesh = cmds.polySphere()[0]
    cmds.parent(mesh, root)
    cmds.skinCluster(joint, mesh, toSelectedBones=True)
    cmds.select(mesh)
    window = ui.PoseBlendshapesUI()
    window.create_blendshape()
    bs = window.current_blendshape()
    cmds.setAttr(ctl + ".rotateZ", 45)
    index, _ = poses.add_target(mesh, bs, ctl)
    cmds.move(.2, 0, 0, mesh + ".vtx[1]", relative=True, objectSpace=True)
    poses.finish_edit()
    backup = cmds.getAttr(poses._delta_path(bs, mesh, index) + ".inputPointsTarget")
    cmds.setAttr(ctl + ".rotateZ", 0)
    cmds.select(joint); window.load_driver_node(window.driver_joint)
    cmds.select(reference); window.load_driver_node(window.driver_reference)
    window.create_orientation_region()
    window.refresh_targets(index)
    cmds.setAttr(ctl + ".rotateZ", 20)
    window.convert_orientation()
    assert cmds.getAttr(ctl + ".rotateZ") == 20
    assert backup == cmds.getAttr(poses._delta_path(bs, mesh, index) + ".inputPointsTarget")
    assert orient.linked(poses.pose_record(bs, index), "orientationSystem")
    cmds.setAttr(ctl + ".rotate", 0, 45, 0)
    cmds.select(ctl)
    dialog = ui.CaptureDialog(window)
    dialog.create()
    assert poses.edit_session() and not window.orientation_box.isEnabled()
    window.finish(False)
    assert window.orientation_box.isEnabled()
    assert len(poses.targets(bs)) == 2
    window.show(); app.processEvents()
    folder = Path("C:/GIT/tmp/research_edward_validation")
    folder.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(folder / "orientation_editor.png"))
    window.close()
    print("PASS orientation Qt: neutral region, conversion preserves sculpt/current pose, orientation capture, editing guards")
finally:
    maya.standalone.uninitialize()
