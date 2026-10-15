"""Run with mayapy: Edward build counts, spine spacing and foot IK/FK outputs."""
import ast
import json
import math
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om

from test_spine_chest_stretch import create_controller

ROOT = Path(__file__).resolve().parents[4]


def load_spine(real_curves=False):
    path = ROOT / "maya_tools/scripts/biped/autorig/spine_module.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = next(node for node in tree.body if isinstance(node, ast.ClassDef)).body
    methods = [node for node in methods if isinstance(node, ast.FunctionDef)]
    scope = {"cmds": cmds, "om": om, "math": math,
             "curve_tool": SimpleNamespace(create_controller=create_controller,
                                           lock_attributes=lambda *args: None),
             "organize_module_nurbs": runpy.run_path(str(ROOT / "maya_tools/scripts/utils/module_nurbs.py"))["organize_module_nurbs"],
             "data_manager": SimpleNamespace(DataExportBiped=lambda: SimpleNamespace(append_data=lambda *args: None))}
    if real_curves:
        from maya_tools.scripts.utils import curve_tool
        scope["curve_tool"] = curve_tool
    guides = json.loads((ROOT / "maya_tools/assets/Edward/guides/Edward_v013.guides").read_text())["Edward"]

    def get_guides(name):
        names = [name] + guides[name].get("children", [])
        chain = []
        for guide in names:
            joint = cmds.createNode("joint", name=guide)
            cmds.xform(joint, ws=True, matrix=guides[guide]["joint_matrix"])
            cmds.makeIdentity(joint, apply=True, rotate=True)
            if chain:
                cmds.parent(joint, chain[-1])
            chain.append(joint)
        return chain

    scope["guides_manager"] = SimpleNamespace(get_guides=get_guides)
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), "exec"), scope)
    return type("TestSpine", (), {node.name: scope[node.name] for node in methods})


def check_spine(count, skinning_count, real_curves=False):
    cmds.file(new=True, force=True)
    cmds.optionVar(sv=("currentAssetRigName", "Edward"))
    spine_class = load_spine(real_curves)
    rig = spine_class.__new__(spine_class)
    rig.modules = cmds.createNode("transform", name="modules")
    rig.skel_grp = cmds.createNode("transform", name="skeleton")
    rig.masterwalk_ctl = cmds.createNode("transform", name="masterwalk")
    cmds.addAttr(rig.masterwalk_ctl, ln="globalScale", at="double", dv=1, k=True)
    rig.make("C", skinning_count, count)
    assert len(rig.spine_ctls) == count, (count, rig.spine_ctls)
    assert len(set(rig.spine_ctls)) == count
    start = om.MVector(cmds.xform(rig.spine_ctls[0], q=True, ws=True, t=True))
    end = om.MVector(cmds.xform(rig.spine_ctls[-1], q=True, ws=True, t=True))
    for index, ctl in enumerate(rig.spine_ctls):
        actual = om.MVector(cmds.xform(ctl, q=True, ws=True, t=True))
        expected = start + (end - start) * (index / float(count - 1))
        assert (actual - expected).length() < 1e-4, (count, index, actual, expected)
        # Every requested control must drive its own curve point after build.
        before = cmds.getAttr("C_spineIK_CRV.controlPoints[{}]".format(index))[0]
        cmds.setAttr(ctl + ".translateZ", 0.25)
        after = cmds.getAttr("C_spineIK_CRV.controlPoints[{}]".format(index))[0]
        assert max(abs(a - b) for a, b in zip(before, after)) > 0.1, (count, ctl)
        cmds.setAttr(ctl + ".translateZ", 0)
    assert cmds.getAttr("C_spineIK_CRV.controlPoints", size=True) == count
    assert len(cmds.ls("C_spine*Skinning_JNT", type="joint")) == skinning_count
    assert not (cmds.cycleCheck(all=True, list=True) or [])
    if count == 5:
        assert rig.spine_ctls == ["C_spine00_CTL", "C_spine01Tan_CTL", "C_spine03_CTL", "C_spine06Tan_CTL", "C_spine07_CTL"]
    if real_curves:
        assert all(cmds.listRelatives(ctl, shapes=True, type="nurbsCurve") for ctl in rig.spine_ctls)
        print("PASS production controller factory and Edward saved curve shapes", flush=True)
    print("PASS Edward spine: {} controls, uniform endpoints, live curve drivers, {} skin joints, no cycles".format(count, skinning_count), flush=True)


