"""Run with mayapy: IK joint/matrix sources, mirrored limbs, offsets and reload."""
import ast
import math
import os
import sys
import tempfile
import runpy
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om


def assert_pose(controls, blends):
    for ctl, blend in zip(controls, blends):
        actual = cmds.getAttr(ctl + ".worldMatrix[0]")
        expected = cmds.getAttr(blend[0] + ".inputMatrix")
        assert max(abs(a - b) for a, b in zip(actual, expected)) < 1e-5, (ctl, actual, expected)
        assert all(cmds.getAttr(ctl + ".translate" + axis, lock=True) for axis in "XYZ")


def build(count, mirrored, matrix_only):
    from maya_tools.scripts.utils import ik_fk_match
    cmds.file(new=True, force=True)
    master = cmds.createNode("transform", name="master")
    cmds.setAttr(master + ".translate", 6, 3, -2)
    cmds.setAttr(master + ".rotate", 12, 30, -16)
    cmds.setAttr(master + ".scale", 2.5, 2.5, 2.5)
    settings = cmds.createNode("transform", name="settings_CTL")
    cmds.addAttr(settings, ln="Ik_Fk", at="double", min=0, max=1, dv=0, k=True)
    controls, blends = [], []
    sign = -1 if mirrored else 1
    for i in range(count):
        group = cmds.createNode("transform", name="fk{}_GRP".format(i), p=controls[-1] if controls else master)
        cmds.setAttr(group + ".translateX", sign * 4 if i else 0)
        offset = cmds.createNode("transform", name="fk{}_ANM".format(i), p=group)
        ctl = cmds.createNode("transform", name="fk{}_CTL".format(i), p=offset)
        cmds.setAttr(ctl + ".rotateOrder", i % 6)
        for axis in "XYZ":
            cmds.setAttr(ctl + ".translate" + axis, lock=True)
        if controls:
            cmds.addAttr(controls[-1], ln="Stretch", at="double", min=0, dv=1, k=True)
            stretch = cmds.createNode("multiplyDivide")
            cmds.setAttr(stretch + ".input2X", sign * 4)
            cmds.connectAttr(controls[-1] + ".Stretch", stretch + ".input1X")
            cmds.connectAttr(stretch + ".outputX", group + ".translateX", force=True)
        source = cmds.createNode("transform" if matrix_only else "joint", name="ik{}".format(i), p=master)
        cmds.setAttr(source + ".translate", sign * (i * 5 + 1), 2 + i * i, -3 + i)
        cmds.setAttr(source + ".rotate", 23 + i * 17, -31 + i * 6, 48 - i * 25)
        blend = cmds.createNode("blendMatrix")
        if matrix_only:
            matrix = cmds.createNode("multMatrix")
            cmds.connectAttr(source + ".worldMatrix[0]", matrix + ".matrixIn[0]")
            cmds.connectAttr(matrix + ".matrixSum", blend + ".inputMatrix")
        else:
            cmds.connectAttr(source + ".worldMatrix[0]", blend + ".inputMatrix")
        cmds.connectAttr(ctl + ".worldMatrix[0]", blend + ".target[0].targetMatrix")
        cmds.connectAttr(settings + ".Ik_Fk", blend + ".target[0].weight")
        controls.append(ctl)
        blends.append([blend])
    ik_fk_match.setup(settings, controls, blends)
    return settings, controls, blends


