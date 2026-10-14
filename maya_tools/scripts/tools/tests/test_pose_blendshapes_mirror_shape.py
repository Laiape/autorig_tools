"""Same-target symmetrization preserves the source side, SDK and target count."""
import os
import sys
import math
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
            cmds.file(new=True, force=True)
            cmds.undoInfo(state=True)
            mesh = cmds.polyPlane(name="body", axis=(0, 0, 1), subdivisionsX=4, subdivisionsY=4,
                                 width=4, height=4)[0]
            joint = cmds.createNode("joint")
            cmds.skinCluster(joint, mesh, toSelectedBones=True)
            controller = cmds.createNode("transform", name="L_shoulder_CTL")
            # An R controller is deliberately absent; copying a shape in place
            # must not require or create another pose driver.
            cmds.setKeyframe(controller, attribute="rotateZ", time=0, value=45)
            cmds.setKeyframe(controller, attribute="rotateZ", time=10, value=0)
            cmds.currentTime(0)
            bs = tool.create_blendshape(mesh, order)
            index, name = tool.add_target(mesh, bs, controller)
            baseline = {v: cmds.pointPosition(mesh + ".vtx[%d]" % v, world=True) for v in (10, 12, 14)}
            cmds.move(.2, .7, .3, mesh + ".vtx[14]", relative=True, worldSpace=True)
            cmds.move(.1, .2, .4, mesh + ".vtx[10]", relative=True, worldSpace=True)
            cmds.move(0, .15, 0, mesh + ".vtx[12]", relative=True, worldSpace=True)
            tool.finish_edit()
            before = {v: cmds.pointPosition(mesh + ".vtx[%d]" % v, world=True) for v in (10, 12, 14)}
            record = tool.pose_record(bs, index)
            channels = cmds.getAttr(record + ".channels")
            driver = cmds.connectionInfo(bs + ".weight[%d]" % index, sourceFromDestination=True)
            anim = cmds.connectionInfo(controller + ".rotateZ", sourceFromDestination=True)
            nodes = set(cmds.ls())
            entries = tool.targets(bs)
            path = tool._delta_path(bs, mesh, index)
            original_points = cmds.getAttr(path + ".inputPointsTarget")
            original_components = cmds.getAttr(path + ".inputComponentsTarget")
            result = tool.mirror_target_shape(mesh, bs, index)
            assert result == (index, name)
            assert tool.targets(bs) == entries
            assert set(cmds.ls()) == nodes
            close(cmds.pointPosition(mesh + ".vtx[14]", world=True), before[14])
            close(cmds.pointPosition(mesh + ".vtx[12]", world=True), before[12])
            close(cmds.pointPosition(mesh + ".vtx[10]", world=True),
                  [baseline[10][0] - .2, baseline[10][1] + .7, baseline[10][2] + .3])
            assert cmds.connectionInfo(bs + ".weight[%d]" % index, sourceFromDestination=True) == driver
            assert cmds.connectionInfo(controller + ".rotateZ", sourceFromDestination=True) == anim
            assert cmds.getAttr(controller + ".rotateZ") == 45
            assert tool.pose_record(bs, index) == record
            assert cmds.getAttr(record + ".channels") == channels
            assert not tool.edit_session()
            cmds.undo()
            assert cmds.getAttr(path + ".inputPointsTarget") == original_points
            assert cmds.getAttr(path + ".inputComponentsTarget") == original_components
            for v in before:
                close(cmds.pointPosition(mesh + ".vtx[%d]" % v, world=True), before[v])
            tool.mirror_target_shape(mesh, bs, index, "R_to_L")
            close(cmds.pointPosition(mesh + ".vtx[10]", world=True), before[10])
            close(cmds.pointPosition(mesh + ".vtx[14]", world=True),
                  [baseline[14][0] - .1, baseline[14][1] + .2, baseline[14][2] + .4])
            assert tool.targets(bs) == entries
            # Native baked targets also work without this tool's pose metadata.
            cmds.delete(record)
            tool.mirror_target_shape(mesh, bs, index, "L_to_R")
            assert tool.targets(bs) == entries
            print("PASS", order, "same target, source/center preserved, destination replaced, SDK/animation unchanged, undo, reverse and unmanaged baked target")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
