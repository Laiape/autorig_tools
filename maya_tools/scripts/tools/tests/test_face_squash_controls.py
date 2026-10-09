"""Run with mayapy: validate channel visibility and the face squash driver.

Extract the production functions to avoid loading character assets or modifying
the build cache. Maya evaluates the actual nodes and transform hierarchy.
"""
import ast
import math
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")

import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om

SCRIPTS = Path(__file__).resolve().parents[2]


def load_functions(path, names, scope):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), scope)
    return scope


def test_rotate_order(curve_tool):
    cmds.file(new=True, force=True)
    create = curve_tool.create_controller
    lock = curve_tool.lock_attributes
    _, ctl = create("free", locked_attrs=["sx", "sy", "sz", "v"])
    assert cmds.getAttr(ctl + ".rotateOrder", channelBox=True)
    lock(ctl, ["rx"])
    assert cmds.getAttr(ctl + ".rotateOrder", channelBox=True)
    lock(ctl, ["rotateY", "rz"])
    assert not cmds.getAttr(ctl + ".rotateOrder", channelBox=True)
    assert not cmds.getAttr(ctl + ".rotateOrder", keyable=True)

    for index, attrs in enumerate([
        ["rx", "ry", "rz"], ["rotateX", "rotateY", "rotateZ"],
        ["rotateX", "ry", "rotateZ"],
        ["rotate"], ["rotateOrder"],
    ]):
        _, ctl = create("locked" + str(index), locked_attrs=attrs)
        assert not cmds.getAttr(ctl + ".rotateOrder", channelBox=True), attrs

    _, ctl = create("explicit", locked_attrs=["rotateOrder"])
    lock(ctl, ["v"])
    assert cmds.getAttr(ctl + ".rotateOrder", lock=True)
    assert not cmds.getAttr(ctl + ".rotateOrder", channelBox=True)

    # Existing channels displayed but not keyable still count as visible.
    ctl = cmds.createNode("transform", name="channel_box_rotation")
    for axis in "xyz":
        cmds.setAttr(ctl + ".r" + axis, keyable=False, channelBox=False)
    cmds.setAttr(ctl + ".rx", channelBox=True)
    lock(ctl, [])
    assert cmds.getAttr(ctl + ".rotateOrder", channelBox=True)
    lock(ctl, ["rx"])
    assert not cmds.getAttr(ctl + ".rotateOrder", channelBox=True)
    print("PASS: rotateOrder follows final rotation visibility and explicit locks")


def test_face_squash(curve_tool):
    scope = load_functions(
        SCRIPTS / "biped/autorig/neck_module_de_boor.py",
        {"controller_creation", "head_squash_setup"},
        {"cmds": cmds, "om": om, "curve_tool": curve_tool},
    )
    cmds.file(new=True, force=True)
    root = cmds.createNode("transform", name="master")
    neck = cmds.createNode("joint", name="neck_guide")
    head = cmds.createNode("joint", name="head_guide", parent=neck)
    cmds.setAttr(head + ".ty", 10)
    rig = SimpleNamespace(
        side="C", neck_chain=[neck, head],
        controllers_grp=cmds.createNode("transform", name="neck_controls", parent=root),
        neck_guide_matrix=cmds.getAttr(neck + ".worldMatrix[0]"),
        head_guide_matrix=cmds.getAttr(head + ".worldMatrix[0]"),
        head_skinning_jnt=cmds.createNode("joint", name="C_headSkinning_JNT"),
    )
    scope["controller_creation"](rig)
    scope["head_squash_setup"](rig)
    assert rig.head_squash_ctl == rig.face_ctl
    assert not cmds.objExists("C_headSquash_CTL")
    assert cmds.attributeQuery("FACE_VIS", node=rig.face_ctl, exists=True)
    assert cmds.getAttr(rig.face_ctl + ".Volume") == 1
    assert cmds.getAttr(rig.face_ctl + ".ty", keyable=True)
    assert not cmds.getAttr(rig.face_ctl + ".ty", lock=True)
    for attr in ["tx", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"]:
        assert cmds.getAttr(rig.face_ctl + "." + attr, lock=True), attr
        assert not cmds.getAttr(rig.face_ctl + "." + attr, keyable=True), attr
        assert not cmds.getAttr(rig.face_ctl + "." + attr, channelBox=True), attr
    assert not cmds.getAttr(rig.face_ctl + ".rotateOrder", channelBox=True)

    facial_group = cmds.createNode("transform", name="facial_controls", parent=rig.face_controls_parent)
    rest = cmds.getAttr(facial_group + ".worldMatrix[0]")
    for ty, volume in [(0, 1), (-5, 1), (10, 1), (-5, 0), (-5, 2), (-20, 1)]:
        cmds.setAttr(rig.face_ctl + ".ty", ty)
        cmds.setAttr(rig.face_ctl + ".Volume", volume)
        sx, sy, sz = cmds.getAttr(rig.head_skinning_jnt + ".scale")[0]
        expected_y = max(0.05, 1 + ty / 10)
        assert math.isclose(sy, expected_y, abs_tol=1e-7)
        assert math.isclose(sx, expected_y ** (-0.5 * volume), abs_tol=1e-7)
        assert math.isclose(sz, sx, abs_tol=1e-7)
        assert cmds.getAttr(facial_group + ".worldMatrix[0]") == rest
        if volume == 1:
            assert math.isclose(sx * sy * sz, 1, abs_tol=1e-7)
    cmds.setAttr(rig.neck_ctls[-1] + ".ry", 30)
    assert cmds.getAttr(facial_group + ".worldMatrix[0]") != rest

    # Each facial module consumes the stationary parent; older builds and
    # quadruped/mGear necks without that cache entry keep their existing parent.
    for parent in [rig.face_controls_parent, None]:
        cache = {"face_ctl": rig.face_ctl, "face_controls_parent": parent}
        data_manager = SimpleNamespace(DataExportBiped=lambda: SimpleNamespace(
            get_data=lambda module, key: cache.get(key)))
        for module in ["eyelid", "tongue", "eyebrow", "teeth", "ear", "nose",
                       "cheekbone", "jaw_module_nurbs", "jaw_module_bezier"]:
            filename = module + (".py" if module.startswith("jaw_") else "_module.py")
            initializer = load_functions(SCRIPTS / "biped/autorig" / filename,
                                         {"__init__"}, {"data_manager": data_manager})
            facial = SimpleNamespace()
            initializer["__init__"](facial)
            assert facial.face_controls_parent == (parent or rig.face_ctl), module
    print("PASS: face TY/Volume drive squash; facial controls follow head without inheriting driver TY")


def main():
    maya.standalone.initialize(name="python")
    try:
        scope = load_functions(
            SCRIPTS / "utils/curve_tool.py", {"lock_attributes", "create_controller"},
            {"cmds": cmds, "om": om, "build_curves_from_template": lambda name: None},
        )
        curve_tool = SimpleNamespace(**{name: scope[name] for name in ["lock_attributes", "create_controller"]})
        test_rotate_order(curve_tool)
        test_face_squash(curve_tool)
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    main()
