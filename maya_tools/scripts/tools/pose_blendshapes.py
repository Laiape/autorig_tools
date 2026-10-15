"""Corrective targets with controller SDK or native orientation pose drivers."""
import functools
import json
import math
import re
import uuid
from contextlib import contextmanager
from collections import deque

from maya import cmds
from maya.api import OpenMaya as om

TR_CHANNELS = tuple(kind + axis for kind in ("translate", "rotate") for axis in "XYZ")
POSE_MARKER = "poseBlendshapeTarget"
EDIT_MARKER = "poseBlendshapeEdit"


def undoable(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        chunk = "PoseBlendshapes_" + uuid.uuid4().hex
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


def _string(node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _message(source, node, attr):
    cmds.addAttr(node, longName=attr, attributeType="message")
    cmds.connectAttr(source + ".message", node + "." + attr)


def linked(node, attr):
    return (cmds.listConnections(node + "." + attr, source=True, destination=False) or [None])[0]


def mesh_transform(mesh):
    matches = cmds.ls(mesh, long=True, objectsOnly=True) or []
    if len(matches) != 1:
        raise ValueError("Select one polygon mesh.")
    mesh = matches[0]
    if cmds.nodeType(mesh) == "mesh":
        mesh = cmds.listRelatives(mesh, parent=True, fullPath=True)[0]
    if len(cmds.listRelatives(mesh, shapes=True, noIntermediate=True, type="mesh") or []) != 1:
        raise ValueError("Select a transform with one polygon mesh shape.")
    return mesh


def blendshapes(mesh):
    mesh = mesh_transform(mesh)
    return list(dict.fromkeys(cmds.ls(cmds.listHistory(mesh) or [], type="blendShape") or []))


def deformation_order(bs, mesh):
    history = cmds.listHistory(mesh_transform(mesh)) or []
    if bs not in history:
        raise ValueError("This blendshape does not affect the loaded mesh.")
    skins = [i for i, n in enumerate(history) if cmds.nodeType(n) == "skinCluster"]
    if not skins:
        return "pre"
    index = history.index(bs)
    if index < min(skins):
        return "post"
    if index > max(skins):
        return "pre"
    return "between skins"


def geometry_index(bs, mesh):
    mesh = mesh_transform(mesh)
    shapes = cmds.blendShape(bs, query=True, geometry=True) or []
    indices = cmds.blendShape(bs, query=True, geometryIndices=True) or []
    for index, shape in zip(indices, shapes):
        if cmds.nodeType(shape) == "mesh" and mesh_transform(shape) == mesh:
            return index
    # An in-place wrinkle graph can be reported as the filter's output path.
    # Keep saved targets editable via their explicit mesh ownership; do not
    # mistake a corrective on a separate wrap-driver branch for this mesh.
    if len(indices) == 1 and bs in (cmds.listHistory(mesh) or []):
        for record in _find(POSE_MARKER):
            if linked(record, "blendShape") == bs:
                owner = linked(record, "mesh")
                if owner and cmds.ls(owner, long=True) == [mesh]:
                    return indices[0]
    raise ValueError("This blendshape does not affect the loaded mesh.")


def targets(bs):
    aliases = cmds.aliasAttr(bs, query=True) or []
    names = {int(plug.split("[")[1].split("]")[0]): name
             for name, plug in zip(aliases[::2], aliases[1::2]) if plug.startswith("weight[")}
    return [(i, names.get(i) or _record_target_name(bs, i) or "target_%d" % i)
            for i in (cmds.getAttr(bs + ".weight", multiIndices=True) or [])]


def _record_target_name(bs, index):
    record = pose_record(bs, index)
    if not record:
        return None
    if cmds.attributeQuery("targetName", node=record, exists=True):
        return cmds.getAttr(record + ".targetName")
    # Compatibility with saved scenes made before names were stored explicitly.
    return record.rsplit("|", 1)[-1].split("_poseData", 1)[0]


def _restore_aliases(bs, aliases):
    for alias, attr in zip(aliases[::2], aliases[1::2]):
        match = re.fullmatch(r"weight\[(\d+)\]", attr)
        if match and int(match.group(1)) in (cmds.getAttr(bs + ".weight", multiIndices=True) or []):
            plug = bs + "." + attr
            if cmds.aliasAttr(plug, query=True) != alias:
                cmds.aliasAttr(alias, plug)


@undoable
def restore_target_names(bs):
    """Recover missing aliases without changing indices, drivers or deltas."""
    restored = []
    for index, name in targets(bs):
        plug = bs + ".weight[%d]" % index
        if not cmds.aliasAttr(plug, query=True) and _record_target_name(bs, index):
            cmds.aliasAttr(name, plug)
            restored.append(name)
        record = pose_record(bs, index)
        if record:
            if not cmds.attributeQuery("targetName", node=record, exists=True):
                _string(record, "targetName", name)
            else:
                cmds.setAttr(record + ".targetName", name, type="string")
    return restored


def _find(marker):
    return [n for n in (cmds.ls(type="network") or []) if cmds.attributeQuery(marker, node=n, exists=True)]


def edit_session():
    return next(iter(_find(EDIT_MARKER)), None)


def _idle():
    if edit_session():
        raise ValueError("Save or cancel the active target edit first.")


def pose_record(bs, index):
    for node in _find(POSE_MARKER):
        if linked(node, "blendShape") == bs and cmds.getAttr(node + ".targetIndex") == index:
            return node
    return None


def capture_control(controller):
    matches = cmds.ls(controller, long=True, objectsOnly=True) or []
    if len(matches) != 1 or cmds.nodeType(matches[0]) not in ("transform", "joint"):
        raise ValueError("Select one posed controller in the scene.")
    controller = matches[0]
    values = []
    for channel in TR_CHANNELS:
        plug = controller + "." + channel
        default = (cmds.attributeQuery(channel, node=controller, listDefault=True) or [0])[0]
        value = cmds.getAttr(plug)
        if not math.isfinite(value) or not math.isfinite(default):
            raise ValueError("The controller has a non-finite channel value.")
        if not math.isclose(value, default, abs_tol=1e-5):
            values.append({"channel": channel, "default": default, "pose": value})
    if not values:
        raise ValueError("Pose the controller first: its Translate/Rotate channels are at their defaults.")
    return controller, values


def _number(value):
    # Maya aliases do not support '-' or decimal dots.
    return format(value, ".4f").rstrip("0").rstrip(".").replace("-", "m").replace(".", "p") or "0"


def target_name(controller, values):
    name = controller.rsplit("|", 1)[-1].split(":")[-1]
    name = re.sub(r"_(CTL|CTRL|CONTROL)$", "", name, flags=re.IGNORECASE)
    parts = name.split("_")
    side = parts.pop(0).upper() if parts[0].upper() in ("L", "R", "C") else "C"
    name = re.sub(r"[^A-Za-z0-9_]", "_", "_".join(parts))
    channels = "_".join(("T" if v["channel"].startswith("translate") else "R")
                        + v["channel"][-1] + _number(v["pose"]) for v in values)
    return side + "_" + name + "_" + channels + "_BLS"


@undoable
def create_blendshape(mesh, order="post"):
    _idle()
    mesh = mesh_transform(mesh)
    if order not in ("pre", "post"):
        raise ValueError("Choose pre or post deformation.")
    name = mesh.rsplit("|", 1)[-1].replace(":", "_") + "_poseCorrectives_BLS"
    # Default insertion appends to this mesh's deformation chain. Explicit
    # `after` can follow a worldMesh consumer (e.g. a proximityWrap driver)
    # instead, leaving the visible mesh unaffected and geometry queries empty.
    flags = {"frontOfChain": True} if order == "pre" else {}
    bs = cmds.blendShape(mesh, name=name, **flags)[0]
    cmds.setAttr(bs + ".deformationOrder", 0 if order == "pre" else 1)
    return bs


def _delta_path(bs, mesh, index):
    return "%s.inputTarget[%d].inputTargetGroup[%d].inputTargetItem[6000]" % (bs, geometry_index(bs, mesh), index)


@undoable
def convert_target_to_transform_space(mesh, bs, index, transform):
    """Rebake a full-weight corrective at its sculpt pose into a stable frame.

    The caller must pose the rig first. Endpoint geometry, aliases and SDKs are
    preserved. Painted masks and in-betweens require a separate conversion.
    """
    _idle()
    mesh = mesh_transform(mesh)
    if deformation_order(bs, mesh) != "post":
        raise ValueError("Transform-space conversion requires a post blendshape.")
    matches = cmds.ls(transform, long=True) or []
    if len(matches) != 1 or cmds.nodeType(matches[0]) not in ("transform", "joint"):
        raise ValueError("Choose one stable transform or joint.")
    transform = matches[0]
    geo = geometry_index(bs, mesh)
    group = "%s.inputTarget[%d].inputTargetGroup[%d]" % (bs, geo, index)
    if cmds.getAttr(group + ".inputTargetItem", multiIndices=True) != [6000]:
        raise ValueError("Convert targets with a single full-weight shape only.")
    if cmds.listConnections(group + ".inputTargetItem[6000].inputGeomTarget", source=True, destination=False):
        raise ValueError("Bake or disconnect the live target geometry first.")
    for array in (group + ".targetWeights", "%s.inputTarget[%d].baseWeights" % (bs, geo),
                  "%s.weightList[%d].weights" % (bs, geo)):
        for item in cmds.getAttr(array, multiIndices=True) or []:
            if not math.isclose(cmds.getAttr(array + "[%d]" % item), 1.0, abs_tol=1e-7):
                raise ValueError("Painted blendshape weights require a mask-aware conversion.")
    record = pose_record(bs, index)
    if record:
        controller = linked(record, "controller")
        for value in json.loads(cmds.getAttr(record + ".channels")):
            if not math.isclose(cmds.getAttr(controller + "." + value["channel"]), value["pose"], abs_tol=1e-5):
                raise ValueError("Go to the recorded full-weight pose before converting.")
    aliases = cmds.aliasAttr(bs, query=True) or []
    isolated = {bs + ".weight[%d]" % i: float(i == index) for i, _ in targets(bs)}
    isolated[bs + ".envelope"] = 1.0
    selection = cmds.ls(selection=True, long=True) or []
    scratch = None
    try:
        with _temporary_values(isolated):
            selected = om.MSelectionList()
            selected.add(cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True)[0])
            fn = om.MFnMesh(selected.getDagPath(0))
            before = fn.getPoints(om.MSpace.kObject)
            scratch = cmds.duplicate(mesh, name="poseTransformSpaceScratch")[0]
            cmds.setAttr(bs + ".weight[%d]" % index, 0.0)
            # Maya's native replacement does not reliably undo the target mode.
            # Record that change explicitly before it writes the new deltas.
            cmds.setAttr(group + ".postDeformersMode", 2)
            cmds.blendShape(bs, edit=True, target=(mesh, index, scratch, 1.0), transform=transform)
            cmds.delete(scratch)
            scratch = None
            cmds.setAttr(bs + ".weight[%d]" % index, 1.0)
            after = fn.getPoints(om.MSpace.kObject)
            error = max((a - b).length() for a, b in zip(after, before))
            if cmds.getAttr(group + ".postDeformersMode") != 2 or error > 2e-5:
                raise RuntimeError("Transform conversion changed the sculpt (max error %.8f)." % error)
            _restore_aliases(bs, aliases)
    finally:
        if scratch and cmds.objExists(scratch):
            cmds.delete(scratch)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    return {"targetIndex": index, "transform": transform, "maxEndpointError": error}


def _connect_driver(bs, index, controller, values, record):
    nodes = []
    output = None
    if len(values) > 1:
        cmds.addAttr(record, longName="axisWeight", attributeType="double", multi=True)
    for i, value in enumerate(values):
        weight_plug = bs + ".weight[%d]" % index if len(values) == 1 else record + ".axisWeight[%d]" % i
        driver = controller + "." + value["channel"]
        for dv, weight in ((value["default"], 0), (value["pose"], 1)):
            cmds.setDrivenKeyframe(weight_plug, currentDriver=driver, driverValue=dv, value=weight,
                                   inTangentType="linear", outTangentType="linear")
        curve = (cmds.listConnections(weight_plug, source=True, destination=False,
                                      skipConversionNodes=True) or [None])[0]
        nodes.append(curve)
        cmds.setInfinity(curve, preInfinite="constant", postInfinite="constant")
        if len(values) > 1:
            if output is None:
                output = weight_plug
            else:
                product = cmds.createNode("multiplyDivide", name=record + "_combine", skipSelect=True)
                nodes.append(product)
                cmds.connectAttr(output, product + ".input1X")
                cmds.connectAttr(weight_plug, product + ".input2X")
                output = product + ".outputX"
    if len(values) > 1:
        cmds.connectAttr(output, bs + ".weight[%d]" % index)
    cmds.addAttr(record, longName="driverNodes", attributeType="message", multi=True)
    for i, node in enumerate(nodes):
        cmds.connectAttr(node + ".message", record + ".driverNodes[%d]" % i)


def _create_pose_target(mesh, bs, controller, values):
    geo_index = geometry_index(bs, mesh)
    name = target_name(controller, values)
    aliases = {alias for _, alias in targets(bs)}
    original = name
    suffix = 2
    while name in aliases:
        name = original[:-4] + "_%02d_BLS" % suffix
        suffix += 1
    index = max([i for i, _ in targets(bs)], default=-1) + 1
    duplicate = cmds.duplicate(mesh, name="poseCorrectiveScratch")[0]
    order = deformation_order(bs, mesh)
    # Native tangent targets store deltas in the moving surface frame. For pre
    # targets, native sculptTarget inverts supported downstream deformation.
    cmds.blendShape(bs, edit=True, target=(mesh, index, duplicate, 1), tangentSpace=order == "post")
    cmds.delete(duplicate)
    cmds.blendShape(bs, edit=True, resetTargetDelta=(geo_index, index))
    cmds.aliasAttr(name, bs + ".weight[%d]" % index)
    record = cmds.createNode("network", name=name + "_poseData")
    cmds.addAttr(record, longName=POSE_MARKER, attributeType="bool", defaultValue=True)
    cmds.addAttr(record, longName="targetIndex", attributeType="long", defaultValue=index)
    _message(bs, record, "blendShape")
    _message(controller, record, "controller")
    _message(mesh, record, "mesh")
    _string(record, "channels", json.dumps(values))
    _string(record, "targetName", name)
    _connect_driver(bs, index, controller, values, record)
    return index, name


@undoable
def add_target(mesh, bs, controller, orientation_system=None, pose_type="swing_twist"):
    _idle()
    mesh = mesh_transform(mesh)
    controller, values = capture_control(controller)
    index, name = _create_pose_target(mesh, bs, controller, values)
    if orientation_system:
        from maya_tools.scripts.tools import orientation_correctives
        orientation_correctives.attach_target(orientation_system, bs, index, pose_record(bs, index), pose_type)
    begin_edit(mesh, bs, index)
    return index, name


def _right_controller(controller):
    from maya_tools.scripts.tools import rig_roles
    root = rig_roles.root_for(controller)
    binding = next((b for b in rig_roles.bindings(root) if b['node'] == rig_roles.path(controller)), None) if root else None
    if binding and binding['side'] in ('L', 'R'):
        return rig_roles.counterpart(controller, side='R' if binding['side'] == 'L' else 'L')
    leaf = controller.rsplit("|", 1)[-1]
    namespace, separator, name = leaf.rpartition(":")
    if not name.startswith("L_"):
        raise ValueError("Mirror L_ to R_ requires a left controller starting with L_.")
    right = (namespace + separator if separator else "") + "R_" + name[2:]
    # Prefer the equivalent hierarchy when both controls share their parent.
    sibling = controller.rsplit("|", 1)[0] + "|" + right
    matches = cmds.ls(sibling, long=True) or cmds.ls(right, long=True) or []
    if len(matches) != 1:
        raise ValueError("The matching right controller is missing or ambiguous: " + right)
    return matches[0]


@contextmanager
def _temporary_values(values):
    """Evaluate a neutral pose without modifying animation or its connections."""
    saved = []
    try:
        for plug, value in values.items():
            old = cmds.getAttr(plug)
            if cmds.getAttr(plug, lock=True):
                if math.isclose(old, value, abs_tol=1e-8):
                    continue
                raise ValueError("Unlock the channel before mirroring: " + plug)
            source = cmds.connectionInfo(plug, sourceFromDestination=True) or ""
            if source:
                cmds.disconnectAttr(source, plug)
            saved.append((plug, old, source))
            cmds.setAttr(plug, value)
        yield
    finally:
        for plug, value, source in reversed(saved):
            cmds.setAttr(plug, value)
            if source:
                cmds.connectAttr(source, plug, force=True)


def _mirrored_channels(mesh, left, right, values):
    mesh_inverse = om.MMatrix(cmds.getAttr(mesh + ".worldInverseMatrix[0]"))
    def frame(node):
        return (om.MMatrix(cmds.getAttr(node + ".offsetParentMatrix"))
                * om.MMatrix(cmds.getAttr(node + ".parentMatrix[0]")) * mesh_inverse)
    left_frame, right_frame = frame(left), frame(right)
    mirrored = []
    for value in values:
        channel = value["channel"]
        axis = "XYZ".index(channel[-1])
        offset = axis * 4
        l_axis = om.MVector(*(left_frame[offset + j] for j in range(3))).normal()
        r_axis = om.MVector(*(right_frame[offset + j] for j in range(3))).normal()
        reflected = om.MVector(-l_axis.x, l_axis.y, l_axis.z)
        alignment = reflected * r_axis
        if abs(alignment) < .98:
            raise ValueError("The controller axes do not mirror across mesh X: " + channel)
        sign = 1 if alignment >= 0 else -1
        # Rotations are axial vectors; reflections reverse their handedness.
        if channel.startswith("rotate"):
            sign *= -1
        default = (cmds.attributeQuery(channel, node=right, listDefault=True) or [0])[0]
        mirrored.append({"channel": channel, "default": default,
                         "pose": default + sign * (value["pose"] - value["default"])})
    return mirrored


def _mesh_points(mesh):
    shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True, type="mesh")[0]
    return om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0)).getPoints(om.MSpace.kObject)