def matrix_close(actual, expected, label):
    assert max(abs(a - b) for a, b in zip(actual, expected)) < 1e-4, label


def check_foot(filename, side):
    from test_ik_fk_settings_match import check_module_inverse
    rig = check_module_inverse(filename, side, foot_skinning=True)
    names = [side + "_legAnkleSkinning_JNT", side + "_legBallSkinning_JNT"]
    if "custom" in filename:
        names.append(side + "_legToeSkinning_JNT")
    for joint in names:
        source = cmds.listConnections(joint + ".offsetParentMatrix", s=True, d=False, plugs=True)[0]
        assert cmds.nodeType(source.split(".")[0]) == "blendMatrix", (filename, joint, source)
    for scale in (1, 2):
        cmds.setAttr(rig.masterwalk_ctl + ".globalScale", scale)
        for weight in (0, 0.5, 1):
            cmds.setAttr(rig.settings_ctl + ".Ik_Fk", weight)
            for joint in names:
                source = cmds.listConnections(joint + ".offsetParentMatrix", s=True, d=False, plugs=True)[0]
                matrix_close(cmds.getAttr(joint + ".worldMatrix[0]"), cmds.getAttr(source), (filename, side, scale, weight, joint))
        # IK foot roll and translation must not move the FK deforming foot.
        before = [cmds.getAttr(joint + ".worldMatrix[0]") for joint in names]
        old_roll = cmds.getAttr(rig.ik_controllers[0] + ".Roll")
        old_x = cmds.getAttr(rig.ik_controllers[0] + ".translateX")
        cmds.setAttr(rig.ik_controllers[0] + ".Roll", old_roll + 30)
        cmds.setAttr(rig.ik_controllers[0] + ".translateX", old_x + 3)
        for joint, expected in zip(names, before):
            matrix_close(cmds.getAttr(joint + ".worldMatrix[0]"), expected, (filename, side, joint, "FK isolation"))
        cmds.setAttr(rig.ik_controllers[0] + ".Roll", old_roll)
        cmds.setAttr(rig.ik_controllers[0] + ".translateX", old_x)
        ball = side + "_legBallSkinning_JNT"
        before_ball = cmds.getAttr(ball + ".worldMatrix[0]")
        old_rotation = cmds.getAttr(rig.fk_controllers[-1] + ".rotateZ")
        cmds.setAttr(rig.fk_controllers[-1] + ".rotateZ", old_rotation + 20)
        assert max(abs(a - b) for a, b in zip(before_ball, cmds.getAttr(ball + ".worldMatrix[0]"))) > 0.1
        if "custom" in filename:
            matrix_close(cmds.getAttr(ball + ".worldMatrix[0]"), cmds.getAttr(rig.fk_controllers[-1] + ".worldMatrix[0]"), "Custom ball FK")
            expected_toe = (om.MMatrix(cmds.getAttr(rig.guides_matrices[-1])) *
                            om.MMatrix(cmds.getAttr(rig.guides_matrices[-2])).inverse() *
                            om.MMatrix(cmds.getAttr(rig.fk_controllers[-1] + ".worldMatrix[0]")))
            matrix_close(cmds.getAttr(names[-1] + ".worldMatrix[0]"), list(expected_toe), "Custom toe FK")
        cmds.setAttr(rig.fk_controllers[-1] + ".rotateZ", old_rotation)
    assert not (cmds.cycleCheck(all=True, list=True) or [])
    print("PASS foot: {}, {}, every skin output blended, IK/FK/intermediate, global scale, FK isolation".format(filename, side), flush=True)


def run():
    maya.standalone.initialize(name="python")
    try:
        sys.path.insert(0, str(ROOT))
        cmds.loadPlugin("matrixNodes", quiet=True)
        cmds.loadPlugin("lookdevKit", quiet=True)
        build = json.loads((ROOT / "maya_tools/assets/Edward/build/Edward_v001.build").read_text())
        for count in (3, 4, 5, build["spine_controllers"], 7, 10):
            check_spine(count, build["spine_skinning_jnts"])
        check_spine(build["spine_controllers"], build["spine_skinning_jnts"], real_curves=True)
        for filename in ("leg_module.py", "leg_module_custom.py"):
            for side in ("L", "R"):
                check_foot(filename, side)
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
