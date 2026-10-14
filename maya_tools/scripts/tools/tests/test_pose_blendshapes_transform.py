"""Native corrective conversion preserves sculpt, SDK, editing and rotation."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om


def points(mesh):
    selection = om.MSelectionList()
    selection.add(cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True)[0])
    return om.MFnMesh(selection.getDagPath(0)).getPoints()


def equal(a, b):
    assert max((x - y).length() for x, y in zip(a, b)) < 2e-5


def run():
    maya.standalone.initialize(name="python")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from maya_tools.scripts.tools import pose_blendshapes as tool
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)
        control = cmds.createNode("transform", name="L_corner_CTL")
        joint = cmds.createNode("joint", name="stableJoint")
        cmds.connectAttr(control + ".rz", joint + ".rz")
        mesh = cmds.polyPlane(subdivisionsX=2, subdivisionsY=2)[0]
        cmds.skinCluster(joint, mesh, toSelectedBones=True)
        cmds.setAttr(control + ".rz", 45)
        bs = tool.create_blendshape(mesh)
        index, alias = tool.add_target(mesh, bs, control)
        cmds.move(0, 1, 0, mesh + ".vtx[0]", relative=True, worldSpace=True)
        tool.finish_edit()
        before = points(mesh)
        weight = bs + ".weight[0]"
        driver = cmds.connectionInfo(weight, sourceFromDestination=True)
        group = bs + ".inputTarget[0].inputTargetGroup[0]"
        cmds.select(control)
        result = tool.convert_target_to_transform_space(mesh, bs, index, joint)
        equal(before, points(mesh))
        assert result["maxEndpointError"] < 2e-5
        assert cmds.getAttr(group + ".postDeformersMode") == 2
        assert cmds.aliasAttr(weight, query=True) == alias
        assert cmds.connectionInfo(weight, sourceFromDestination=True) == driver
        assert cmds.ls(selection=True) == [control]
        cmds.undo()
        assert cmds.getAttr(group + ".postDeformersMode") == 1
        equal(before, points(mesh))
        cmds.redo()
        assert cmds.getAttr(group + ".postDeformersMode") == 2
        equal(before, points(mesh))
        for angle, expected_weight in [(0, 0), (22.5, .5), (45, 1), (90, 1)]:
            cmds.setAttr(control + ".rz", angle)
            assert abs(cmds.getAttr(weight) - expected_weight) < 1e-7
        corrected = points(mesh)
        cmds.setAttr(bs + ".envelope", 0)
        delta = corrected[0] - points(mesh)[0]
        assert (delta - om.MVector(-2**-.5, 2**-.5, 0)).length() < 2e-5
        cmds.setAttr(bs + ".envelope", 1)
        tool.begin_edit(mesh, bs, index, restore_pose=True)
        cmds.move(0, 2, 0, mesh + ".vtx[0]", relative=True, worldSpace=True)
        tool.finish_edit(save=False)
        equal(before, points(mesh))
        cmds.setAttr(group + ".targetWeights[0]", .5)
        masked = points(mesh)
        try:
            tool.convert_target_to_transform_space(mesh, bs, index, joint)
        except ValueError as exc:
            assert "mask" in str(exc).lower()
        else:
            raise AssertionError("Painted masks must not be rebaked twice.")
        equal(masked, points(mesh))
        cmds.setAttr(group + ".targetWeights[0]", 1)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "converted.ma")
            cmds.file(rename=path)
            cmds.file(save=True, type="mayaAscii")
            cmds.file(path, open=True, force=True)
            equal(before, points(mesh))
            assert cmds.getAttr(group + ".postDeformersMode") == 2
            assert cmds.connectionInfo(weight, sourceFromDestination=True) == driver
        assert not (cmds.cycleCheck(all=True, list=True) or [])
        print("PASS: transform rebake, exact endpoint, SDK/alias, undo/redo, rotation, sculpt cancel, mask guard, reopen")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