def _symmetry_points(mesh, fallback):
    # Match vertices on the undeformed shape, not an asymmetrically posed body.
    shapes = cmds.ls(cmds.listHistory(mesh) or [], type="mesh", long=True) or []
    for shape in reversed(shapes):
        if not cmds.getAttr(shape + ".intermediateObject"):
            continue
        if (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0] != mesh:
            continue
        points = om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0)).getPoints(om.MSpace.kObject)
        if len(points) == len(fallback):
            return points
    return fallback


def _topology_symmetry(mesh, reference, tolerance):
    """Walk paired faces from center-line edges, allowing sculpted asymmetry."""
    shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True, type="mesh")[0]
    fn = om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))
    faces = [list(fn.getPolygonVertices(i)) for i in range(fn.numPolygons)]
    edge_faces = {}
    for face_index, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edge_faces.setdefault(tuple(sorted((a, b))), []).append(face_index)
    pending = deque()
    mapping = {}
    for (a, b), adjacent in edge_faces.items():
        if len(adjacent) != 2 or abs(reference[a].x) > tolerance or abs(reference[b].x) > tolerance:
            continue
        f, g = adjacent
        x_f = sum(reference[v].x for v in faces[f]) / len(faces[f])
        x_g = sum(reference[v].x for v in faces[g]) / len(faces[g])
        if x_f * x_g >= 0:
            continue
        mapping[a], mapping[b] = a, b
        pending.append((f, g, a, b))
    visited = set()
    while pending:
        f, g, a, b = pending.popleft()
        pair = tuple(sorted((f, g)))
        if pair in visited:
            continue
        visited.add(pair)
        left, right = faces[f], faces[g]
        if len(left) != len(right):
            raise ValueError("Mesh topology does not mirror across the center line.")
        n = len(left)
        start_l, start_r = left.index(a), right.index(mapping[a])
        offset_b = (left.index(b) - start_l) % n
        directions = [s for s in (-1, 1) if right[(start_r + s * offset_b) % n] == mapping[b]]
        if len(directions) != 1:
            raise ValueError("Ambiguous topology symmetry around the center line.")
        direction = directions[0]
        for k in range(n):
            v, opposite = left[(start_l + k) % n], right[(start_r + direction * k) % n]
            if ((v in mapping and mapping[v] != opposite)
                    or (opposite in mapping and mapping[opposite] != v)):
                raise ValueError("Mesh topology does not mirror across the center line.")
            mapping[v], mapping[opposite] = opposite, v
        for v, w in zip(left, left[1:] + left[:1]):
            neighbors_l = [i for i in edge_faces[tuple(sorted((v, w)))] if i != f]
            neighbors_r = [i for i in edge_faces.get(tuple(sorted((mapping[v], mapping[w]))), []) if i != g]
            if len(neighbors_l) != len(neighbors_r) or len(neighbors_l) > 1:
                raise ValueError("Mesh topology does not mirror across the center line.")
            if neighbors_l:
                pending.append((neighbors_l[0], neighbors_r[0], v, w))
    return mapping


