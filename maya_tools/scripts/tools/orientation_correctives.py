"""Native orientation pose drivers, measured in a base-rig reference frame.

Runtime is a Maya poseInterpolator and DG nodes; Python only authors data.
Neutral and sculpt samples are quaternions, not controller Euler channels.
"""
import json
import math

from maya import cmds
from maya.api import OpenMaya as om

MARKER = "orientationCorrectiveSystem"
POSE_TYPES = {"swing_twist": 0, "swing": 1, "twist": 2}


def linked(node, attr):
    if not node or not cmds.objExists(node):
        return None
    if not cmds.attributeQuery(attr.split("[", 1)[0], node=node, exists=True):
        return None
    return (cmds.listConnections(node + "." + attr, source=True, destination=False) or [None])[0]


def _link(source, node, attr):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="message")
    cmds.connectAttr(source + ".message", node + "." + attr, force=True)


def systems():
    return [n for n in cmds.ls(type="network") or []
            if cmds.attributeQuery(MARKER, node=n, exists=True)]


def _transform(node):
    matches = cmds.ls(node, long=True, objectsOnly=True) or []
    if len(matches) != 1 or cmds.nodeType(matches[0]) not in ("joint", "transform"):
        raise ValueError("Choose one base-rig joint or transform.")
    return matches[0]


def _quaternion(matrix):
    q = om.MTransformationMatrix(om.MMatrix(matrix)).rotation(asQuaternion=True)
    q.normalizeIt()
    return [q.x, q.y, q.z, q.w]


def _write_pose(pi, index, name, quaternion, pose_type, **settings):
    root = pi + ".pose[%d]" % index
    cmds.setAttr(root + ".poseName", name, type="string")
    cmds.setAttr(root + ".poseRotation[0]", quaternion, type="doubleArray")
    cmds.setAttr(root + ".poseTranslation[0]", [0., 0., 0.], type="doubleArray")
    cmds.setAttr(root + ".poseType", pose_type)
    cmds.setAttr(root + ".isEnabled", True)
    for attr, value in settings.items():
        cmds.setAttr(root + "." + attr, value)


def _create_interpolator(owner, joint, rotation, axis):
    """Create the native helper for a new or restored orientation region."""
    cmds.loadPlugin("poseInterpolator", quiet=True)
    pi = cmds.createNode("poseInterpolator", name=owner + "Shape")
    parent = cmds.listRelatives(pi, parent=True)[0]
    parent = cmds.rename(parent, owner + "_PI")
    pi = cmds.listRelatives(parent, shapes=True)[0]
    cmds.setAttr(parent + ".visibility", False)
    char_root = "|" + joint.split("|")[1]
    if char_root != joint:
        cmds.parent(parent, char_root)
    cmds.connectAttr(rotation + ".outputMatrix", pi + ".driver[0].driverMatrix")
    cmds.setAttr(pi + ".driver[0].driverTwistAxis", "XYZ".index(axis))
    cmds.setAttr(pi + ".driver[0].driverEulerTwist", False)
    cmds.setAttr(pi + ".enableTranslation", False)
    cmds.setAttr(pi + ".interpolation", 0)
    cmds.setAttr(pi + ".regularization", 0)
    _link(pi, owner, "interpolator")
    _link(parent, owner, "helper")
    return pi


def create_system(joint, reference, name="orientationCorrectives", axis="X", neutral_matrix=None):
    """Call at the intended neutral pose. Use a reference upstream of the joint."""
    from maya_tools.scripts.tools import pose_blendshapes as poses
    return poses.undoable(_create_system)(joint, reference, name, axis, neutral_matrix)