def check_module_inverse(filename, side, foot_skinning=False):
    """Exercise the actual limb controller, stretch, pin and IK construction."""
    from maya_tools.scripts.utils import ik_fk_match, matrix_manager, guides_manager, custom_ik_solver, ribbon
    from test_spine_chest_stretch import create_controller as basic_controller
    def lock(ctl, attrs):
        for attr in attrs:
            cmds.setAttr(ctl + "." + attr, lock=True, keyable=False)
    def controller(name, offset, parent=None, locked_attrs=None, match=None):
        nodes, ctl = basic_controller(name, offset, parent)
        if match:
            cmds.matchTransform(nodes[0], match, pos=True, rot=True)
        lock(ctl, locked_attrs or [])
        return nodes, ctl
    cmds.file(new=True, force=True)
    scope = {"cmds": cmds, "om": om, "math": math, "matrix_manager": matrix_manager,
             "custom_ik_solver": custom_ik_solver, "ribbon": ribbon,
             "curve_tool": SimpleNamespace(create_controller=controller, lock_attributes=lock)}
    scope['organize_module_nurbs'] = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / 'utils/module_nurbs.py'))['organize_module_nurbs']
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "biped", "autorig", filename)
    with open(path, encoding="utf-8") as source:
        tree = ast.parse(source.read())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    functions = [n for n in cls.body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), scope)
    limb_class = type("TestLimb", (), {n.name: scope[n.name] for n in functions})
    rig = limb_class.__new__(limb_class)
    rig.side = side
    leg = filename.startswith("leg")
    custom = "custom" in filename
    limb = "leg" if leg else "arm"
    sign = -1 if side == "R" else 1
    rig.module_name = side + "_" + limb
    rig.masterwalk_ctl = cmds.createNode("transform", name="C_masterwalk_CTL")
    cmds.addAttr(rig.masterwalk_ctl, ln="globalScale", at="double", dv=1, k=True)
    for axis in "XYZ":
        cmds.connectAttr(rig.masterwalk_ctl + ".globalScale", rig.masterwalk_ctl + ".scale" + axis)
    rig.local_hip_ctl = rig.masterwalk_ctl
    rig.module_trn = cmds.createNode("transform", name="module")
    rig.skeleton_grp = cmds.createNode("transform", name="skeleton")
    rig.controllers_grp = cmds.createNode("transform", name="controllers", p=rig.masterwalk_ctl)
    rig.primaryInputAxis = rig.primary_axis = (sign, 0, 0)
    rig.secondaryInputAxis = (0, 0, sign)
    rig.secondary_axis = (0, -sign, 0)
    rig.aim_axis_signed = "x" if sign > 0 else "-x"
    rig.up_axis_signed = "y"
    rig.settings_loc = cmds.spaceLocator(name="settings_LOC")[0]
    points = [(0, 0, 0), (5 * sign, 2, 0), (10 * sign, 0, 0)]
    if leg:
        points.extend([(12 * sign, 0, 0), (14 * sign, 0, 0)])
    names = ["hip", "knee", "ankle", "ball", "tip"] if leg else ["shoulder", "elbow", "wrist"]
    chain = []
    for name, point in zip(names, points):
        joint = cmds.createNode("joint", name=side + "_" + name + "_JNT")
        cmds.xform(joint, ws=True, t=point)
        chain.append(joint)
    rig.guides_matrices, rig.guides_trns = guides_manager.orient_guides(
        chain, rig.primary_axis, rig.secondary_axis if leg else rig.secondaryInputAxis)
    for joint, matrix in zip(chain, rig.guides_matrices):
        cmds.xform(joint, ws=True, matrix=cmds.getAttr(matrix))
    for parent, child in zip(chain, chain[1:]):
        cmds.parent(child, parent)
    if leg:
        rig.leg_chain = chain
        for attr, point in (("bank_out_loc", (10 * sign, 0, 1)),
                            ("bank_in_loc", (10 * sign, 0, -1)), ("heel_loc", (9 * sign, 0, 0))):
            loc = cmds.spaceLocator()[0]
            cmds.xform(loc, ws=True, t=point)
            setattr(rig, attr, loc)
    else:
        rig.arm_chain = chain
    rig.create_chains()
    rig.controllers_creation()
    rig.fk_stretch()
    rig.ik_setup()
    if not custom:
        rig.soft_ik()
    getattr(rig, "knee_pin_setup" if leg else "elbow_pin_setup")()
    if leg:
        rig.foot_attributes()
        if foot_skinning:
            rig.de_boor_ribbon(5)
    root = rig.root_ik_ctl if leg else rig.ik_root_ctl
    end = rig.ik_controllers[0] if leg else rig.ik_wrist_ctl
    ik_fk_match.setup(rig.settings_ctl, rig.fk_controllers, rig.blend_matrices,
                      ik_root=root, ik_end=end, pv=rig.pv_ctl,
                      foot_controls=rig.ik_controllers if leg else None,
                      guides=rig.guides_matrices, master=rig.masterwalk_ctl, custom_foot=custom,
                      refine_middle=custom)
    cmds.delete(chain[0])  # The production build deletes the guide joint chain.
    cmds.setAttr(rig.settings_ctl + ".Ik_Fk", 1)
    cmds.setAttr(rig.fk_controllers[0] + ".rotateZ", 25)
    cmds.setAttr(rig.fk_controllers[1] + ".rotateZ", -35)
    cmds.setAttr(rig.fk_controllers[0] + ".Stretch", 1.3)
    cmds.setAttr(rig.fk_controllers[1] + ".Stretch", 0.8)
    for scale in (1, 2):
        cmds.setAttr(rig.masterwalk_ctl + ".globalScale", scale)
        expected = [cmds.xform(ctl, q=True, ws=True, t=True) for ctl in rig.fk_controllers]
        before = cmds.xform(end, q=True, ws=True, matrix=True)
        cmds.undoInfo(state=True)
        ik_fk_match.match_fk_to_ik(rig.settings_ctl)
        actual = [cmds.getAttr(blend[0] + ".inputMatrix")[12:15] for blend in rig.blend_matrices]
        for index, (a, b) in enumerate(zip(actual, expected)):
            assert max(abs(x-y) for x, y in zip(a, b)) < 1e-3, (filename, side, scale, index, a, b)
        assert cmds.getAttr(rig.settings_ctl + ".Ik_Fk") == 0
        cmds.undo()
        assert max(abs(a-b) for a, b in zip(before, cmds.xform(end, q=True, ws=True, matrix=True))) < 1e-5
        cmds.redo()
        assert cmds.getAttr(rig.settings_ctl + ".Ik_Fk") == 0
        cmds.setAttr(rig.settings_ctl + ".Match_Fk_To_Ik", 1)
        ik_fk_match._trigger(cmds.ls(rig.settings_ctl, uuid=True)[0], "Match_Fk_To_Ik")
        assert cmds.getAttr(rig.settings_ctl + ".Match_Fk_To_Ik") == 0
    print("PASS actual FK to IK", filename, side)
    if filename == "leg_module_custom.py" and side == "R":
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "inverse_match.ma")
            cmds.file(rename=path)
            cmds.file(save=True, type="mayaAscii", force=True)
            cmds.file(path, open=True, force=True)
            script = next(n for n in cmds.ls(type="script")
                          if cmds.attributeQuery("ikFkMatchSettings", node=n, exists=True))
            exec(cmds.getAttr(script + ".before"), {})
            ik_fk_match.match_fk_to_ik(rig.settings_ctl)
            for ctl, blend in zip(rig.fk_controllers, rig.blend_matrices):
                expected = cmds.xform(ctl, q=True, ws=True, t=True)
                actual = cmds.getAttr(blend[0] + ".inputMatrix")[12:15]
                assert max(abs(a-b) for a, b in zip(actual, expected)) < 1e-3
        print("PASS inverse save/reload")
    return rig