def _mirror_deltas(mesh, base, corrected):
    reference = _symmetry_points(mesh, base)
    bounds = [max(p[a] for p in reference) - min(p[a] for p in reference) for a in range(3)]
    tolerance = max(max(bounds) * 1e-4, 1e-5)
    try:
        topology = _topology_symmetry(mesh, reference, tolerance)
    except ValueError:
        # Production bodies may include different detail topology on each side.
        # Interpolate the correction on the mirrored surface in that case.
        return _surface_mirror_deltas(mesh, reference, base, corrected, max(bounds))
    cells = {}
    def cell(p):
        return tuple(math.floor(p[a] / tolerance) for a in range(3))
    for index, point in enumerate(reference):
        cells.setdefault(cell(point), []).append(index)
    deltas = {}
    for index, (before, after) in enumerate(zip(base, corrected)):
        delta = after - before
        if delta.length() < 1e-6:
            continue
        opposite = topology.get(index)
        if opposite is None:
            point = reference[index]
            reflected = om.MPoint(-point.x, point.y, point.z)
            key = cell(reflected)
            candidates = [i for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)
                          for i in cells.get((key[0]+x, key[1]+y, key[2]+z), [])]
            opposite = min(candidates, key=lambda i: (reference[i] - reflected).length(), default=None)
            if opposite is None or (reference[opposite] - reflected).length() > tolerance:
                return _surface_mirror_deltas(mesh, reference, base, corrected, max(bounds))
        if opposite in deltas:
            raise ValueError("Ambiguous symmetry at vertex %d (overlapping vertices)." % index)
        deltas[opposite] = om.MVector(-delta.x, delta.y, delta.z)
    if not deltas:
        raise ValueError("Sculpt and save the left target before mirroring it.")
    return deltas