def _create_system(joint, reference, name, axis, neutral_matrix=None):
    joint, reference = _transform(joint), _transform(reference)
    if joint == reference or reference.startswith(joint + "|"):
        raise ValueError("The reference must not be the driver or its descendant.")
    axis = axis.upper()
    if axis not in ("X", "Y", "Z"):
        raise ValueError("Choose the bone's X, Y or Z twist axis.")
    cmds.loadPlugin("poseInterpolator", quiet=True)
    owner = cmds.createNode("network", name=name)
    cmds.addAttr(owner, longName=MARKER, attributeType="bool", defaultValue=True)
    _link(joint, owner, "joint")
    _link(reference, owner, "reference")
    cmds.addAttr(owner, longName="twistAxis", dataType="string")
    cmds.setAttr(owner + ".twistAxis", axis, type="string")
    relative = cmds.createNode("multMatrix", name=owner + "_relative")
    cmds.connectAttr(joint + ".worldMatrix[0]", relative + ".matrixIn[0]")
    cmds.connectAttr(reference + ".worldInverseMatrix[0]", relative + ".matrixIn[1]")
    rotation = cmds.createNode("pickMatrix", name=owner + "_rotation")
    cmds.connectAttr(relative + ".matrixSum", rotation + ".inputMatrix")
    for attr in ("useTranslate", "useScale", "useShear"):
        cmds.setAttr(rotation + "." + attr, False)
    pi = _create_interpolator(owner, joint, rotation, axis)
    for attr, node in (("relative", relative), ("rotation", rotation)):
        _link(node, owner, attr)
    matrix = neutral_matrix or cmds.getAttr(rotation + ".outputMatrix")
    if len(matrix) != 16 or not all(math.isfinite(v) for v in matrix):
        raise ValueError("Neutral must be a finite rotation matrix.")
    cmds.addAttr(owner, longName="neutralMatrix", dataType="matrix")
    cmds.setAttr(owner + ".neutralMatrix", matrix, type="matrix")
    quaternion = _quaternion(matrix)
    for label, pose_type in POSE_TYPES.items():
        _write_pose(pi, pose_type, "neutral_" + label, quaternion, pose_type)
    return owner


def _same_pose(a, b, pose_type, axis):
    qa, qb = om.MQuaternion(*a), om.MQuaternion(*b)
    if pose_type == 1:
        direction = om.MVector(*(1. if i == axis else 0. for i in range(3)))
        return (direction.rotateBy(qa) - direction.rotateBy(qb)).length() < 1e-6
    if pose_type == 2:
        a = [a[axis], a[3]]
        b = [b[axis], b[3]]
        la, lb = math.hypot(*a), math.hypot(*b)
        if min(la, lb) < 1e-8:
            raise ValueError("Twist is undefined at this swing orientation. Choose another sample.")
        return abs(sum(x * y for x, y in zip(a, b)) / (la * lb)) > 1 - 1e-10
    return abs(sum(x * y for x, y in zip(a, b))) > 1 - 1e-10


def attach_target(system, bs, index, record, pose_type="swing_twist", quaternion=None):
    if cmds.attributeQuery('combinationData', node=record, exists=True):
        raise ValueError('A combination target keeps its composite driver. Convert its source targets instead.')
    """Replace this managed target's driver using its current joint orientation."""
    from maya_tools.scripts.tools import pose_blendshapes as poses
    return poses.undoable(_attach_target)(system, bs, index, record, pose_type, quaternion)


def _attach_target(system, bs, index, record, pose_type, quaternion=None):
    from maya_tools.scripts.tools import pose_blendshapes as poses
    poses._idle()
    if system not in systems() or pose_type not in POSE_TYPES:
        raise ValueError("Choose an orientation region and pose type.")
    if poses.pose_record(bs, index) != record:
        raise ValueError("Only captured Pose Blendshapes targets can be converted.")
    pi = linked(system, "interpolator")
    quaternion = quaternion or _quaternion(cmds.getAttr(linked(system, "rotation") + ".outputMatrix"))
    kind = POSE_TYPES[pose_type]
    axis = "XYZ".index(cmds.getAttr(system + ".twistAxis"))
    indices = cmds.getAttr(pi + ".pose", multiIndices=True) or []
    for i in indices:
        root = pi + ".pose[%d]" % i
        if cmds.getAttr(root + ".isEnabled") and cmds.getAttr(root + ".poseType") == kind:
            sample = cmds.getAttr(root + ".poseRotation[0]")
            if _same_pose(sample, quaternion, kind, axis):
                raise ValueError("This orientation already has a sample (or is neutral).")
    pose_index = max(indices, default=-1) + 1
    name = dict(poses.targets(bs))[index]
    _write_pose(pi, pose_index, name, quaternion, kind)
    return _replace_driver(system, pose_index, bs, index, record)


