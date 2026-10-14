"""Real Maya sculpt, driver, naming, cancellation and save/load checks."""
import math
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds


def close(a, b):
    if isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            close(x, y)
    else:
        assert math.isclose(a, b, abs_tol=2e-5), (a, b)


def run():
    maya.standalone.initialize(name="python")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from maya_tools.scripts.tools import pose_blendshapes as tool
        for order in ("pre", "post"):
            cmds.file(new=True, force=True)
            cmds.undoInfo(state=True)
            master = cmds.createNode("transform", name="master")
            control = cmds.createNode("transform", name="L_shoulder_CTL", parent=master)
            joint = cmds.createNode("joint", parent=master)
            cmds.connectAttr(control + ".rotate", joint + ".rotate")
            cmds.connectAttr(control + ".translate", joint + ".translate")
            mesh = cmds.polyPlane(name="body", subdivisionsX=3, subdivisionsY=3)[0]
            cmds.parent(mesh, master)
            skin = cmds.skinCluster(joint, mesh, toSelectedBones=True)[0]
            cmds.setAttr(control + ".rotateZ", 45)
            bs = tool.create_blendshape(mesh, order)
            assert tool.deformation_order(bs, mesh) == order
            before = cmds.pointPosition(mesh + ".vtx[0]", world=True)
            index, name = tool.add_target(mesh, bs, control)
            assert name == "L_shoulder_RZ45_BLS", name
            assert index == 0 and tool.edit_session()
            close(cmds.pointPosition(mesh + ".vtx[0]", world=True), before)
            cmds.move(0, 1, 0, mesh + ".vtx[0]", relative=True, worldSpace=True)
            corrected = cmds.pointPosition(mesh + ".vtx[0]", world=True)
            close(corrected, (before[0], before[1] + 1, before[2]))
            tool.finish_edit()
            close(cmds.pointPosition(mesh + ".vtx[0]", world=True), corrected)
            assert not tool.edit_session()
            record = tool.pose_record(bs, 0)
            assert record
            assert tool.linked(record, "controller") == control
            for angle, expected in ((0, 0), (22.5, .5), (45, 1), (90, 1), (-45, 0)):
                cmds.setAttr(control + ".rotateZ", angle)
                close(cmds.getAttr(bs + ".weight[0]"), expected)
            # At neutral, disabling the blendshape has no effect.
            tool.go_to_pose(bs, 0, neutral=True)
            neutral = cmds.pointPosition(mesh + ".vtx[0]", world=True)
            cmds.setAttr(bs + ".envelope", 0)
            close(cmds.pointPosition(mesh + ".vtx[0]", world=True), neutral)
            cmds.setAttr(bs + ".envelope", 1)
            # New additive shape corrections rotate with the skinned surface.
            cmds.setAttr(control + ".rotateZ", 90)
            pos90 = cmds.pointPosition(mesh + ".vtx[0]", world=True)
            cmds.setAttr(bs + ".envelope", 0)
            base90 = cmds.pointPosition(mesh + ".vtx[0]", world=True)
            cmds.setAttr(bs + ".envelope", 1)
            close([a-b for a,b in zip(pos90, base90)], (-math.sqrt(.5), math.sqrt(.5), 0))
            # Cancel edits to an existing target exactly restores old deltas.
            tool.begin_edit(mesh, bs, 0, restore_pose=True)
            close(cmds.getAttr(control + ".rotateZ"), 45)
            cmds.move(0, 3, 0, mesh + ".vtx[0]", relative=True, worldSpace=True)
            tool.finish_edit(save=False)
            close(cmds.pointPosition(mesh + ".vtx[0]", world=True), corrected)
            # Signed/decimal channels and multiple simultaneous drivers.
            cmds.setAttr(control + ".translateX", -2.5)
            cmds.setAttr(control + ".rotateZ", -30)
            second, second_name = tool.add_target(mesh, bs, control)
            assert second_name == "L_shoulder_TXm2p5_RZm30_BLS", second_name
            cmds.move(0, 0, .2, mesh + ".vtx[1]", relative=True, worldSpace=True)
            tool.finish_edit()
            close(cmds.getAttr(bs + ".weight[%d]" % second), 1)
            cmds.setAttr(control + ".translateX", -1.25)
            cmds.setAttr(control + ".rotateZ", -15)
            close(cmds.getAttr(bs + ".weight[%d]" % second), .25)
            cmds.setAttr(control + ".translateX", 0)
            close(cmds.getAttr(bs + ".weight[%d]" % second), 0)
            # Duplicate poses get an automatic unique alias, no overwrite.
            tool.go_to_pose(bs, 0)
            duplicate, duplicate_name = tool.add_target(mesh, bs, control)
            assert duplicate_name == "L_shoulder_RZ45_02_BLS", duplicate_name
            tool.finish_edit(False)
            tool.remove_target(mesh, bs, duplicate)
            assert duplicate not in [i for i, _ in tool.targets(bs)]
            cmds.undo()
            assert duplicate in [i for i, _ in tool.targets(bs)]
            assert tool.pose_record(bs, duplicate)
            # Controller renaming preserves the recorded pose through messages.
            control = cmds.rename(control, "L_renamed_CTL")
            tool.go_to_pose(bs, 0, neutral=True)
            close(cmds.getAttr(control + ".rotateZ"), 0)
            tool.go_to_pose(bs, 0)
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "pose_correctives.ma")
                saved = cmds.pointPosition(mesh + ".vtx[0]", world=True)
                cmds.file(rename=path)
                cmds.file(save=True, type="mayaAscii")
                cmds.file(new=True, force=True)
                cmds.file(path, open=True, force=True)
                close(cmds.pointPosition(mesh + ".vtx[0]", world=True), saved)
                cmds.setAttr(control + ".rotateZ", 22.5)
                close(cmds.getAttr(bs + ".weight[0]"), .5)
            assert not any(cmds.nodeType(n) == "poseInterpolator" for n in cmds.ls())
            assert not (cmds.cycleCheck(all=True, list=True) or [])
            print("PASS", order, "native posed sculpt, follows rotation, neutral/half/full weights, cancel, mixed signed drivers, unique names, delete/undo, rename, save/reopen, no Pose Interpolator")
        # A wrapped garment consumes worldMesh. New corrections must still
        # deform the body, and the garment must keep reading the visible body.
        cmds.file(new=True, force=True)
        mesh = cmds.polySphere(name="wrap_driver_body")[0]
        control = cmds.createNode("transform", name="L_shoulder_CTL")
        joint = cmds.createNode("joint")
        cmds.connectAttr(control + ".rotate", joint + ".rotate")
        skin = cmds.skinCluster(joint, mesh, toSelectedBones=True)[0]
        garment = cmds.polySphere(name="garment")[0]
        wrap = cmds.deformer(garment, type="proximityWrap")[0]
        from maya.internal.nodes.proximitywrap.node_interface import NodeInterface
        shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True)[0]
        NodeInterface(wrap).addDrivers([shape])
        wrap_source = cmds.connectionInfo(wrap + ".drivers[0].driverGeometry", sourceFromDestination=True)
        cmds.setAttr(control + ".rotateZ", 45)
        bs = tool.create_blendshape(mesh, "post")
        assert tool.geometry_index(bs, mesh) == 0
        assert tool.deformation_order(bs, mesh) == "post"
        assert bs in tool.blendshapes(mesh)
        assert cmds.connectionInfo(wrap + ".drivers[0].driverGeometry", sourceFromDestination=True) == wrap_source
        before = cmds.pointPosition(mesh + ".vtx[0]", world=True)
        index, _ = tool.add_target(mesh, bs, control)
        cmds.move(0, .3, 0, mesh + ".vtx[0]", relative=True, worldSpace=True)
        tool.finish_edit()
        close(cmds.pointPosition(mesh + ".vtx[0]", world=True), (before[0], before[1] + .3, before[2]))
        print("PASS: post sculpt on body with proximityWrap consumers preserves driver connections")
        # Existing blendshape contents must survive adding a managed pose.
        cmds.file(new=True, force=True)
        mesh = cmds.polyPlane(name="existing_mesh", subdivisionsX=2, subdivisionsY=2)[0]
        live = cmds.duplicate(mesh, name="existing_target")[0]
        cmds.move(0, .2, 0, live + ".vtx[0]", relative=True, objectSpace=True)
        bs = cmds.blendShape(live, mesh, name="existing_BLS")[0]
        cmds.setAttr(bs + ".weight[0]", .4)
        control = cmds.createNode("transform", name="R_arm_CTL")
        cmds.setAttr(control + ".rotateZ", 45)
        before = cmds.pointPosition(mesh + ".vtx[0]", world=True)
        index, name = tool.add_target(mesh, bs, control)
        assert index == 1 and name == "R_arm_RZ45_BLS"
        close(cmds.pointPosition(mesh + ".vtx[0]", world=True), before)
        close(cmds.getAttr(bs + ".weight[0]"), .4)
        tool.finish_edit(False)
        assert cmds.objExists(live)
        assert cmds.listConnections(tool._delta_path(bs, mesh, 0) + ".inputGeomTarget", source=True, destination=False)
        try:
            tool.begin_edit(mesh, bs, 0)
        except ValueError:
            pass
        else:
            raise AssertionError("Live-connected source target should remain protected")
        assert not tool.edit_session()
        print("PASS: existing blendshape target geometry, driver weights and live connections preserved")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