def run():
    maya.standalone.initialize(name="python")
    try:
        cmds.loadPlugin("matrixNodes", quiet=True)
        cmds.loadPlugin("lookdevKit", quiet=True)
        root = Path(__file__).resolve().parents[4]
        sys.path.insert(0, str(root))
        from maya_tools.scripts.utils import ik_fk_match
        for filename in ("arm_module.py", "arm_module_custom.py", "leg_module.py", "leg_module_custom.py"):
            tree = ast.parse((root / "maya_tools/scripts/biped/autorig" / filename).read_text(encoding="utf-8"))
            calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                     and n.func.value.id == "ik_fk_match" and n.func.attr == "setup"]
            assert len(calls) == 1, filename
        for count in (3, 4):
            for mirrored in (False, True):
                for matrix_only in (False, True):
                    settings, controls, blends = build(count, mirrored, matrix_only)
                    cmds.undoInfo(state=True)
                    initial = [cmds.getAttr(c + ".worldMatrix[0]") for c in controls]
                    ik_fk_match.match_ik_to_fk(settings)
                    assert_pose(controls, blends)
                    assert cmds.getAttr(settings + ".Ik_Fk") == 1
                    cmds.undo()
                    for ctl, expected in zip(controls, initial):
                        assert max(abs(a-b) for a, b in zip(cmds.getAttr(ctl + ".worldMatrix[0]"), expected)) < 1e-5
                    cmds.redo()
                    assert_pose(controls, blends)
                    # A second action must be repeatable without accumulating offsets.
                    for i in range(count):
                        cmds.setAttr("ik{}.translateY".format(i), 8 - i)
                    settings = cmds.rename(settings, "renamed_settings_CTL")
                    cmds.setAttr(settings + ".Match_Ik_To_Fk", 1)
                    ik_fk_match._trigger(cmds.ls(settings, uuid=True)[0])
                    assert_pose(controls, blends)
                    assert cmds.getAttr(settings + ".Match_Ik_To_Fk") == 0
                    # Reject an unavailable channel before making any edits.
                    cmds.setAttr(controls[-1] + ".rotateX", lock=True)
                    before = [cmds.getAttr(c + ".worldMatrix[0]") for c in controls]
                    try:
                        ik_fk_match.match_ik_to_fk(settings)
                        raise AssertionError("Locked rotation should reject the match")
                    except RuntimeError:
                        pass
                    assert before == [cmds.getAttr(c + ".worldMatrix[0]") for c in controls]
                    cmds.setAttr(controls[-1] + ".rotateX", lock=False)
                    print("PASS", count, mirrored, matrix_only)
        # The embedded runtime must execute without importing the autorig package.
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "match.ma")
            cmds.file(rename=path)
            cmds.file(save=True, type="mayaAscii", force=True)
            cmds.file(path, open=True, force=True)
            script = next(n for n in cmds.ls(type="script")
                          if cmds.attributeQuery("ikFkMatchSettings", node=n, exists=True))
            source = cmds.getAttr(script + ".before")
            assert "maya_tools" not in source
            exec(source, {})
            ik_fk_match.match_ik_to_fk(settings)
            assert_pose(controls, blends)
        print("PASS save/reload and self-contained runtime (scriptJob events require interactive Maya)")
        for filename in ("arm_module.py", "arm_module_custom.py", "leg_module.py", "leg_module_custom.py"):
            for side in ("L", "R"):
                check_module_inverse(filename, side)
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