def share_target(system, pose_index, bs, index, record):
    """Reuse one regional pose for another mesh without fitting duplicate samples."""
    from maya_tools.scripts.tools import pose_blendshapes as poses
    poses._idle()
    pi = linked(system, "interpolator")
    if not pi or pose_index < 3 or not cmds.getAttr(pi + ".pose[%d].isEnabled" % pose_index):
        raise ValueError("Choose an enabled corrective sample.")
    if poses.pose_record(bs, index) != record:
        raise ValueError("Choose a captured target.")
    return poses.undoable(_replace_driver)(system, pose_index, bs, index, record)


def _replace_driver(system, pose_index, bs, index, record):
    pi = linked(system, "interpolator")
    detach_target(record)
    destination = bs + ".weight[%d]" % index
    source = cmds.connectionInfo(destination, sourceFromDestination=True)
    if source:
        cmds.disconnectAttr(source, destination)
    old_nodes = cmds.listConnections(record + ".driverNodes", source=True, destination=False) or []
    for i in cmds.getAttr(record + ".driverNodes", multiIndices=True) or []:
        cmds.removeMultiInstance(record + ".driverNodes[%d]" % i, b=True)
    # Only delete nodes owned by this record, with no outside consumers.
    for node in reversed(old_nodes):
        consumers = cmds.listConnections(node, source=False, destination=True) or []
        if all(n in old_nodes for n in consumers):
            cmds.delete(node)
    clamp = cmds.createNode("clamp", name=record + "_orientationWeight")
    cmds.setAttr(clamp + ".maxR", 1)
    cmds.connectAttr(pi + ".output[%d]" % pose_index, clamp + ".inputR")
    cmds.connectAttr(clamp + ".outputR", destination)
    cmds.connectAttr(clamp + ".message", record + ".driverNodes[0]")
    _link(system, record, "orientationSystem")
    if not cmds.attributeQuery("orientationPose", node=record, exists=True):
        cmds.addAttr(record, longName="orientationPose", attributeType="long")
    cmds.setAttr(record + ".orientationPose", pose_index)
    return pose_index


def detach_target(record):
    system = linked(record, "orientationSystem")
    if not system:
        return
    pi = linked(system, "interpolator")
    i = cmds.getAttr(record + ".orientationPose")
    from maya_tools.scripts.tools import pose_blendshapes as poses
    shared = any(other != record and linked(other, "orientationSystem") == system
                 and cmds.getAttr(other + ".orientationPose") == i for other in poses._find(poses.POSE_MARKER))
    if not shared and pi and i in (cmds.getAttr(pi + ".pose", multiIndices=True) or []):
        # A pose compound contains typed quaternion data. Removing it child by
        # child can transiently evaluate an incomplete native sample; disable
        # the owned sample instead, retaining stable sparse indices for undo.
        cmds.setAttr(pi + ".pose[%d].isEnabled" % i, False)
    cmds.disconnectAttr(system + ".message", record + ".orientationSystem")