def _surface_mirror_deltas(mesh, reference, base, corrected, size):
    shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True, type="mesh")[0]
    fn = om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))
    counts, vertices = fn.getVertices()
    data = om.MFnMeshData().create()
    reference_fn = om.MFnMesh()
    reference_object = reference_fn.create(reference, counts, vertices, parent=data)
    intersector = om.MMeshIntersector()
    intersector.create(reference_object, om.MMatrix())
    field = [after - before for before, after in zip(base, corrected)]
    if not any(delta.length() > 1e-6 for delta in field):
        raise ValueError("Sculpt and save the left target before mirroring it.")
    deltas = {}
    for index, point in enumerate(reference):
        # Limit projection to nearby counterparts instead of reaching across
        # unrelated disconnected geometry. Small model asymmetry is supported.
        hit = intersector.getClosestPoint(om.MPoint(-point.x, point.y, point.z), max(size * .02, 1e-4))
        if hit is None:
            continue
        triangle = reference_fn.getPolygonTriangleVertices(hit.face, hit.triangle)
        u, v = hit.barycentricCoords
        delta = field[triangle[0]] * u + field[triangle[1]] * v + field[triangle[2]] * (1-u-v)
        if delta.length() > 1e-6:
            deltas[index] = om.MVector(-delta.x, delta.y, delta.z)
    if not deltas:
        raise ValueError("No corresponding surface was found on the opposite side of mesh X.")
    return deltas


