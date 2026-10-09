"""Run with mayapy: chest and spine endpoint stretch/squash regression."""
import ast
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om


def create_controller(name, offset, parent=None, **kwargs):
    nodes = []
    for suffix in offset:
        node = cmds.createNode("transform", name=name + "_" + suffix)
        if nodes or parent:
            cmds.parent(node, nodes[-1] if nodes else parent, relative=True)
        nodes.append(node)
    ctl = cmds.circle(name=name + "_CTL", ch=False)[0]
    cmds.parent(ctl, nodes[-1], relative=True)
    return nodes, ctl


def run():
    maya.standalone.initialize(name="python")
    try:
        cmds.loadPlugin("lookdevKit", quiet=True)
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from maya_tools.scripts.utils import matrix_manager
        path = Path(__file__).resolve().parents[2] / "biped/autorig/spine_module.py"
        source = ast.parse(path.read_text(encoding="utf-8"))
        names = {"controller_creation", "local_hip_chest_setup", "chest_spine_curve_drivers", "ik_spine"}
        functions = [n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = {"cmds": cmds, "om": om, "math": math,
                 "curve_tool": SimpleNamespace(create_controller=create_controller,
                                               lock_attributes=lambda *args: None)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), scope)
        module_class = type("TestSpine", (), {name: scope[name] for name in names})
        for chest_guide in (False, True):
            cmds.file(new=True, force=True)
            module = module_class()
            module.side = "C"
            module.module_trn = cmds.createNode("transform", name="module")
            module.skeleton_grp = cmds.createNode("transform", name="skeleton")
            module.masterwalk_ctl = cmds.createNode("transform", name="masterwalk")
            cmds.addAttr(module.masterwalk_ctl, ln="globalScale", at="double", dv=1, k=True)
            for axis in "XYZ":
                cmds.connectAttr(module.masterwalk_ctl + ".globalScale", module.masterwalk_ctl + ".scale" + axis)
            module.controllers_grp = cmds.createNode("transform", name="controllers", p=module.masterwalk_ctl)
            module.spine_chain = []
            for i in range(5):
                joint = cmds.createNode("joint", name=f"C_spine{i:02d}_JNT",
                                        p=module.spine_chain[-1] if i else module.module_trn)
                cmds.setAttr(joint + ".translateY", 2 if i else 10)
                module.spine_chain.append(joint)
            module.body_guide_matrix = cmds.getAttr(module.spine_chain[0] + ".worldMatrix[0]")
            module.chest_guide_matrix = list(cmds.getAttr(module.spine_chain[-1] + ".worldMatrix[0]"))
            module.has_chest_guide = chest_guide
            if chest_guide:
                module.chest_guide_matrix[13] += 1
            module.spine_skinning_jnts = 5
            module.controller_creation()
            module.local_hip_chest_setup()
            module.ik_spine()
            cmds.setAttr(module.body_ctl + ".spineStretch", 1)
            cmds.setAttr(module.body_ctl + ".spineStretchMin", 0.1)
            cmds.setAttr(module.body_ctl + ".spineStretchMax", 3)
            factor = lambda: cmds.getAttr("C_spineStretchFactor_DIV.output")
            squash = lambda: cmds.getAttr("C_spineSquashFactor_DIV.output")
            baseline = factor()
            assert math.isclose(baseline, 1, abs_tol=1e-5), baseline
            for attr, value, direction in (("translateY", 1, 1), ("translateY", -1, -1),
                                           ("scaleY", 1.2, 1), ("scaleY", 0.8, -1)):
                cmds.setAttr(module.local_chest_ctl + "." + attr, value)
                measured = factor()
                assert (measured - baseline) * direction > 0.01, (attr, value, measured)
                assert (squash() - 1) * direction > 0.01, (attr, value, squash())
                cmds.setAttr(module.local_chest_ctl + "." + attr, 1 if attr.startswith("scale") else 0)
                assert math.isclose(factor(), baseline, abs_tol=1e-5)
            skin_joints = [f"C_spine{i:02d}Skinning_JNT" for i in range(1, 6)]
            for axis in "XZ":
                baseline_scales = [cmds.getAttr(joint + ".scale" + axis) for joint in skin_joints]
                cmds.setAttr(module.local_chest_ctl + ".scale" + axis, 1.5)
                for index, joint in enumerate(skin_joints):
                    weight = max(0, (index - 2) / 2)
                    assert math.isclose(cmds.getAttr(joint + ".scale" + axis),
                                        baseline_scales[index] * (1 + 0.5 * weight), abs_tol=1e-5)
                cmds.setAttr(module.local_chest_ctl + ".scale" + axis, 1)
            cmds.setAttr(module.spine_ctls[-1] + ".translateY", 1)
            endpoint_only = factor()
            assert endpoint_only > baseline
            cmds.setAttr(module.local_chest_ctl + ".translateY", 1)
            assert factor() > endpoint_only
            cmds.setAttr(module.local_chest_ctl + ".translateY", 0)
            cmds.setAttr(module.spine_ctls[-1] + ".translateY", 0)
            for follow in (0, 1):
                cmds.setAttr(module.spine_ctls[-1] + ".follow", follow)
                for scale in (0.5, 2):
                    cmds.setAttr(module.masterwalk_ctl + ".globalScale", scale)
                    assert math.isclose(factor(), baseline, abs_tol=1e-5), (follow, scale, factor())
                    cmds.setAttr(module.local_chest_ctl + ".translateY", 1)
                    assert factor() > baseline
                    cmds.setAttr(module.local_chest_ctl + ".translateY", 0)
            # Original chest follow still uses the solved tip and guide offset.
            # Local rotation stays independent; translation is not doubled.
            cmds.setAttr(module.masterwalk_ctl + ".globalScale", 1)
            nodes, attachment = create_controller("C_chestAttachment", ["GRP"])
            cmds.matchTransform(nodes[0], module.local_chest_ctl)
            attached_rest = cmds.getAttr(nodes[0] + ".worldMatrix[0]")
            cmds.xform(nodes[0], m=om.MMatrix.kIdentity)
            cmds.setAttr(nodes[0] + ".offsetParentMatrix", attached_rest, type="matrix")
            matrix_manager.space_switches(attachment, [module.local_chest_ctl, module.body_ctl],
                                          sources_names=["Chest", "Body"], base_ctl=module.masterwalk_ctl)
            for translation in (0, 1, -1):
                cmds.setAttr(module.local_chest_ctl + ".translateY", translation)
                before_rotation = factor()
                cmds.setAttr(module.local_chest_ctl + ".rotateX", 25)
                assert math.isclose(factor(), before_rotation, abs_tol=1e-5)
                original_follow = cmds.getAttr("C_localChest_BLM.outputMatrix")
                actual_chest = cmds.getAttr(module.local_chest_ctl + ".worldMatrix[0]")
                for index in (12, 13, 14):
                    assert math.isclose(original_follow[index], actual_chest[index], abs_tol=1e-5)
                actual_skin = cmds.getAttr("C_localChestSkinning_JNT.worldMatrix[0]")
                for a, b in zip(actual_skin, actual_chest):
                    assert math.isclose(a, b, abs_tol=1e-5)
                attached = cmds.xform(attachment, q=True, ws=True, t=True)
                assert all(math.isclose(a, b, abs_tol=1e-5)
                           for a, b in zip(attached, actual_chest[12:15])), (attached, actual_chest[12:15])
                cmds.setAttr(module.local_chest_ctl + ".rotateX", 0)
            cmds.setAttr(attachment + ".SpaceFollow", 1)
            independent = cmds.xform(attachment, q=True, ws=True, t=True)
            cmds.setAttr(module.local_chest_ctl + ".translateY", 2)
            assert all(math.isclose(a, b, abs_tol=1e-5)
                       for a, b in zip(independent, cmds.xform(attachment, q=True, ws=True, t=True)))
            cycles = cmds.cycleCheck(all=True, list=True) or []
            assert not cycles, cycles
            print(f"PASS chest_guide={chest_guide}: move/scale XYZ, squash, endpoint, globalScale, original chest follow/rotation/skin, dependent space switches, no cycles")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