def export_systems():
    result = []
    for owner in systems():
        pi = linked(owner, "interpolator")
        if not pi:
            raise ValueError("Orientation region has lost its interpolator: " + owner)
        samples = []
        for i in cmds.getAttr(pi + ".pose", multiIndices=True) or []:
            root = pi + ".pose[%d]" % i
            samples.append({"index": i, "name": cmds.getAttr(root + ".poseName"),
                            "quaternion": cmds.getAttr(root + ".poseRotation[0]"),
                            "type": cmds.getAttr(root + ".poseType"),
                            "settings": {a: cmds.getAttr(root + "." + a) for a in (
                                "isEnabled", "isIndependent", "poseRotationFalloff", "poseFalloff")}})
        result.append({"version": 1, "name": owner, "joint": linked(owner, "joint"),
                       "reference": linked(owner, "reference"), "axis": cmds.getAttr(owner + ".twistAxis"),
                       "neutral": cmds.getAttr(owner + ".neutralMatrix"), "samples": samples,
                       "settings": {a: cmds.getAttr(pi + "." + a) for a in (
                           "interpolation", "regularization", "outputSmoothing", "allowNegativeWeights")},
                       "nodes": {a: linked(owner, a) for a in ("interpolator", "relative", "rotation", "helper")}})
    return result


def _reconnect_existing_targets(owner, pi):
    """Reconnect surviving managed clamps after their interpolator was lost."""
    for record in cmds.listConnections(owner + ".message", source=False, destination=True,
                                       type="network") or []:
        if linked(record, "orientationSystem") != owner:
            continue
        bs = linked(record, "blendShape")
        if not bs or not cmds.attributeQuery("driverNodes", node=record, exists=True):
            continue
        destination = bs + ".weight[%d]" % cmds.getAttr(record + ".targetIndex")
        for node in cmds.listConnections(record + ".driverNodes", source=True, destination=False) or []:
            if cmds.nodeType(node) != "clamp" or not cmds.isConnected(node + ".outputR", destination):
                continue
            if not cmds.connectionInfo(node + ".inputR", isDestination=True):
                index = cmds.getAttr(record + ".orientationPose")
                cmds.connectAttr(pi + ".output[%d]" % index, node + ".inputR")


def import_systems(records, resolve, node_map, warnings):
    for entry in records or []:
        if entry.get("version") != 1:
            raise ValueError("Unsupported orientation driver snapshot version.")
        owner = resolve(entry["name"])
        if owner and owner not in systems():
            warnings.append(entry["name"] + ": name occupied by another node; region was not restored.")
            continue
        restore_samples = not owner
        if not owner:
            joint, reference = resolve(entry["joint"]), resolve(entry["reference"])
            if not joint or not reference:
                warnings.append(entry["name"] + ": base-rig driver/reference is missing.")
                continue
            owner = create_system(joint, reference, entry["name"], entry["axis"], entry["neutral"])
        pi = linked(owner, "interpolator")
        if not pi:
            joint = linked(owner, "joint")
            rotation = linked(owner, "rotation")
            if not joint or not rotation:
                raise ValueError("Orientation region cannot restore its interpolator without its driver: " + owner)
            pi = _create_interpolator(owner, _transform(joint), rotation,
                                      cmds.getAttr(owner + ".twistAxis"))
            restore_samples = True
        if restore_samples:
            for sample in entry["samples"]:
                _write_pose(pi, sample["index"], sample["name"], sample["quaternion"],
                            sample["type"], **sample["settings"])
            for a, v in entry["settings"].items():
                cmds.setAttr(pi + "." + a, v)
            _reconnect_existing_targets(owner, pi)
        node_map[entry["name"]] = owner
        for attr, old in entry["nodes"].items():
            node_map[old] = linked(owner, attr)


def restore_target(record, system, pose_index, bs, index, old_clamp_name=None):
    """Restore an existing native sample without recapturing the scene pose."""
    _link(system, record, "orientationSystem")
    cmds.addAttr(record, longName="orientationPose", attributeType="long", defaultValue=pose_index)
    cmds.addAttr(record, longName="driverNodes", attributeType="message", multi=True)
    clamp = cmds.createNode("clamp", name=old_clamp_name or record + "_orientationWeight")
    cmds.setAttr(clamp + ".maxR", 1)
    cmds.connectAttr(linked(system, "interpolator") + ".output[%d]" % pose_index, clamp + ".inputR")
    cmds.connectAttr(clamp + ".outputR", bs + ".weight[%d]" % index)
    cmds.connectAttr(clamp + ".message", record + ".driverNodes[0]")
    return clamp