@undoable
def mirror_target_shape(mesh, bs, index, direction="auto"):
    """Copy one side's sculpt to the other side within the same target."""
    _idle()
    if direction not in ("auto", "L_to_R", "R_to_L"):
        raise ValueError("Choose L to R or R to L.")
    mesh = mesh_transform(mesh)
    geometry_index(bs, mesh)
    if index not in dict(targets(bs)):
        raise ValueError("Select a target first.")
    path = _delta_path(bs, mesh, index)
    if cmds.listConnections(path + ".inputGeomTarget", source=True, destination=False):
        raise ValueError("Mirror shape supports saved sculpt targets, not live source meshes.")
    neutral = {bs + ".weight[%d]" % index: 0, bs + ".envelope": 1}
    record = pose_record(bs, index)
    controller = linked(record, "controller") if record else None
    controls = [controller] if controller else []
    if controller:
        leaf = controller.rsplit("|", 1)[-1]
        namespace, separator, name = leaf.rpartition(":")
        if name.startswith(("L_", "R_")):
            opposite = (namespace + separator if separator else "") + ("R_" if name.startswith("L_") else "L_") + name[2:]
            matches = cmds.ls(opposite, long=True) or []
            if len(matches) == 1:
                controls.append(matches[0])
    for control in controls:
        for channel in TR_CHANNELS:
            neutral[control + "." + channel] = (cmds.attributeQuery(channel, node=control, listDefault=True) or [0])[0]
    weight = bs + ".weight[%d]" % index
    old_selection = cmds.ls(selection=True, long=True) or []
    try:
        with _temporary_values(neutral):
            base = _mesh_points(mesh)
            cmds.setAttr(weight, 1)
            corrected = _mesh_points(mesh)
            reference = _symmetry_points(mesh, base)
            size = max(max(p[a] for p in reference) - min(p[a] for p in reference) for a in range(3))
            tolerance = max(size * 1e-4, 1e-5)
            if direction == "auto":
                left_amount = sum((after-before).length() for p, before, after in zip(reference, base, corrected) if p.x > tolerance)
                right_amount = sum((after-before).length() for p, before, after in zip(reference, base, corrected) if p.x < -tolerance)
                alias = dict(targets(bs))[index]
                if max(left_amount, right_amount) <= 1e-6:
                    raise ValueError("This target has no sculpt to mirror. Edit it with LIVE first.")
                if left_amount <= 1e-6:
                    direction = "R_to_L"
                elif right_amount <= 1e-6:
                    direction = "L_to_R"
                elif alias.startswith("R_"):
                    direction = "R_to_L"
                elif alias.startswith("L_"):
                    direction = "L_to_R"
                else:
                    direction = "L_to_R" if left_amount >= right_amount else "R_to_L"
            source_sign = 1 if direction == "L_to_R" else -1
            one_side = om.MPointArray()
            for p, before, after in zip(reference, base, corrected):
                one_side.append(after if source_sign * p.x > tolerance else before)
            if not any((after-before).length() > 1e-6 for before, after in zip(base, one_side)):
                source_side = "left" if source_sign > 0 else "right"
                raise ValueError("This target has no sculpt on its " + source_side + " side.")
            deltas = _mirror_deltas(mesh, base, one_side)
            # Native vertex undo may leave newly allocated zero-delta entries.
            # Register the original sparse arrays first so undo also restores
            # their exact contents after reversing the sculpt operations.
            points_backup = cmds.getAttr(path + ".inputPointsTarget") or []
            components_backup = cmds.getAttr(path + ".inputComponentsTarget") or []
            cmds.setAttr(path + ".inputPointsTarget", len(points_backup), *points_backup, type="pointArray")
            cmds.setAttr(path + ".inputComponentsTarget", len(components_backup), *components_backup, type="componentList")
            cmds.sculptTarget(bs, edit=True, target=index)
            try:
                world = om.MMatrix(cmds.getAttr(mesh + ".worldMatrix[0]"))
                for vertex, point in enumerate(reference):
                    if source_sign * point.x >= -tolerance:
                        continue  # Keep the source side and center line intact.
                    desired = deltas.get(vertex, om.MVector())
                    current = corrected[vertex] - base[vertex]
                    change = desired - current
                    if change.length() < 1e-6:
                        continue
                    displacement = change * world
                    cmds.move(displacement.x, displacement.y, displacement.z,
                              mesh + ".vtx[%d]" % vertex, relative=True, worldSpace=True)
            finally:
                cmds.sculptTarget(bs, edit=True, target=-1)
        return index, dict(targets(bs))[index]
    finally:
        if old_selection:
            cmds.select(old_selection, replace=True)
        else:
            cmds.select(clear=True)


