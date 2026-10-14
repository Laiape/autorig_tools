"""Real pre/post mirrored sculpts, rig axes, animation preservation and undo."""
import json
import math
import os
import sys
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds


def close(a, b):
    assert all(math.isclose(x, y, abs_tol=3e-5) for x, y in zip(a, b)), (a, b)


def run():
    maya.standalone.initialize(name="python")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from maya_tools.scripts.tools import pose_blendshapes as tool
        for order in ("pre", "post"):
            for mirrored_axes in (False, True):
                cmds.file(new=True, force=True)
                cmds.undoInfo(state=True)
                cmds.namespace(add="character")
                left = cmds.createNode("transform", name="character:L_arm_CTL")
                right_grp = cmds.createNode("transform", name="right_grp")
                if mirrored_axes:
                    cmds.setAttr(right_grp + ".rotateY", 180)
                right = cmds.createNode("transform", name="character:R_arm_CTL", parent=right_grp)
                left_joint = cmds.createNode("joint", name="L_arm_JNT")
                right_joint = cmds.createNode("joint", name="R_arm_JNT")
                if mirrored_axes:
                    cmds.parent(right_joint, right_grp, relative=True)
                cmds.connectAttr(left + ".rotate", left_joint + ".rotate")
                cmds.connectAttr(right + ".rotate", right_joint + ".rotate")
                mesh = cmds.polyPlane(name="body", axis=(0, 0, 1), subdivisionsX=4, subdivisionsY=4, width=4, height=4)[0]
                if mirrored_axes:
                    # Same bind pose as the unmirrored fixture, with mirrored R axes.
                    cmds.setAttr(right_joint + ".jointOrientY", 180)
                cmds.skinCluster([left_joint, right_joint], mesh, toSelectedBones=True)
                for vertex in range(25):
                    x = cmds.pointPosition(mesh + ".vtx[%d]" % vertex, local=True)[0]
                    cmds.skinPercent(cmds.ls(type="skinCluster")[0], mesh + ".vtx[%d]" % vertex,
                                     transformValue=[(left_joint, 1 if x >= 0 else 0), (right_joint, 0 if x >= 0 else 1)])
                cmds.setKeyframe(left, attribute="rotateZ", time=0, value=45)
                cmds.setKeyframe(left, attribute="rotateZ", time=10, value=0)
                cmds.currentTime(0)
                animation = cmds.connectionInfo(left + ".rotateZ", sourceFromDestination=True)
                bs = tool.create_blendshape(mesh, order)
                source, _ = tool.add_target(mesh, bs, left)
                if not mirrored_axes:
                    try:
                        tool.mirror_target(mesh, bs, source)
                    except ValueError as exc:
                        assert "active target edit" in str(exc)
                    else:
                        raise AssertionError("An unfinished sculpt must be protected")
                cmds.move(.2, .7, .3, mesh + ".vtx[14]", relative=True, worldSpace=True)
                tool.finish_edit()
                source_delta = cmds.getAttr(tool._delta_path(bs, mesh, source) + ".inputPointsTarget")
                old_selection = cmds.ls(selection=True, long=True)
                old_nodes = set(cmds.ls())
                destination, name = tool.mirror_target(mesh, bs, source)
                assert name.startswith("R_arm_"), name
                assert not tool.edit_session()
                assert cmds.connectionInfo(left + ".rotateZ", sourceFromDestination=True) == animation
                assert cmds.getAttr(left + ".rotateZ") == 45
                assert cmds.getAttr(right + ".rotateZ") == 0
                assert cmds.ls(selection=True, long=True) == old_selection
                assert cmds.getAttr(tool._delta_path(bs, mesh, source) + ".inputPointsTarget") == source_delta
                record = tool.pose_record(bs, destination)
                assert tool.linked(record, "controller") == right
                values = json.loads(cmds.getAttr(record + ".channels"))
                expected_pose = 45 if mirrored_axes else -45
                assert values[0]["pose"] == expected_pose, values
                # At neutral, compare the actual world-space deformations of
                # both targets, including native tangent-space authoring.
                with tool._temporary_values({left + ".rotateZ": 0, right + ".rotateZ": 0,
                                             bs + ".weight[%d]" % source: 0,
                                             bs + ".weight[%d]" % destination: 0}):
                    baseline_left = cmds.pointPosition(mesh + ".vtx[14]", world=True)
                    baseline_right = cmds.pointPosition(mesh + ".vtx[10]", world=True)
                    cmds.setAttr(bs + ".weight[%d]" % source, 1)
                    sculpt_left = cmds.pointPosition(mesh + ".vtx[14]", world=True)
                    cmds.setAttr(bs + ".weight[%d]" % source, 0)
                    cmds.setAttr(bs + ".weight[%d]" % destination, 1)
                    sculpt_right = cmds.pointPosition(mesh + ".vtx[10]", world=True)
                    delta_left = [a-b for a,b in zip(sculpt_left, baseline_left)]
                    delta_right = [a-b for a,b in zip(sculpt_right, baseline_right)]
                    close(delta_right, [-delta_left[0], delta_left[1], delta_left[2]])
                # Mirror the same pose again without overwriting the first R.
                duplicate, duplicate_name = tool.mirror_target(mesh, bs, source)
                assert duplicate != destination and "_02_BLS" in duplicate_name
                cmds.undo()
                assert duplicate not in dict(tool.targets(bs))
                assert tool.pose_record(bs, duplicate) is None
                with tool._temporary_values({right + ".rotateZ": expected_pose / 2}):
                    assert math.isclose(cmds.getAttr(bs + ".weight[%d]" % destination), .5)
                try:
                    tool.mirror_target(mesh, bs, destination)
                except ValueError as exc:
                    assert "left controller" in str(exc)
                else:
                    raise AssertionError("R target should not be mirrored L to R")
                print("PASS", order, "mirrored axes", mirrored_axes,
                      "world-space sculpt reflection, signed R driver, namespaces, animation, selection, duplicate and undo")
        # Slight model asymmetry and no center-line edges require interpolation
        # on the reflected surface instead of exact vertex lookup.
        cmds.file(new=True, force=True)
        mesh = cmds.polyPlane(name="asymmetric_body", axis=(0, 0, 1), subdivisionsX=3,
                             subdivisionsY=2, width=4, height=2)[0]
        cmds.move(0, 0, .05, mesh + ".vtx[11]", relative=True, objectSpace=True)
        joint = cmds.createNode("joint")
        cmds.skinCluster(joint, mesh, toSelectedBones=True)
        left = cmds.createNode("transform", name="L_shoulder_CTL")
        right = cmds.createNode("transform", name="R_shoulder_CTL")
        cmds.setAttr(left + ".rotateZ", 45)
        bs = tool.create_blendshape(mesh, "post")
        index, _ = tool.add_target(mesh, bs, left)
        cmds.move(0, .7, 0, mesh + ".vtx[11]", relative=True, worldSpace=True)
        tool.finish_edit()
        destination, _ = tool.mirror_target(mesh, bs, index)
        with tool._temporary_values({bs + ".weight[%d]" % index: 0,
                                     bs + ".weight[%d]" % destination: 0}):
            before = cmds.pointPosition(mesh + ".vtx[8]", world=True)
            cmds.setAttr(bs + ".weight[%d]" % destination, 1)
            after = cmds.pointPosition(mesh + ".vtx[8]", world=True)
            assert .6 < after[1] - before[1] <= .70001, (before, after)
        values = [{"channel": "translateX", "default": 0, "pose": -2.5},
                  {"channel": "rotateY", "default": 0, "pose": -30}]
        mirrored = tool._mirrored_channels(tool.mesh_transform(mesh), left, right, values)
        assert [v["pose"] for v in mirrored] == [2.5, 30]
        print("PASS: asymmetric surface interpolation, translated and rotated driver signs")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
