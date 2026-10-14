"""Real Maya: orientation drivers, IK/FK invariance, mirror and SKC recovery."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
from maya import cmds


def close(a, b, tolerance=2e-5):
    assert abs(a - b) < tolerance, (a, b)


def run():
    maya.standalone.initialize(name="python")
    try:
        from maya_tools.scripts.tools import orientation_correctives as orient
        from maya_tools.scripts.tools import pose_blendshapes as poses
        from maya_tools.scripts.tools.skin_manager_api import SkinManager
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)
        root = cmds.createNode("transform", name="Character")
        torso = cmds.createNode("transform", name="C_torso", parent=root)
        fk = cmds.createNode("transform", name="L_shoulder_CTL", parent=root)
        ik = cmds.createNode("transform", name="L_ik_CTL", parent=root)
        right = cmds.createNode("transform", name="R_shoulder_CTL", parent=root)
        joint = cmds.createNode("joint", name="L_shoulder_JNT", parent=torso)
        right_joint = cmds.createNode("joint", name="R_shoulder_JNT", parent=torso)
        cmds.connectAttr(right + ".rotate", right_joint + ".rotate")
        blend = cmds.createNode("blendColors")
        cmds.connectAttr(fk + ".rotate", blend + ".color1")
        cmds.connectAttr(ik + ".rotate", blend + ".color2")
        cmds.connectAttr(blend + ".output", joint + ".rotate")
        cmds.setAttr(blend + ".blender", 1)
        mesh = cmds.polySphere(name="body", subdivisionsX=12, subdivisionsY=8)[0]
        cmds.parent(mesh, root)
        cmds.skinCluster(joint, mesh, toSelectedBones=True)
        bs = poses.create_blendshape(mesh)
        system = orient.create_system(joint, torso, "L_shoulder_orientation")
        cmds.setAttr(fk + ".rotateZ", 45)
        index, name = poses.add_target(mesh, bs, fk, system)
        cmds.move(.1, 0, 0, mesh + ".vtx[4]", relative=True, objectSpace=True)
        poses.finish_edit()
        close(cmds.getAttr(bs + ".weight[%d]" % index), 1)
        record = poses.pose_record(bs, index)
        # A front pose gets its own sample; equal elevation must not conflate it.
        cmds.setAttr(fk + ".rotateZ", 0)
        cmds.setAttr(fk + ".rotateY", 45)
        front, _ = poses.add_target(mesh, bs, fk, system)
        poses.finish_edit(False)
        close(cmds.getAttr(bs + ".weight[%d]" % front), 1)
        close(cmds.getAttr(bs + ".weight[%d]" % index), 0)
        cmds.setAttr(fk + ".rotateY", 0)
        cmds.setAttr(ik + ".rotateZ", 45)
        cmds.setAttr(blend + ".blender", 0)
        close(cmds.getAttr(bs + ".weight[%d]" % index), 1)
        # Moving/rotating/scaling the whole character cannot change activation.
        cmds.setAttr(root + ".rotate", 31, -42, 19)
        cmds.setAttr(root + ".translate", 10, 3, -8)
        cmds.setAttr(root + ".scale", 2, 2, 2)
        close(cmds.getAttr(bs + ".weight[%d]" % index), 1)
        cmds.setAttr(ik + ".rotateZ", 0)
        close(cmds.getAttr(bs + ".weight[%d]" % index), 0)
        cmds.setAttr(root + ".rotate", 0, 0, 0)
        cmds.setAttr(root + ".translate", 0, 0, 0)
        cmds.setAttr(root + ".scale", 1, 1, 1)
        cmds.setAttr(blend + ".blender", 1)
        cmds.setAttr(fk + ".rotateZ", 45)
        # Failed duplicate conversion must restore the old driver and nodes.
        before = set(cmds.ls())
        try:
            orient.attach_target(system, bs, index, record)
            raise AssertionError("Duplicate pose accepted")
        except ValueError:
            pass
        assert before == set(cmds.ls())
        close(cmds.getAttr(bs + ".weight[%d]" % index), 1)
        mirrored, _ = poses.mirror_target(mesh, bs, index)
        r_record = poses.pose_record(bs, mirrored)
        assert orient.linked(r_record, "orientationSystem")
        poses.go_to_pose(bs, mirrored)
        close(cmds.getAttr(bs + ".weight[%d]" % mirrored), 1)
        poses.go_to_pose(bs, mirrored, neutral=True)
        cmds.setAttr(fk + ".rotateZ", 0)
        manager = SkinManager.__new__(SkinManager)
        manager.k_skin_attrs = ["skinningMethod", "normalizeWeights", "maintainMaxInfluences", "maxInfluences"]
        manager.tolerance = 1e-5
        with tempfile.TemporaryDirectory() as folder:
            scene = str(Path(folder) / "orientation.mb")
            cmds.file(rename=scene)
            cmds.file(save=True, type="mayaBinary", force=True)
            cmds.file(new=True, force=True)
            cmds.file(scene, open=True, force=True)
            cmds.setAttr(fk + ".rotateZ", 45)
            close(cmds.getAttr(bs + ".weight[%d]" % index), 1)
            cmds.setAttr(fk + ".rotateZ", 0)
            snapshot = str(Path(folder) / "orientation.skc")
            cmds.select(clear=True)
            manager.export_skins(snapshot)
            data = json.loads(Path(snapshot).read_text())
            assert len(data[manager.SCENE_DEFORMERS_KEY]["orientation_systems"]) == 2
            # A surviving region can lose just its hidden native helper. Keep
            # export strict, then recover samples and existing target clamps
            # from the saved snapshot without replacing the sculpted targets.
            regions = data[manager.SCENE_DEFORMERS_KEY]["orientation_systems"]
            cmds.delete(orient.linked(system, "helper"))
            try:
                orient.export_systems()
                raise AssertionError("Broken region was silently exported")
            except ValueError as error:
                assert "lost its interpolator" in str(error)
            node_map, warnings = {}, []
            orient.import_systems(regions, lambda n: n if cmds.objExists(n) else None,
                                  node_map, warnings)
            assert not warnings, warnings
            assert poses.pose_record(bs, index) == record
            cmds.setAttr(fk + ".rotateZ", 45)
            close(cmds.getAttr(bs + ".weight[%d]" % index), 1)
            cmds.setAttr(fk + ".rotateZ", 0)
            close(cmds.getAttr(bs + ".weight[%d]" % index), 0)
            recovered_nodes = set(cmds.ls())
            orient.import_systems(regions, lambda n: n if cmds.objExists(n) else None,
                                  {}, [])
            assert set(cmds.ls()) == recovered_nodes
            manager.export_skins(snapshot)
            # Native region plus sparse target deletion and undo.
            pi = orient.linked(system, "interpolator")
            count = len(cmds.getAttr(pi + ".pose", multiIndices=True))
            front_pose = cmds.getAttr(poses.pose_record(bs, front) + ".orientationPose")
            poses.remove_target(mesh, bs, front)
            assert not cmds.getAttr(pi + ".pose[%d].isEnabled" % front_pose)
            cmds.undo()
            assert len(cmds.getAttr(pi + ".pose", multiIndices=True)) == count
            assert cmds.getAttr(pi + ".pose[%d].isEnabled" % front_pose)
            cmds.delete(mesh, constructionHistory=True)
            for s in orient.systems():
                nodes = [orient.linked(s, a) for a in ("helper", "relative", "rotation")]
                cmds.delete([n for n in nodes + [s] if n and cmds.objExists(n)])
            cmds.delete([n for n in poses._find(poses.POSE_MARKER)])
            cmds.delete(cmds.ls(type="clamp") or [])
            manager.import_skins(snapshot, replace_existing=True)
            assert poses.pose_record(bs, index)
            assert len(orient.systems()) == 2
            for mode in ("off", "serial", "parallel"):
                cmds.evaluationManager(mode=mode)
                for y, z, expected in ((0, 0, 0), (0, 45, 1), (45, 0, 0)):
                    cmds.setAttr(fk + ".rotateY", y)
                    cmds.setAttr(fk + ".rotateZ", z)
                    close(cmds.getAttr(bs + ".weight[%d]" % index), expected)
            assert not (cmds.cycleCheck(all=True, list=True) or [])
        print("PASS orientation: front/side separation, IK/FK, global transforms, duplicate rollback, mirror, delete/undo, native reopen, SKC reconstruction, DG/Serial/Parallel", flush=True)
        # Separate swing and twist modes must ignore the other motion.
        cmds.file(new=True, force=True)
        reference = cmds.createNode("transform", name="reference")
        driver = cmds.createNode("joint", name="driver")
        control = cmds.createNode("transform", name="L_test_CTL")
        cmds.connectAttr(control + ".rotate", driver + ".rotate")
        mesh = cmds.polySphere()[0]
        cmds.skinCluster(driver, mesh, toSelectedBones=True)
        bs = poses.create_blendshape(mesh)
        system = orient.create_system(driver, reference)
        cmds.setAttr(control + ".rotateZ", 45)
        swing, _ = poses.add_target(mesh, bs, control, system, "swing")
        poses.finish_edit(False)
        cmds.setAttr(control + ".rotateX", 60)
        close(cmds.getAttr(bs + ".weight[%d]" % swing), 1)
        cmds.setAttr(control + ".rotate", 45, 0, 0)
        twist, _ = poses.add_target(mesh, bs, control, system, "twist")
        poses.finish_edit(False)
        cmds.setAttr(control + ".rotateZ", 60)
        close(cmds.getAttr(bs + ".weight[%d]" % twist), 1)
        print("PASS orientation: swing ignores axial twist; twist ignores swing", flush=True)
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