@undoable
def mirror_target(mesh, bs, index):
    """Create an independent R_ corrective, preserving the L_ target and pose."""
    _idle()
    mesh = mesh_transform(mesh)
    geometry_index(bs, mesh)
    record = pose_record(bs, index)
    if record:
        from maya_tools.scripts.tools import combination_correctives
        if combination_correctives.data(record):
            return combination_correctives.mirror(mesh, bs, index)
    if not record:
        raise ValueError("Select a left pose target created with Add.")
    left = linked(record, "controller")
    if not left:
        raise ValueError("The captured left controller no longer exists.")
    right = _right_controller(left)
    path = _delta_path(bs, mesh, index)
    if cmds.listConnections(path + ".inputGeomTarget", source=True, destination=False):
        raise ValueError("Mirror supports saved sculpt targets, not live source meshes.")
    values = json.loads(cmds.getAttr(record + ".channels"))
    neutral = {node + "." + channel: (cmds.attributeQuery(channel, node=node, listDefault=True) or [0])[0]
               for node in (left, right) for channel in TR_CHANNELS}
    weight = bs + ".weight[%d]" % index
    # Evaluate source deltas at neutral, then author the reflected displacement
    # through native sculptTarget. Raw flipTarget treats tangent-space deltas as
    # object vectors and can reverse the displacement on post/tangent targets.
    neutral[weight] = 0
    old_selection = cmds.ls(selection=True, long=True) or []
    try:
        with _temporary_values(neutral):
            mirrored_values = _mirrored_channels(mesh, left, right, values)
            base = _mesh_points(mesh)
            cmds.setAttr(weight, 1)
            corrected = _mesh_points(mesh)
            cmds.setAttr(weight, 0)
            deltas = _mirror_deltas(mesh, base, corrected)
            new_index, name = _create_pose_target(mesh, bs, right, mirrored_values)
            from maya_tools.scripts.tools import orientation_correctives as orientation
            source_system = orientation.linked(record, "orientationSystem")
            if source_system:
                driver = orientation.linked(source_system, "joint")
                reference = orientation.linked(source_system, "reference")
                right_driver = _right_controller(driver)
                ref_leaf = reference.rsplit("|", 1)[-1].split(":")[-1]
                right_reference = _right_controller(reference) if ref_leaf.startswith("L_") else reference
                right_system = next((s for s in orientation.systems()
                                     if cmds.ls(orientation.linked(s, "joint"), long=True) == cmds.ls(right_driver, long=True)
                                     and cmds.ls(orientation.linked(s, "reference"), long=True) == cmds.ls(right_reference, long=True)), None)
                if not right_system:
                    right_system = orientation.create_system(right_driver, right_reference,
                        source_system.replace("L_", "R_", 1), cmds.getAttr(source_system + ".twistAxis"))
                pi = orientation.linked(source_system, "interpolator")
                sample = cmds.getAttr(record + ".orientationPose")
                kind = cmds.getAttr(pi + ".pose[%d].poseType" % sample)
                with _temporary_values({right + "." + v["channel"]: v["pose"] for v in mirrored_values}):
                    orientation.attach_target(right_system, bs, new_index, pose_record(bs, new_index),
                                              next(k for k, v in orientation.POSE_TYPES.items() if v == kind))
            new_weight = bs + ".weight[%d]" % new_index
            with _temporary_values({new_weight: 1}):
                cmds.sculptTarget(bs, edit=True, target=new_index)
                try:
                    world = om.MMatrix(cmds.getAttr(mesh + ".worldMatrix[0]"))
                    for vertex, delta in deltas.items():
                        displacement = delta * world
                        cmds.move(displacement.x, displacement.y, displacement.z,
                                  mesh + ".vtx[%d]" % vertex, relative=True, worldSpace=True)
                finally:
                    cmds.sculptTarget(bs, edit=True, target=-1)
        return new_index, name
    finally:
        if old_selection:
            cmds.select(old_selection, replace=True)
        else:
            cmds.select(clear=True)


