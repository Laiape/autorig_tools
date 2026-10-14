"""Editable joint targets on a normalized, post-skin deformation layer.

All playback uses stock Maya DG nodes. Targets store local TRS deltas; each
target has a manual weight or a remapped driver. Scene data survives save/load.
"""
import functools
import json
import math
import re
import uuid

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

MARKER = "jointTargetSystem"


def undoable(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        chunk = "JointTargets_" + uuid.uuid4().hex
        cmds.undoInfo(openChunk=True, chunkName=chunk)
        try:
            result = function(*args, **kwargs)
        except Exception:
            cmds.undoInfo(closeChunk=True)
            if cmds.undoInfo(query=True, state=True) and cmds.undoInfo(query=True, undoName=True) == chunk:
                cmds.undo()
            raise
        cmds.undoInfo(closeChunk=True)
        return result
    return call


def _name(name):
    result = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    if not result:
        raise ValueError("Enter a name.")
    return ("target_" + result) if result[0].isdigit() else result


def _attr(node, name, kind="double", value=None, multi=False, **kwargs):
    cmds.addAttr(node, longName=name, attributeType=kind, multi=multi, **kwargs)
    if value is not None:
        cmds.setAttr(node + "." + name, value)


def _text(node, name, value=""):
    cmds.addAttr(node, longName=name, dataType="string")
    cmds.setAttr(node + "." + name, value, type="string")


def _link(source, node, attr, index=None):
    destination = node + "." + attr
    if index is not None:
        destination += "[%d]" % index
    cmds.connectAttr(source + ".message", destination)


def linked(node, attr, index=None):
    plug = node + "." + attr
    if index is not None:
        plug += "[%d]" % index
    return (cmds.listConnections(plug, source=True, destination=False) or [None])[0]


def indexed(node, attr):
    return [(i, linked(node, attr, i)) for i in (cmds.getAttr(node + "." + attr, multiIndices=True) or [])
            if linked(node, attr, i)]


def systems():
    return [n for n in (cmds.ls(type="network") or []) if cmds.attributeQuery(MARKER, node=n, exists=True)]


def _owned(node, owner):
    indices = cmds.getAttr(owner + ".nodes", multiIndices=True) or []
    _link(node, owner, "nodes", max(indices, default=-1) + 1)
    return node


def _node(kind, name, owner):
    return _owned(cmds.createNode(kind, name=name, skipSelect=True), owner)


def _idle(system):
    if cmds.getAttr(system + ".editing"):
        raise ValueError("Save or cancel the current target edit first.")


def _mesh(mesh):
    matches = cmds.ls(mesh, long=True) or []
    if len(matches) != 1:
        raise ValueError("Choose one unambiguous polygon mesh.")
    mesh = matches[0]
    if cmds.nodeType(mesh) == "mesh":
        mesh = cmds.listRelatives(mesh, parent=True, fullPath=True)[0]
    shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
    if len(shapes) != 1:
        raise ValueError("Choose a transform with one polygon mesh shape.")
    return mesh


@undoable
def create_system(mesh, name="shoulder"):
    mesh = _mesh(mesh)
    name = _name(name)
    system = cmds.createNode("network", name=name + "_jointTargets")
    _attr(system, MARKER, "bool", True)
    for attr in ("mesh", "skin", "neutral"):
        _attr(system, attr, "message")
    for attr in ("joints", "anchors", "handles", "poses", "nodes"):
        _attr(system, attr, "message", multi=True)
    _attr(system, "envelope", value=1, minValue=0, maxValue=1, keyable=True)
    _attr(system, "editing", "bool", False)
    _attr(system, "editIndex", "long", -1)
    _text(system, "previewState")
    _link(mesh, system, "mesh")
    # An identity influence carries the remaining weight. A sparse skin with
    # normalization disabled would shrink vertices whose weights sum below 1.
    neutral = _node("joint", name + "_jointTargetsNeutral_JNT", system)
    cmds.setAttr(neutral + ".inheritsTransform", False)
    cmds.setAttr(neutral + ".visibility", False)
    skin = cmds.skinCluster(neutral, mesh, toSelectedBones=True, multi=True,
                            name=name + "_jointTargets_SKC")[0]
    cmds.setAttr(skin + ".normalizeWeights", 1)
    cmds.setAttr(skin + ".maintainMaxInfluences", False)
    cmds.setAttr(skin + ".skinningMethod", 0)
    _link(neutral, system, "neutral")
    _link(skin, system, "skin")
    return system


def _vertices(system, vertices):
    mesh = linked(system, "mesh")
    mesh_long = cmds.ls(mesh, long=True)[0]
    expanded = cmds.ls(vertices, flatten=True, long=True) or []
    if not expanded or any(".vtx[" not in v or v.split(".vtx[")[0] != mesh_long for v in expanded):
        raise ValueError("Select vertices on this system's mesh.")
    return list(dict.fromkeys(expanded))


@undoable
def add_joint(system, parent, vertices, name="volume", falloff=True):
    _idle(system)
    vertices = _vertices(system, vertices)
    if not cmds.objExists(parent) or cmds.nodeType(parent) not in ("joint", "transform"):
        raise ValueError("Choose the rig joint/transform that this patch follows.")
    name = _name(name)
    points = [om.MVector(*cmds.pointPosition(v, world=True)) for v in vertices]
    center = sum(points, om.MVector()) / len(points)
    anchor = _node("transform", name + "_jointTargetAnchor", system)
    anchor = cmds.parent(anchor, parent)[0]
    cmds.xform(anchor, worldSpace=True, translation=list(center))
    joint = _owned(cmds.createNode("joint", name=name + "_jointTarget_JNT", parent=anchor), system)
    cmds.setAttr(joint + ".segmentScaleCompensate", False)
    # A visible editing handle is separate from the evaluated joint.
    pts = []
    for axis in range(3):
        for step in range(17):
            angle = step * math.tau / 16
            point = [0.0, 0.0, 0.0]
            point[(axis + 1) % 3] = math.cos(angle) * .5
            point[(axis + 2) % 3] = math.sin(angle) * .5
            pts.append(point)
    handle = _owned(cmds.curve(name=name + "_jointTarget_EDIT", degree=1, point=pts), system)
    handle = cmds.parent(handle, anchor, relative=True)[0]
    cmds.connectAttr(system + ".editing", handle + ".visibility")
    indices = [i for i, _ in indexed(system, "joints")]
    index = max(indices, default=-1) + 1
    for node, attr in ((joint, "joints"), (anchor, "anchors"), (handle, "handles")):
        _link(node, system, attr, index)
    for kind in ("translate", "rotate", "scale"):
        _attr(joint, kind + "Sum", "message")
        total = _node("plusMinusAverage", name + "_" + kind + "Sum", system)
        _link(total, joint, kind + "Sum")
        cmds.setAttr(total + ".input3D[0]", *((1, 1, 1) if kind == "scale" else (0, 0, 0)))
        edit = _node("blendColors", name + "_" + kind + "Edit", system)
        cmds.connectAttr(handle + "." + kind, edit + ".color1")
        cmds.connectAttr(total + ".output3D", edit + ".color2")
        cmds.connectAttr(system + ".editing", edit + ".blender")
        cmds.connectAttr(edit + ".output", joint + "." + kind)
    skin = linked(system, "skin")
    cmds.skinCluster(skin, edit=True, addInfluence=joint, weight=0, lockWeights=False)
    selection = om.MSelectionList()
    selection.add(skin)
    selection.add(joint)
    influence_index = oma.MFnSkinCluster(selection.getDependNode(0)).indexForInfluenceObject(selection.getDagPath(1))
    cmds.connectAttr(anchor + ".worldInverseMatrix[0]", skin + ".bindPreMatrix[%d]" % influence_index, force=True)
    # Initial masks preserve old masks wherever there is remaining neutral weight.
    # For overlap, renormalize only the corrective influences; all rest matrices
    # remain identity, so adding a new joint cannot change the zero-weight mesh.
    set_mask(system, joint, vertices, falloff)
    for pose_index, pose in indexed(system, "poses"):
        _connect_target(system, pose, pose_index, joint, index)
    return joint


@undoable
def set_mask(system, joint, vertices, falloff=True):
    _idle(system)
    vertices = _vertices(system, vertices)
    if joint not in [j for _, j in indexed(system, "joints")]:
        raise ValueError("Choose a joint from this system.")
    skin, neutral = linked(system, "skin"), linked(system, "neutral")
    points = [om.MVector(*cmds.pointPosition(v, world=True)) for v in vertices]
    center = sum(points, om.MVector()) / len(points)
    distances = [(p - center).length() for p in points]
    radius = max(distances, default=0) * 1.5
    infs = cmds.skinCluster(skin, query=True, influence=True)
    for vertex, distance in zip(vertices, distances):
        weight = max(0, 1 - (distance / radius) ** 2) ** 2 if falloff and radius > 1e-8 else 1
        old = cmds.skinPercent(skin, vertex, query=True, value=True)
        others = [(j, w) for j, w in zip(infs, old) if j not in (joint, neutral)]
        remaining = sum(w for _, w in others)
        factor = min(1, (1 - weight) / remaining) if remaining > 0 else 1
        values = [(j, w * factor) for j, w in others]
        values += [(joint, weight), (neutral, max(0, 1 - weight - remaining * factor))]
        cmds.skinPercent(skin, vertex, transformValue=values, normalize=True)


def _target_attr(pose, kind):
    attr = "target" + kind.title()
    _attr(pose, attr, "double3", multi=True)
    for axis in "XYZ":
        cmds.addAttr(pose, longName=attr + axis, attributeType="double", parent=attr)


def _connect_target(system, pose, pose_index, joint, joint_index):
    for kind in ("translate", "rotate", "scale"):
        attr = pose + ".target" + kind.title() + "[%d]" % joint_index
        if not cmds.objExists(attr) or cmds.getAttr(attr) is None:
            cmds.setAttr(attr, 0, 0, 0)
        multiply = _node("multiplyDivide", pose + "_" + kind + str(joint_index), pose)
        cmds.connectAttr(attr, multiply + ".input1")
        for axis in "XYZ":
            cmds.connectAttr(pose + ".effectiveWeight", multiply + ".input2" + axis)
        total = linked(joint, kind + "Sum")
        cmds.connectAttr(multiply + ".output", total + ".input3D[%d]" % (pose_index + 1))


@undoable
def add_pose(system, name="shoulder_volume"):
    _idle(system)
    if not indexed(system, "joints"):
        raise ValueError("Add at least one corrective joint first.")
    name = _name(name)
    pose = cmds.createNode("network", name=name + "_jointTargetPose")
    _text(pose, "label", name)
    _attr(pose, "nodes", "message", multi=True)
    _attr(pose, "system", "message")
    _link(system, pose, "system")
    for attr, value in (("weight", 0), ("driverWeight", 0), ("previewWeight", 0), ("effectiveWeight", 0)):
        _attr(pose, attr, value=value, minValue=0, maxValue=1, keyable=attr == "weight")
    for attr, value in (("auto", False), ("override", False), ("enabled", True)):
        _attr(pose, attr, "bool", value)
    _attr(pose, "start", value=30, keyable=True)
    _attr(pose, "end", value=90, keyable=True)
    _attr(pose, "smooth", "bool", True)
    _attr(pose, "driverRemap", "message")
    _text(pose, "driverPlug")
    auto = _node("blendColors", name + "_autoWeight", pose)
    cmds.connectAttr(pose + ".driverWeight", auto + ".color1R")
    cmds.connectAttr(pose + ".weight", auto + ".color2R")
    cmds.connectAttr(pose + ".auto", auto + ".blender")
    preview_node = _node("blendColors", name + "_previewWeight", pose)
    cmds.connectAttr(pose + ".previewWeight", preview_node + ".color1R")
    cmds.connectAttr(auto + ".outputR", preview_node + ".color2R")
    cmds.connectAttr(pose + ".override", preview_node + ".blender")
    enable = _node("multiplyDivide", name + "_enabled", pose)
    cmds.connectAttr(preview_node + ".outputR", enable + ".input1X")
    cmds.connectAttr(pose + ".enabled", enable + ".input2X")
    envelope = _node("multiplyDivide", name + "_envelope", pose)
    cmds.connectAttr(enable + ".outputX", envelope + ".input1X")
    cmds.connectAttr(system + ".envelope", envelope + ".input2X")
    cmds.connectAttr(envelope + ".outputX", pose + ".effectiveWeight")
    for kind in ("translate", "rotate", "scale"):
        _target_attr(pose, kind)
    index = max([i for i, _ in indexed(system, "poses")], default=-1) + 1
    _link(pose, system, "poses", index)
    for joint_index, joint in indexed(system, "joints"):
        _connect_target(system, pose, index, joint, joint_index)
    return pose


@undoable
def configure_driver(pose, plug, start=30, end=90, smooth=True):
    system = linked(pose, "system")
    _idle(system)
    if not cmds.objExists(plug) or cmds.getAttr(plug, type=True) not in ("double", "float", "doubleAngle", "doubleLinear", "long", "short", "bool"):
        raise ValueError("Choose a numeric driver attribute.")
    if not math.isfinite(start) or not math.isfinite(end) or abs(end - start) < 1e-8:
        raise ValueError("Start and end must be finite and different.")
    # Reject feedback from corrective joints, handles or their descendants.
    source = plug.split(".", 1)[0]
    forbidden = [j for _, j in indexed(system, "joints")] + [h for _, h in indexed(system, "handles")]
    source_path = cmds.ls(source, long=True)[0]
    if any(source_path == cmds.ls(n, long=True)[0] or source_path.startswith(cmds.ls(n, long=True)[0] + "|") for n in forbidden):
        raise ValueError("The driver must come from the base rig, not a corrective.")
    remap = linked(pose, "driverRemap")
    if not remap:
        difference = _node("plusMinusAverage", pose + "_driverDifference", pose)
        cmds.setAttr(difference + ".operation", 2)
        span = _node("plusMinusAverage", pose + "_driverSpan", pose)
        cmds.setAttr(span + ".operation", 2)
        cmds.connectAttr(pose + ".end", span + ".input1D[0]")
        cmds.connectAttr(pose + ".start", span + ".input1D[1]")
        cmds.connectAttr(pose + ".start", difference + ".input1D[1]")
        divide = _node("multiplyDivide", pose + "_driverRatio", pose)
        cmds.setAttr(divide + ".operation", 2)
        cmds.connectAttr(difference + ".output1D", divide + ".input1X")
        cmds.connectAttr(span + ".output1D", divide + ".input2X")
        remap = _node("remapValue", pose + "_driverRamp", pose)
        cmds.connectAttr(divide + ".outputX", remap + ".inputValue")
        cmds.connectAttr(remap + ".outValue", pose + ".driverWeight")
        _link(remap, pose, "driverRemap")
        _attr(pose, "driverDifference", "message")
        _link(difference, pose, "driverDifference")
    difference = linked(pose, "driverDifference")
    if not cmds.isConnected(plug, difference + ".input1D[0]", ignoreUnitConversion=True):
        cmds.connectAttr(plug, difference + ".input1D[0]", force=True)
    for attr, value in (("start", start), ("end", end), ("smooth", smooth), ("auto", True)):
        cmds.setAttr(pose + "." + attr, value)
    for i in (0, 1):
        cmds.setAttr(remap + ".value[%d].value_Interp" % i, 2 if smooth else 1)
    cmds.setAttr(pose + ".driverPlug", plug, type="string")


@undoable
def direction_driver(system, joint, reference, axis="X"):
    """Swing angle from the current neutral direction, independent of IK/FK.

    Call in the intended zero pose. A direction metric deliberately ignores
    axial twist; use a separate attribute driver for twist-specific targets.
    """
    _idle(system)
    if axis not in "XYZ" or len(axis) != 1:
        raise ValueError("Bone axis must be X, Y or Z.")
    forbidden = [j for _, j in indexed(system, "joints")] + [h for _, h in indexed(system, "handles")]
    for node in (joint, reference):
        if not cmds.objExists(node) or cmds.nodeType(node) not in ("joint", "transform"):
            raise ValueError("Choose existing base-rig transforms.")
        path = cmds.ls(node, long=True)[0]
        if any(path == cmds.ls(n, long=True)[0] or path.startswith(cmds.ls(n, long=True)[0] + "|") for n in forbidden):
            raise ValueError("Use the base rig to measure the shoulder angle.")
    relative = _node("multMatrix", system + "_swingMatrix", system)
    cmds.connectAttr(joint + ".worldMatrix[0]", relative + ".matrixIn[0]")
    cmds.connectAttr(reference + ".worldInverseMatrix[0]", relative + ".matrixIn[1]")
    vector = _node("vectorProduct", system + "_swingDirection", system)
    cmds.setAttr(vector + ".operation", 3)
    cmds.setAttr(vector + ".normalizeOutput", True)
    cmds.setAttr(vector + ".input1" + axis, 1)
    cmds.connectAttr(relative + ".matrixSum", vector + ".matrix")
    angle = _node("angleBetween", system + "_swingAngle", system)
    cmds.setAttr(angle + ".vector1", *cmds.getAttr(vector + ".output")[0])
    cmds.connectAttr(vector + ".output", angle + ".vector2")
    return angle + ".angle"


@undoable
def preview(system, pose=None, weight=1):
    _idle(system)
    if pose is not None and pose not in [p for _, p in indexed(system, "poses")]:
        raise ValueError("Choose a target from this system.")
    for _, current in indexed(system, "poses"):
        cmds.setAttr(current + ".override", pose is not None)
        cmds.setAttr(current + ".previewWeight", weight if current == pose else 0)


@undoable
def begin_edit(system, pose):
    _idle(system)
    poses = indexed(system, "poses")
    matches = [i for i, p in poses if p == pose]
    if not matches:
        raise ValueError("Choose a target from this system.")
    state = {str(i): [cmds.getAttr(p + ".override"), cmds.getAttr(p + ".previewWeight")] for i, p in poses}
    cmds.setAttr(system + ".previewState", json.dumps(state), type="string")
    for i, handle in indexed(system, "handles"):
        for kind in ("translate", "rotate", "scale"):
            value = cmds.getAttr(pose + ".target" + kind.title() + "[%d]" % i)[0]
            if kind == "scale":
                value = tuple(v + 1 for v in value)
            cmds.setAttr(handle + "." + kind, *value)
    cmds.setAttr(system + ".editIndex", matches[0])
    cmds.setAttr(system + ".editing", True)
    cmds.select([h for _, h in indexed(system, "handles")], replace=True)


@undoable
def finish_edit(system, save=True):
    if not cmds.getAttr(system + ".editing"):
        raise ValueError("No target is being edited.")
    pose = linked(system, "poses", cmds.getAttr(system + ".editIndex"))
    if save:
        for i, handle in indexed(system, "handles"):
            for kind in ("translate", "rotate", "scale"):
                value = cmds.getAttr(handle + "." + kind)[0]
                if kind == "scale":
                    value = tuple(v - 1 for v in value)
                cmds.setAttr(pose + ".target" + kind.title() + "[%d]" % i, *value)
    state = json.loads(cmds.getAttr(system + ".previewState") or "{}")
    for i, current in indexed(system, "poses"):
        override, weight = state.get(str(i), (False, 0))
        cmds.setAttr(current + ".override", override)
        cmds.setAttr(current + ".previewWeight", weight)
    cmds.setAttr(system + ".editing", False)
    cmds.setAttr(system + ".editIndex", -1)


@undoable
def remove_pose(system, pose):
    _idle(system)
    matches = [i for i, p in indexed(system, "poses") if p == pose]
    if not matches:
        raise ValueError("Choose a target from this system.")
    for _, joint in indexed(system, "joints"):
        for kind in ("translate", "rotate", "scale"):
            total = linked(joint, kind + "Sum")
            cmds.removeMultiInstance(total + ".input3D[%d]" % (matches[0] + 1), b=True)
    nodes = [n for _, n in indexed(pose, "nodes")]
    cmds.delete(nodes + [pose])
    cmds.removeMultiInstance(system + ".poses[%d]" % matches[0], b=True)


def show():
    from maya_tools.scripts.ui import joint_correctives_UI
    return joint_correctives_UI.show()
