"""Run with mayapy: real neck/head deformation, eye aim, skinning and ENV joints."""
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


def methods(path, names, scope):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    return type("TestModule", (), {name: scope[name] for name in names})


def matrix(node):
    return om.MMatrix(cmds.getAttr(node + ".worldMatrix[0]"))


def assert_matrix(actual, expected):
    assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(actual, expected)), (actual, expected)


def run():
    maya.standalone.initialize(name="python")
    try:
        cmds.loadPlugin("matrixNodes", quiet=True)
        scripts = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(scripts.parents[1]))
        from maya_tools.scripts.utils import ribbon, matrix_manager
        scope = {"cmds": cmds, "om": om, "math": math, "ribbon": ribbon,
                 "matrix_manager": matrix_manager,
                 "curve_tool": SimpleNamespace(create_controller=create_controller,
                                               lock_attributes=lambda *args: None),
                 "guides_manager": SimpleNamespace(get_guides=lambda *args: []),
                 "data_manager": SimpleNamespace(DataExportBiped=lambda: SimpleNamespace(
                     get_data=lambda *args: None))}
        Neck = methods(scripts / "biped/autorig/neck_module_de_boor.py",
                       {"controller_creation", "neck_stretch_setup", "ribbon_setup",
                        "neck_squash_setup", "local_head", "head_squash_setup"}, scope)
        Eye = methods(scripts / "biped/autorig/eyelid_module.py",
                      {"create_main_eye_setup", "eye_direct"}, scope)
        methods(scripts / "utils/rig_manager.py", {"parented_chain"}, scope)
        cmds.file(new=True, force=True)
        neck = Neck()
        neck.side = "C"
        neck.module_trn = cmds.createNode("transform", name="module")
        neck.skeleton_grp = cmds.createNode("transform", name="skeleton")
        neck.masterwalk_ctl = cmds.createNode("transform", name="C_masterwalk_CTL")
        cmds.addAttr(neck.masterwalk_ctl, ln="globalScale", at="double", dv=1, k=True)
        for axis in "XYZ":
            cmds.connectAttr(neck.masterwalk_ctl + ".globalScale", neck.masterwalk_ctl + ".scale" + axis)
        neck.controllers_grp = cmds.createNode("transform", name="controllers", p=neck.masterwalk_ctl)
        base = cmds.createNode("joint", name="C_neck00_JNT", p=neck.module_trn)
        cmds.setAttr(base + ".translateY", 20)
        head = cmds.createNode("joint", name="C_neck01_JNT", p=base)
        cmds.setAttr(head + ".translateY", 5)
        neck.neck_chain = [base, head]
        neck.neck_guide_matrix = cmds.getAttr(base + ".worldMatrix[0]")
        neck.head_guide_matrix = cmds.getAttr(head + ".worldMatrix[0]")
        neck.controller_creation()
        neck.neck_stretch_setup()
        neck.ribbon_setup(5)
        neck.local_head()
        neck.head_squash_setup()
        cmds.addAttr(neck.face_ctl, ln="Eyes", at="long", dv=2)
        eyes = []
        for side, x in (("L", 3), ("R", -3)):
            eye = Eye()
            eye.side = side
            eye.surface = False
            eye.head_ctl = neck.neck_ctls[-1]
            eye.head_skinning_jnt = neck.head_skinning_jnt
            eye.head_guide_matrix = neck.head_guide_matrix
            eye.face_ctl = neck.face_ctl
            eye.face_controls_parent = neck.face_controls_parent
            eye.controllers_grp = cmds.createNode("transform", name=side + "_controllers", p=neck.face_controls_parent)
            eye.extra_controllers_grp = cmds.createNode("transform", p=eye.controllers_grp)
            eye.skeleton_grp = cmds.createNode("transform", name=side + "_skeleton", p=neck.skeleton_grp)
            # Ensure world-driven eye joints don't double their skeleton parent.
            cmds.setAttr(eye.skeleton_grp + ".translate", 11, -3, 7)
            cmds.setAttr(eye.skeleton_grp + ".rotate", 15, 27, -8)
            cmds.setAttr(eye.skeleton_grp + ".scale", 2, 2, 2)
            guide = cmds.createNode("transform")
            cmds.setAttr(guide + ".translate", x, 27, 4)
            cmds.setAttr(guide + ".rotate", 5, 12 if side == "L" else -12, 0)
            eye.eye_guide_matrix = list(matrix(guide))
            cmds.delete(guide)
            eye.primary_controller = []
            eye.secondary_controller = []
            eye.create_main_eye_setup()
            eye.eye_direct()
            env = scope["parented_chain"]([eye.eye_skinning_jnt], neck.head_skinning_jnt)[0]
            mesh = cmds.polySphere(name=side + "_eyeMesh", radius=1, subdivisionsX=8, subdivisionsY=6)[0]
            cmds.xform(mesh, ws=True, m=eye.eye_guide_matrix)
            cmds.skinCluster(eye.eye_skinning_jnt, mesh, tsb=True, skinMethod=0)
            selection = om.MSelectionList()
            selection.add(mesh)
            path = selection.getDagPath(0)
            path.extendToShape()
            eye.mesh_fn = om.MFnMesh(path)
            eye.bind_points = eye.mesh_fn.getPoints(om.MSpace.kWorld)
            eye.bind_inverse = matrix(eye.eye_skinning_jnt).inverse()
            eyes.append((eye, env))

        cases = [(0, 0, 1, 1), (5, 0, 1, 1), (-4, 0, 1, 1),
                 (0.5, -2, 1, 1), (-0.5, 2, 1, 1), (5, -2, 0, 0.5),
                 (-4, 2, 2, 2), (0.5, -4.5, 1, 2)]
        for mode in ("off", "parallel"):
            cmds.evaluationManager(mode=mode)
            for stretch, squash, volume, global_scale in cases:
                cmds.setAttr(neck.neck_ctls[-1] + ".translateY", stretch)
                cmds.setAttr(neck.neck_ctls[-1] + ".rotate", -12, 35, 21)
                cmds.setAttr(neck.face_ctl + ".translateY", squash)
                cmds.setAttr(neck.face_ctl + ".Volume", volume)
                cmds.setAttr(neck.masterwalk_ctl + ".globalScale", global_scale)
                for eye, env in eyes:
                    actual = matrix(eye.eye_skinning_jnt)
                    eye_local = om.MMatrix(eye.eye_guide_matrix) * om.MMatrix(neck.head_guide_matrix).inverse()
                    expected_center = om.MPoint(*list(eye_local)[12:15]) * matrix(neck.head_skinning_jnt)
                    actual_center = om.MPoint(*list(actual)[12:15])
                    assert (expected_center - actual_center).length() < 1e-5
                    direction = om.MVector(actual[8], actual[9], actual[10]).normal()
                    target = om.MPoint(*cmds.xform(eye.side_aim_ctl, q=True, ws=True, t=True))
                    assert (direction - (target - actual_center).normal()).length() < 1e-5
                    local_aim = om.MMatrix(cmds.getAttr(eye.side + "_eyeDirectEye_AIM.outputMatrix"))
                    assert_matrix(actual, local_aim * matrix(neck.head_skinning_jnt))
                    assert_matrix(matrix(env), actual)
                    for bind, result in zip(eye.bind_points, eye.mesh_fn.getPoints(om.MSpace.kWorld)):
                        assert (result - bind * eye.bind_inverse * actual).length() < 1e-5

            # Direct rotation is preserved before the head deformation matrix.
            for eye, env in eyes:
                cmds.setAttr(eye.eye_direct_ctl + ".rotate", 10, -17, 5)
                ctl_local = om.MMatrix(cmds.getAttr(eye.eye_direct_ctl + ".matrix"))
                local_aim = om.MMatrix(cmds.getAttr(eye.side + "_eyeDirectEye_AIM.outputMatrix"))
                assert_matrix(matrix(eye.eye_skinning_jnt), ctl_local * local_aim * matrix(neck.head_skinning_jnt))
                cmds.setAttr(eye.eye_direct_ctl + ".rotate", 0, 0, 0)
        assert not (cmds.cycleCheck(all=True, list=True) or [])
        print("PASS: L/R eyes follow bounded neck, head squash/Volume, gaze, direct rotation, globalScale, skin and ENV; DG/parallel; no cycles")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