@undoable
def go_to_pose(bs, index, neutral=False):
    _idle()
    record = pose_record(bs, index)
    if record:
        from maya_tools.scripts.tools import combination_correctives as combinations
        snapshot = combinations.data(record)
        if snapshot:
            return combinations.go_to_pose(snapshot, neutral)
    if not record:
        raise ValueError("This target has no controller pose captured by this tool.")
    controller = linked(record, "controller")
    if not controller:
        raise ValueError("The captured controller no longer exists.")
    values = json.loads(cmds.getAttr(record + ".channels"))
    plugs = [controller + "." + value["channel"] for value in values]
    changes = [(plug, value["default" if neutral else "pose"]) for plug, value in zip(plugs, values)
               if not math.isclose(cmds.getAttr(plug), value["default" if neutral else "pose"], abs_tol=1e-5)]
    if any(not cmds.getAttr(plug, settable=True) for plug, _ in changes):
        raise ValueError("A captured channel is locked or connected. Pose it through the rig instead.")
    for plug, value in changes:
        cmds.setAttr(plug, value)


@undoable
def neutral_pose(mesh):
    """Reset this mesh's rig controls to declared defaults in one undo step."""
    _idle()
    mesh = mesh_transform(mesh)
    root = "|" + mesh.split("|")[1]
    controls = [node for node in cmds.ls(type="transform", long=True) or []
                if (node == root or node.startswith(root + "|"))
                and node.rsplit("|", 1)[-1].endswith("_CTL")]
    if not controls:
        raise ValueError("No rig controls ending in _CTL were found under the loaded mesh's root.")
    changes, skipped = [], []
    for control in controls:
        for attr in cmds.listAttr(control, keyable=True, scalar=True) or []:
            if attr == "visibility":
                continue
            defaults = cmds.attributeQuery(attr, node=control, listDefault=True)
            if not defaults or len(defaults) != 1 or not isinstance(defaults[0], (int, float)):
                continue
            plug = control + "." + attr
            current = cmds.getAttr(plug)
            if not isinstance(current, (int, float)) or math.isclose(current, defaults[0], abs_tol=1e-6):
                continue
            if not cmds.getAttr(plug, settable=True) or cmds.getAttr(plug, lock=True):
                skipped.append(plug)
                continue
            changes.append((plug, defaults[0]))
    for plug, value in changes:
        cmds.setAttr(plug, value)
    return {"controls": len(controls), "channels": len(changes), "skipped": skipped}


