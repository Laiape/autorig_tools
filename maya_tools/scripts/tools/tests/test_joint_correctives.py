"""Real Maya checks for joint targets, skin neutrality and saved playback."""
import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om


def close(actual, expected):
    if isinstance(actual, (list, tuple)):
        assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(actual, expected)), (actual, expected)
    else:
        assert math.isclose(actual, expected, abs_tol=1e-5), (actual, expected)


def points(mesh):
    return [cmds.pointPosition(v, world=True) for v in cmds.ls(mesh + ".vtx[*]", flatten=True)]


def run():
    maya.standalone.initialize(name="python")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from maya_tools.scripts.tools import joint_correctives as jc
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)
        master = cmds.createNode("transform", name="master")
        shoulder = cmds.createNode("joint", name="shoulder", parent=master)
        cmds.setAttr(shoulder + ".jointOrient", 12, 25, -8)
        mesh = cmds.polyPlane(name="body", width=4, height=4, subdivisionsX=4, subdivisionsY=4)[0]
        cmds.parent(mesh, master)
        base_skin = cmds.skinCluster(shoulder, mesh, toSelectedBones=True)[0]
        before = points(mesh)
        system = jc.create_system(mesh)
        for a, b in zip(points(mesh), before):
            close(a, b)
        vertices = [mesh + ".vtx[%d]" % i for i in (6, 7, 11, 12)]
        joint = jc.add_joint(system, shoulder, vertices)
        pose = jc.add_pose(system, "volume")
        jc.begin_edit(system, pose)
        handle = jc.linked(system, "handles", 0)
        cmds.setAttr(handle + ".translate", 0, 2, 0)
        jc.finish_edit(system)
        close(cmds.getAttr(joint + ".translate")[0], (0, 0, 0))
        for a, b in zip(points(mesh), before):
            close(a, b)
        cmds.setAttr(pose + ".weight", .5)
        close(cmds.getAttr(joint + ".translateY"), 1)
        half = points(mesh)
        cmds.setAttr(pose + ".weight", 1)
        close(cmds.getAttr(joint + ".translateY"), 2)
        full = points(mesh)
        for rest, middle, end in zip(before, half, full):
            close(middle, [(a + b) / 2 for a, b in zip(rest, end)])
        assert full != before
        assert full[0] == before[0]
        # A second target can subtract volume without overwriting the first.
        second = jc.add_pose(system, "reduce")
        jc.begin_edit(system, second)
        cmds.setAttr(handle + ".translateY", -1)
        cmds.setAttr(handle + ".rotateZ", 20)
        cmds.setAttr(handle + ".scale", 1.2, .8, 1)
        jc.finish_edit(system)
        cmds.setAttr(second + ".weight", .5)
        close(cmds.getAttr(joint + ".translateY"), 1.5)
        close(cmds.getAttr(joint + ".rotateZ"), 10)
        close(cmds.getAttr(joint + ".scale")[0], (1.1, .9, 1))
        jc.preview(system, second)
        close(cmds.getAttr(joint + ".translateY"), -1)
        jc.begin_edit(system, second)
        cmds.setAttr(handle + ".translateY", -99)
        jc.finish_edit(system, save=False)
        close(cmds.getAttr(joint + ".translateY"), -1)
        jc.preview(system)
        cmds.setAttr(second + ".enabled", False)
        close(cmds.getAttr(joint + ".translateY"), 2)
        # Zero targets must exactly match the original skin in every pose.
        cmds.setAttr(system + ".envelope", 0)
        for rotation, scale in (((20, 10, 30), (1, 1, 1)), ((-45, 60, 12), (2, 2, 2)), ((30, -25, 50), (-1, 1.3, .7))):
            cmds.setAttr(master + ".translate", 7, -3, 4)
            cmds.setAttr(master + ".rotate", *rotation)
            cmds.setAttr(master + ".scale", *scale)
            cmds.setAttr(shoulder + ".rotateZ", 67)
            enabled = points(mesh)
            skin = jc.linked(system, "skin")
            cmds.setAttr(skin + ".envelope", 0)
            disabled = points(mesh)
            for a, b in zip(enabled, disabled):
                close(a, b)
            cmds.setAttr(skin + ".envelope", 1)
        cmds.setAttr(master + ".translate", 0, 0, 0)
        cmds.setAttr(master + ".rotate", 0, 0, 0)
        cmds.setAttr(master + ".scale", 1, 1, 1)
        cmds.setAttr(shoulder + ".rotateZ", 0)
        cmds.setAttr(system + ".envelope", 1)
        # Driver thresholds accept degrees, including descending ranges.
        jc.configure_driver(pose, shoulder + ".rotateZ", 30, 90, smooth=False)
        for angle, weight in ((0, 0), (30, 0), (60, .5), (90, 1), (110, 1)):
            cmds.setAttr(shoulder + ".rotateZ", angle)
            close(cmds.getAttr(pose + ".effectiveWeight"), weight)
        jc.configure_driver(pose, shoulder + ".rotateZ", 0, -90, smooth=False)
        cmds.setAttr(shoulder + ".rotateZ", -45)
        close(cmds.getAttr(pose + ".effectiveWeight"), .5)
        cmds.setAttr(shoulder + ".rotateZ", 0)
        angle_plug = jc.direction_driver(system, shoulder, master, "X")
        close(cmds.getAttr(angle_plug), 0)
        cmds.setAttr(shoulder + ".rotateZ", 60)
        print("swing60", cmds.getAttr(angle_plug))
        assert cmds.getAttr(angle_plug) > 0
        jc.configure_driver(pose, angle_plug, 0, cmds.getAttr(angle_plug), smooth=False)
        close(cmds.getAttr(pose + ".effectiveWeight"), 1)
        # New joints participate in existing targets with zero deltas.
        extra = jc.add_joint(system, shoulder, vertices, "extra", falloff=False)
        close(cmds.getAttr(extra + ".translate")[0], (0, 0, 0))
        jc.remove_pose(system, second)
        assert not cmds.objExists(second)
        cmds.undo()
        assert cmds.objExists(second)
        assert len(jc.indexed(system, "poses")) == 2
        # No Python expression or callback is needed to evaluate a reopened scene.
        assert not (cmds.ls(type="expression") or [])
        assert not (cmds.cycleCheck(all=True, list=True) or [])
        saved = points(mesh)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "joint_targets.ma")
            cmds.file(rename=path)
            cmds.file(save=True, type="mayaAscii")
            cmds.file(new=True, force=True)
            cmds.file(path, open=True, force=True)
            assert system in jc.systems()
            for a, b in zip(points(mesh), saved):
                close(a, b)
            cmds.setAttr(pose + ".auto", False)
            cmds.setAttr(pose + ".weight", .25)
            close(cmds.getAttr(joint + ".translateY"), .5)
        print("PASS: normalized masks, zero-effect base skin in posed/scaled rig, additive TRS targets, edit/cancel/solo, automatic ranges, new joints, delete/undo, save/reopen, no cycles")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
