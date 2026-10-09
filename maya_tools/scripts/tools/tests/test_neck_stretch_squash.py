"""Run with mayapy: real neck ribbon, volume, head and space-switch checks."""
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
from test_spine_chest_stretch import create_controller


def run():
    maya.standalone.initialize(name="python")
    try:
        cmds.loadPlugin("matrixNodes", quiet=True)
        scripts = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(scripts.parents[1]))
        from maya_tools.scripts.utils import ribbon, matrix_manager
        path = scripts / "biped/autorig/neck_module_de_boor.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {"controller_creation", "neck_stretch_setup", "ribbon_setup", "neck_squash_setup",
                 "local_head", "head_squash_setup"}
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = {"cmds": cmds, "om": om, "math": math, "ribbon": ribbon,
                 "matrix_manager": matrix_manager,
                 "curve_tool": SimpleNamespace(create_controller=create_controller,
                                               lock_attributes=lambda *args: None)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), scope)
        module_class = type("TestNeck", (), {name: scope[name] for name in names})
        cmds.file(new=True, force=True)
        rig = module_class()
        rig.side = "C"
        rig.module_trn = cmds.createNode("transform", name="module")
        rig.skeleton_grp = cmds.createNode("transform", name="skeleton")
        rig.masterwalk_ctl = cmds.createNode("transform", name="C_masterwalk_CTL")
        cmds.addAttr(rig.masterwalk_ctl, ln="globalScale", at="double", dv=1, k=True)
        for axis in "XYZ":
            cmds.connectAttr(rig.masterwalk_ctl + ".globalScale", rig.masterwalk_ctl + ".scale" + axis)
        rig.controllers_grp = cmds.createNode("transform", name="controllers", p=rig.masterwalk_ctl)
        base = cmds.createNode("joint", name="C_neck00_JNT", p=rig.module_trn)
        cmds.setAttr(base + ".translateY", 20)
        head = cmds.createNode("joint", name="C_neck01_JNT", p=base)
        cmds.setAttr(head + ".translateY", 5)
        rig.neck_chain = [base, head]
        rig.neck_guide_matrix = cmds.getAttr(base + ".worldMatrix[0]")
        rig.head_guide_matrix = cmds.getAttr(head + ".worldMatrix[0]")
        rig.controller_creation()
        rig.neck_stretch_setup()
        rig.ribbon_setup(5)
        rig.local_head()
        rig.head_squash_setup()
        ctl, head_ctl = rig.neck_ctls
        assert ctl == "C_neck_CTL"
        distance = lambda: (om.MVector(*cmds.xform(rig.output_joints[-1], q=True, ws=True, t=True))
                            - om.MVector(*cmds.xform(rig.output_joints[0], q=True, ws=True, t=True))).length()
        for ty, expected in ((0, 1), (0.5, 1.1), (-0.5, 0.9), (5, 1.2), (-4, 0.8)):
            cmds.setAttr(head_ctl + ".translateY", ty)
            assert math.isclose(cmds.getAttr(rig.neck_stretch_factor), expected, abs_tol=1e-5)
            assert math.isclose(distance(), 5 * expected, abs_tol=1e-5), (ty, distance())
            for joint in rig.output_joints:
                sx, sy, sz = [cmds.getAttr(joint + ".scale" + axis) for axis in "XYZ"]
                assert math.isclose(sy, expected, abs_tol=1e-5)
                assert math.isclose(sx * sy * sz, 1, abs_tol=1e-5)
            assert math.isclose(cmds.getAttr(rig.head_skinning_jnt + ".scaleY"), 1)
            head_position = cmds.xform(rig.head_skinning_jnt, q=True, ws=True, t=True)
            face_position = cmds.xform(rig.face_controls_parent, q=True, ws=True, t=True)
            assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(head_position, face_position))
            matrix = om.MMatrix(cmds.getAttr(rig.head_skinning_jnt + ".worldMatrix[0]"))
            assert math.isclose(om.MVector(matrix[0], matrix[1], matrix[2]).length(), 1, abs_tol=1e-5)
        cmds.setAttr(ctl + ".neckStretch", 0)
        assert math.isclose(distance(), 5, abs_tol=1e-5)
        cmds.setAttr(ctl + ".neckStretch", 1)
        cmds.setAttr(ctl + ".volumePreservation", 0)
        assert math.isclose(cmds.getAttr(rig.output_joints[2] + ".scaleX"), 1)
        cmds.setAttr(ctl + ".volumePreservation", 1)
        cmds.setAttr(ctl + ".neckFalloff", 1)
        assert math.isclose(cmds.getAttr(rig.output_joints[0] + ".scaleX"), 1)
        assert math.isclose(cmds.getAttr(rig.output_joints[-1] + ".scaleX"), 1)
        assert cmds.getAttr(rig.output_joints[2] + ".scaleX") > 1
        cmds.setAttr(ctl + ".neckFalloff", 0)
        cmds.setAttr(head_ctl + ".translateY", 0.5)
        for scale in (0.5, 2):
            cmds.setAttr(rig.masterwalk_ctl + ".globalScale", scale)
            assert math.isclose(cmds.getAttr(rig.neck_stretch_factor), 1.1, abs_tol=1e-5)
            assert math.isclose(distance(), 5.5 * scale, abs_tol=1e-5)
        cmds.setAttr(rig.face_ctl + ".translateY", 1)
        assert cmds.getAttr(rig.head_skinning_jnt + ".scaleY") > 1
        assert not (cmds.cycleCheck(all=True, list=True) or [])
        print("PASS: real neck ribbon, stretch limits/on-off, exact volume/falloff, independent head squash, globalScale, no cycles")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