@undoable
def begin_edit(mesh, bs, index, restore_pose=False):
    _idle()
    mesh = mesh_transform(mesh)
    if index not in [i for i, _ in targets(bs)]:
        raise ValueError("Select a target first.")
    path = _delta_path(bs, mesh, index)
    if cmds.listConnections(path + ".inputGeomTarget", source=True, destination=False):
        raise ValueError("This target has a live source mesh. Edit that source in Maya, or create a pose target with Add.")
    plug = bs + ".weight[%d]" % index
    if cmds.getAttr(plug, lock=True):
        raise ValueError("The target weight is locked.")
    if restore_pose:
        go_to_pose(bs, index)
    if abs(cmds.getAttr(bs + ".envelope")) < 1e-8:
        raise ValueError("Enable the blendshape envelope before editing.")
    session = cmds.createNode("network", name="poseCorrectiveEditSession")
    cmds.addAttr(session, longName=EDIT_MARKER, attributeType="bool", defaultValue=True)
    cmds.addAttr(session, longName="targetIndex", attributeType="long", defaultValue=index)
    _message(bs, session, "blendShape")
    _message(mesh, session, "mesh")
    source = cmds.connectionInfo(plug, sourceFromDestination=True) or ""
    _string(session, "weightSource", source)
    cmds.addAttr(session, longName="oldWeight", attributeType="double", defaultValue=cmds.getAttr(plug))
    backup = {"points": cmds.getAttr(path + ".inputPointsTarget") or [],
              "components": cmds.getAttr(path + ".inputComponentsTarget") or []}
    _string(session, "deltaBackup", json.dumps(backup))
    _string(session, "aliasBackup", json.dumps(cmds.aliasAttr(bs, query=True) or []))
    record = pose_record(bs, index)
    if record:
        name = dict(targets(bs))[index]
        if not cmds.attributeQuery("targetName", node=record, exists=True):
            _string(record, "targetName", name)
        else:
            cmds.setAttr(record + ".targetName", name, type="string")
    if source:
        cmds.disconnectAttr(source, plug)
    cmds.setAttr(plug, 1)
    cmds.sculptTarget(bs, edit=True, target=index)
    cmds.select(mesh, replace=True)
    return session


@undoable
def finish_edit(save=True):
    session = edit_session()
    if not session:
        raise ValueError("No target is being edited.")
    bs, mesh = linked(session, "blendShape"), linked(session, "mesh")
    index = cmds.getAttr(session + ".targetIndex")
    cmds.sculptTarget(bs, edit=True, target=-1)
    if not save:
        backup = json.loads(cmds.getAttr(session + ".deltaBackup"))
        path = _delta_path(bs, mesh, index)
        cmds.setAttr(path + ".inputPointsTarget", len(backup["points"]), *backup["points"], type="pointArray")
        cmds.setAttr(path + ".inputComponentsTarget", len(backup["components"]), *backup["components"], type="componentList")
    plug = bs + ".weight[%d]" % index
    source = cmds.getAttr(session + ".weightSource")
    if source and cmds.objExists(source):
        cmds.connectAttr(source, plug, force=True)
    else:
        cmds.setAttr(plug, cmds.getAttr(session + ".oldWeight"))
    if cmds.attributeQuery("aliasBackup", node=session, exists=True):
        _restore_aliases(bs, json.loads(cmds.getAttr(session + ".aliasBackup")))
    restore_target_names(bs)
    cmds.delete(session)


@undoable
def remove_target(mesh, bs, index):
    from maya_tools.scripts.tools import combination_correctives as combinations
    if combinations.consumers(bs, index):
        raise ValueError('Delete the dependent combination targets first.')
    _idle()
    if len(cmds.blendShape(bs, query=True, geometry=True) or []) > 1:
        raise ValueError("This blendshape drives multiple meshes. Delete its target in Maya to manage all bases together.")
    geo_index = geometry_index(bs, mesh)
    if index not in [i for i, _ in targets(bs)]:
        raise ValueError("Select a target first.")
    record = pose_record(bs, index)
    plug = bs + ".weight[%d]" % index
    alias = cmds.aliasAttr(plug, query=True)
    aliases = cmds.aliasAttr(bs, query=True) or []
    if alias:
        cmds.aliasAttr(plug, remove=True)
    source = cmds.connectionInfo(plug, sourceFromDestination=True)
    if source:
        cmds.disconnectAttr(source, plug)
    cmds.removeMultiInstance(bs + ".inputTarget[%d].inputTargetGroup[%d]" % (geo_index, index), b=True)
    cmds.removeMultiInstance(plug, b=True)
    _restore_aliases(bs, aliases)
    if record:
        from maya_tools.scripts.tools import orientation_correctives
        orientation_correctives.detach_target(record)
        nodes = [n for n in (cmds.listConnections(record + ".driverNodes", source=True, destination=False) or [])
                 if cmds.objExists(n)]
        # Do not delete an SDK that another scene consumer also uses.
        disposable = [n for n in nodes if not (cmds.listConnections(n, source=False, destination=True) or [])]
        cmds.delete(record)
        for node in nodes:
            if not cmds.objExists(node):
                continue
            destinations = cmds.listConnections(node, source=False, destination=True) or []
            if not destinations or all(d in nodes for d in destinations):
                disposable.append(node)
        if disposable:
            cmds.delete([n for n in dict.fromkeys(disposable) if cmds.objExists(n)])


def show():
    from maya_tools.scripts.ui import pose_blendshapes_UI
    return pose_blendshapes_UI.show()
