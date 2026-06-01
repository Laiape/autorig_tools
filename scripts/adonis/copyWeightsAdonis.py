"""
AdonisFX weight map transfer for adnSkin, adnFat, adnSkinMerge and adnMuscle.

USAGE
-----
One-click launcher with UI:

    from scripts.adonis import copyWeightsAdonis
    copyWeightsAdonis.show()

Or drag-and-drop this file into a Maya viewport to launch the UI directly.

The UI has four tabs:
  * Transfer      -> source mesh + destination mesh, copies weight maps and
                     mirrors all incoming connections of the source deformer.
  * Copy/Paste    -> in-memory buffer. Copy from one selected mesh, paste onto
                     another (e.g. R side painted, paste onto L side with
                     X-mirror enabled).
  * Mirror L->R   -> mirrors AdnRelax/Push/Mush scalar attrs from L_ to R_ side.
  * Replace Mesh  -> full mesh substitution in the rig setup. Transfers
                     skinCluster + all AdonisFX deformers from OLD mesh to NEW
                     mesh, re-parents and renames as needed.

API (no UI):

    from scripts.adonis.copyWeightsAdonis import (
        copy_from_selection, copy_weights, apply_and_copy,
        copy_to_buffer, paste_from_buffer, clear_buffer,
        replace_mesh_in_setup,
    )

    # Buffer-based copy/paste
    copy_to_buffer()                                          # source selected
    paste_from_buffer(mirror_x=True)                          # dest selected
    paste_from_buffer(maps=["weightMap"], mirror_x=False)

    # Full mesh replacement
    replace_mesh_in_setup("body_OLD", "body_NEW",
                           transfer_skin=True, transfer_adonis=True,
                           reparent=True, rename=True, delete_old=False)

Same-topology meshes are copied index-for-index.
Different-topology meshes (and X-mirror pastes) use closest-point +
barycentric interpolation.
"""

import logging
import re

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om

log = logging.getLogger(__name__)
if not log.handlers:
    log.setLevel(logging.INFO)
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[adonisCopy] %(message)s"))
    log.addHandler(_h)
    log.propagate = False

# ---------------------------------------------------------------------------
# Weight-map registry
# Each entry: map_name -> (list_compound_attr, element_attr)
# Attribute path: node.list_compound_attr[0].element_attr[i]
# ---------------------------------------------------------------------------

_SKIN_MAPS = {
    "weightMap":                    ("weightList",                       "weights"),
    "compressionResistanceMap":     ("compressionResistanceList",        "compressionResistance"),
    "stretchingResistanceMap":      ("stretchingResistanceList",         "stretchingResistance"),
    "globalDampingMap":             ("globalDampingList",                "globalDamping"),
    "hardConstraintsMap":           ("hardConstraintsList",              "hardConstraints"),
    "softConstraintsMap":           ("softConstraintsList",              "softConstraints"),
    "slideConstraintsMap":          ("slideConstraintsList",             "slideConstraints"),
    "slidingDistanceMultiplierMap": ("maxSlidingDistanceMultiplierList", "maxSlidingDistanceMultiplier"),
    "massMap":                      ("massList",                         "mass"),
    "shapePreservationMap":         ("shapePreservationList",            "shapePreservation"),
    "scWeightsMap":                 ("scWeightsList",                    "scWeights"),
    "scThicknessMultiplierMap":     ("scThicknessMultiplierList",        "scThicknessMultiplier"),
    "scPointRadiusMultiplierMap":   ("scPointRadiusMultiplierList",      "scPointRadiusMultiplier"),
}

_FAT_MAPS = {
    "weightMap":                  ("weightList",                    "weights"),
    "globalDampingMap":           ("globalDampingList",             "globalDamping"),
    "hardConstraintsMap":         ("hardConstraintsList",           "hardConstraints"),
    "massMap":                    ("massList",                      "mass"),
    "shapePreservationMap":       ("shapePreservationList",         "shapePreservation"),
    "volumeShapePreservationMap": ("volumeShapePreservationList",   "volumeShapePreservation"),
}

_SKIN_MERGE_MAPS = {
    "weightMap": ("weightList", "weights"),
    "blendMap":  ("blendList",  "blend"),
}

_MUSCLE_MAPS = {
    "attachmentsToGeometryMap":     ("attachmentsToGeometryList",        "attachmentsToGeometry"),
    "attachmentsToTransformMap":    ("attachmentsToTransformList",       "attachmentsToTransform"),
    "compressionResistanceMap":     ("compressionResistanceList",        "compressionResistance"),
    "stretchingResistanceMap":      ("stretchingResistanceList",         "stretchingResistance"),
    "fibersMultiplierMap":          ("fibersMultiplierList",             "fibersMultiplier"),
    "globalDampingMap":             ("globalDampingList",                "globalDamping"),
    "massMap":                      ("massList",                         "mass"),
    "shapePreservationMap":         ("shapePreservationList",            "shapePreservation"),
    "slideOnGeometryMap":           ("slideOnGeometryList",              "slideOnGeometry"),
    "slideOnSegmentMap":            ("slideOnSegmentList",               "slideOnSegment"),
    "slidingDistanceMultiplierMap": ("slidingDistanceMultiplierList",    "slidingDistanceMultiplier"),
}

_RELAX_MAPS = {}
_PUSH_MAPS  = {}
_MUSH_MAPS  = {}

_DEFORMER_MAPS = {
    "AdnSkin":      _SKIN_MAPS,
    "AdnFat":       _FAT_MAPS,
    "AdnSkinMerge": _SKIN_MERGE_MAPS,
    "AdnMuscle":    _MUSCLE_MAPS,
    "AdnRelax":     _RELAX_MAPS,
    "AdnPush":      _PUSH_MAPS,
    "AdnMush":      _MUSH_MAPS,
}

_MIRROR_LR_TYPES = ("AdnRelax", "AdnPush", "AdnMush")

# ---------------------------------------------------------------------------
# Scalar attribute registries
# ---------------------------------------------------------------------------

_GRAVITY_DIRECTION_ATTR = "gravityDirection"

_BASE_SCALAR_ATTRS = [
    "enable", "envelope", "iterations", "stiffnessMultiplier",
    "prerollStartTime", "startTime", "currentTime",
    "timeScale", "spaceScale", "spaceScaleMode",
    "gravity", _GRAVITY_DIRECTION_ATTR,
]

_SKIN_SCALAR_ATTRS = _BASE_SCALAR_ATTRS + [
    "substeps", "material",
    "initShapePreservationAtStartTime", "initUberAtStartTime",
    "useCustomStiffness", "stiffness",
    "distanceStiffnessOverride", "hardStiffnessOverride", "shapeStiffnessOverride",
    "slideStiffnessOverride", "softStiffnessOverride",
    "pointMassMode", "density", "globalMassMultiplier",
    "triangulateMesh", "globalDampingMultiplier", "inertiaDamper",
    "restLengthMultiplier", "maxSlidingDistance",
    "compressionMultiplier", "stretchingMultiplier",
    "attenuationVelocityFactor", "slidingConstraintsMode",
    "selfCollisions", "selfCollisionsMode", "selfCollisionsQualityMode",
    "scIgnoreRestIntersections", "scIterations",
    "scThickness", "scPointRadiusScale", "scPointRadiusMode", "scSearchRadius",
    "scEnableRelax", "scRelaxNeighbors", "scRelaxIterations",
    "scRelaxWeight", "scRelaxSmooth", "scRelaxRelax",
    "scRelaxPushInRatio", "scRelaxPushInThreshold",
    "scRelaxPushOutRatio", "scRelaxPushOutThreshold",
    "scMinDisplacement", "scMaxDisplacement",
    "scLastSubstepOnly", "scLastIterationOnly",
]

_FAT_SCALAR_ATTRS = _BASE_SCALAR_ATTRS + [
    "substeps", "material",
    "initHardAtStartTime", "initShapePreservationAtStartTime",
    "useCustomStiffness", "stiffness",
    "hardStiffnessOverride", "volumeShapeStiffnessOverride", "shapeStiffnessOverride",
    "pointMassMode", "density", "globalMassMultiplier",
    "globalDampingMultiplier", "inertiaDamper", "attenuationVelocityFactor",
    "divisions",
]

_SKIN_MERGE_SCALAR_ATTRS = [
    "enable", "envelope", "startTime", "currentTime",
    "initializationTime",
]

_DEFORMER_SCALAR_ATTRS = {
    "AdnSkin":      _SKIN_SCALAR_ATTRS,
    "AdnFat":       _FAT_SCALAR_ATTRS,
    "AdnSkinMerge": _SKIN_MERGE_SCALAR_ATTRS,
}

# ---------------------------------------------------------------------------
# Connection-mirroring registry
# ---------------------------------------------------------------------------

# Compound/indexed attrs handled explicitly in copy_connections (skipped by generic mirror).
# AdnFat: baseMesh and baseMatrix are single (non-indexed) connections — handled explicitly
#         but NOT added here so the generic handler acts as fallback.
# AdnSkin: targets[] is an indexed compound — must be handled explicitly.
_INDEXED_COMPOUND_ATTRS = {
    "AdnSkin":      {"targets"},
    "AdnFat":       set(),
    "AdnSkinMerge": set(),
    "AdnMuscle":    {"targets"},
    "AdnRelax":     set(),
    "AdnPush":      set(),
    "AdnMush":      set(),
}

# Known single-connection inputs per deformer type:
# AdnFat:    baseMesh  (worldMesh)  ← fascia shape
#            baseMatrix (worldMatrix) ← fascia transform
#            attenuationMatrix ← optional rig transform
# AdnSkin:   targets[i].targetWorldMesh ← fat/muscle shape
#            targets[i].targetWorldMatrix ← fat/muscle transform
#            attenuationMatrix ← optional
# AdnMuscle: targets[i].targetWorldMesh / targetWorldMatrix
#            activationList[i] ← from sensor nodes or activation graph
#            restShapeMesh ← optional sculpted reference

_NEVER_MIRROR_ATTRS = {
    "input",
    "outputGeometry",
    "originalGeometry",
    "message",
    "caching",
    "frozen",
    "isHistoricallyInteresting",
    "nodeState",
    "binMembership",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _attr_path(node, list_attr, elem_attr, index):
    return "{0}.{1}[0].{2}[{3}]".format(node, list_attr, elem_attr, index)


def _get_weights(node, list_attr, elem_attr, count):
    return [cmds.getAttr(_attr_path(node, list_attr, elem_attr, i)) for i in range(count)]


def _set_weights(node, list_attr, elem_attr, weights):
    for i, w in enumerate(weights):
        cmds.setAttr(_attr_path(node, list_attr, elem_attr, i), w)


def _vertex_count(mesh_shape):
    return cmds.polyEvaluate(mesh_shape, vertex=True)


def _get_mesh_shape(node):
    """Return the first mesh shape under *node*, or *node* itself if already a shape."""
    if cmds.nodeType(node) == "mesh":
        return node
    shapes = cmds.listRelatives(node, shapes=True, type="mesh", fullPath=True) or []
    return shapes[0] if shapes else None


def _find_deformer(mesh_shape):
    """Return (node_name, node_type) for the first Adn* deformer in mesh history."""
    for node in (cmds.listHistory(mesh_shape, pruneDagObjects=True) or []):
        node_type = cmds.nodeType(node)
        if node_type in _DEFORMER_MAPS:
            return node, node_type
    return None, None


def _find_all_deformers_in_history(mesh_shape):
    """Return [(node_name, node_type), ...] for every Adn* deformer in mesh history."""
    found = []
    seen = set()
    for node in (cmds.listHistory(mesh_shape, pruneDagObjects=True) or []):
        node_type = cmds.nodeType(node)
        if node_type in _DEFORMER_MAPS and node not in seen:
            seen.add(node)
            found.append((node, node_type))
    return found


def _available_maps(deformer_node):
    """Return the subset of registered maps that actually exist on *deformer_node*."""
    node_type = cmds.nodeType(deformer_node)
    registry  = _DEFORMER_MAPS.get(node_type, {})
    available = {}
    for map_name, (list_attr, elem_attr) in registry.items():
        if cmds.attributeQuery(list_attr, node=deformer_node, exists=True):
            available[map_name] = (list_attr, elem_attr)
        else:
            log.debug("Map '%s' not present on %s (attr '%s' missing).",
                      map_name, deformer_node, list_attr)
    return available


def _dag_path(mesh_shape):
    sel = om.MSelectionList()
    sel.add(mesh_shape)
    return sel.getDagPath(0)


def _barycentric(p, a, b, c):
    """Barycentric coords (u, v, w) of point p inside triangle (a, b, c)."""
    v0 = om.MVector(b.x - a.x, b.y - a.y, b.z - a.z)
    v1 = om.MVector(c.x - a.x, c.y - a.y, c.z - a.z)
    v2 = om.MVector(p.x - a.x, p.y - a.y, p.z - a.z)

    d00 = v0 * v0
    d01 = v0 * v1
    d11 = v1 * v1
    d20 = v2 * v0
    d21 = v2 * v1

    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)

    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return (u, v, w)


def _build_spatial_map(src_shape, dst_shape, flip_x=False):
    """
    For every vertex in *dst_shape*, find the triangle on *src_shape* whose
    closest point is nearest, then return barycentric weights.

    If *flip_x* is True, each destination point is mirrored across the YZ
    plane before querying the source mesh (X-mirror pattern).
    """
    fn_src = om.MFnMesh(_dag_path(src_shape))
    fn_dst = om.MFnMesh(_dag_path(dst_shape))

    tri_counts, tri_verts = fn_src.getTriangles()
    dst_points = fn_dst.getPoints(om.MSpace.kWorld)

    tri_offsets = []
    offset = 0
    for count in tri_counts:
        tri_offsets.append(offset)
        offset += count

    result = []
    for pt in dst_points:
        query_pt = om.MPoint(-pt.x, pt.y, pt.z) if flip_x else pt
        closest_pt, face_id = fn_src.getClosestPoint(query_pt, om.MSpace.kWorld)

        face_tri_count = tri_counts[face_id]
        face_tri_base  = tri_offsets[face_id] * 3

        best_verts = None
        best_bary  = None
        best_dist  = float("inf")

        for t in range(face_tri_count):
            base = face_tri_base + t * 3
            tv = (tri_verts[base], tri_verts[base + 1], tri_verts[base + 2])
            tp = [fn_src.getPoint(v, om.MSpace.kWorld) for v in tv]
            bary = _barycentric(closest_pt, tp[0], tp[1], tp[2])

            if all(b >= -1e-6 for b in bary):
                best_verts = tv
                best_bary  = bary
                break

            cx = (tp[0].x + tp[1].x + tp[2].x) / 3.0
            cy = (tp[0].y + tp[1].y + tp[2].y) / 3.0
            cz = (tp[0].z + tp[1].z + tp[2].z) / 3.0
            dist = (closest_pt.x - cx) ** 2 + (closest_pt.y - cy) ** 2 + (closest_pt.z - cz) ** 2
            if dist < best_dist:
                best_dist  = dist
                best_verts = tv
                best_bary  = bary

        result.append((best_verts, best_bary))

    return result


def _mirror_incoming_connections(src_node, dst_node, skip_attrs):
    """Walk every incoming connection on src_node and replicate it on dst_node."""
    raw = cmds.listConnections(
        src_node,
        connections=True,
        source=True,
        destination=False,
        plugs=True,
    ) or []

    mirrored = []
    for i in range(0, len(raw), 2):
        dest_plug_on_src = raw[i]
        upstream_plug    = raw[i + 1]

        _, _, attr_path = dest_plug_on_src.partition(".")
        if not attr_path:
            continue

        root = attr_path.split(".", 1)[0].split("[", 1)[0]

        if root in _NEVER_MIRROR_ATTRS:
            continue
        if root in skip_attrs:
            continue

        if not cmds.attributeQuery(root, node=dst_node, exists=True):
            log.debug("Skipping %s - attribute missing on destination.", attr_path)
            continue

        dst_plug = "{0}.{1}".format(dst_node, attr_path)

        existing = cmds.listConnections(
            dst_plug, source=True, destination=False, plugs=True
        ) or []
        if existing:
            log.debug("Skipping %s - destination already has incoming connection from %s.",
                      attr_path, existing[0])
            continue

        try:
            cmds.connectAttr(upstream_plug, dst_plug, force=True)
            mirrored.append((upstream_plug, dst_plug))
            log.debug("Mirrored connection: %s -> %s", upstream_plug, dst_plug)
        except Exception as exc:
            log.warning("Could not mirror %s -> %s: %s", upstream_plug, dst_plug, exc)

    return mirrored


def _transfer_weight_maps(src_node, dst_node, maps=None):
    """Inner weight-map transfer - no undo wrapper."""
    src_type = cmds.nodeType(src_node)
    registry = _available_maps(src_node)
    maps_to_copy = list(registry.keys()) if maps is None else maps

    unknown = [m for m in maps_to_copy if m not in registry]
    if unknown:
        raise ValueError(
            "Unknown or unavailable map(s) for {0}: {1}. Available: {2}".format(
                src_type, unknown, sorted(registry.keys())
            )
        )

    src_geo = cmds.deformer(src_node, q=True, geometry=True)
    dst_geo = cmds.deformer(dst_node, q=True, geometry=True)
    if not src_geo:
        raise RuntimeError("Cannot resolve geometry from: {0}".format(src_node))
    if not dst_geo:
        raise RuntimeError("Cannot resolve geometry from: {0}".format(dst_node))

    src_shape = src_geo[0]
    dst_shape = dst_geo[0]
    src_vtx   = _vertex_count(src_shape)
    dst_vtx   = _vertex_count(dst_shape)

    same_topo = src_vtx == dst_vtx
    if not same_topo:
        log.info(
            "Vertex count mismatch (%d vs %d) - building spatial map for %s -> %s.",
            src_vtx, dst_vtx, src_node, dst_node,
        )
        spatial_map = _build_spatial_map(src_shape, dst_shape)

    transferred = []
    for map_name in maps_to_copy:
        list_attr, elem_attr = registry[map_name]
        src_weights = _get_weights(src_node, list_attr, elem_attr, src_vtx)

        if same_topo:
            dst_weights = list(src_weights)
        else:
            dst_weights = []
            for tri_verts, bary in spatial_map:
                w = sum(bary[k] * src_weights[tri_verts[k]] for k in range(3))
                dst_weights.append(max(0.0, min(1.0, w)))

        _set_weights(dst_node, list_attr, elem_attr, dst_weights)
        transferred.append(map_name)
        log.debug("Transferred map '%s'.", map_name)

    return transferred


# ---------------------------------------------------------------------------
# Public API - direct transfer (mesh -> mesh)
# ---------------------------------------------------------------------------

def copy_weights(src_node, dst_node, maps=None, mirror_connections=True):
    """
    Copy AdonisFX weight maps from *src_node* to *dst_node*.
    Both nodes must already exist and be the same deformer type.
    """
    for node in (src_node, dst_node):
        if not cmds.objExists(node):
            raise ValueError("Node does not exist: {0}".format(node))

    src_type = cmds.nodeType(src_node)
    dst_type = cmds.nodeType(dst_node)

    if src_type != dst_type:
        raise TypeError(
            "Source and destination must be the same deformer type "
            "({0} vs {1}).".format(src_type, dst_type)
        )
    if src_type not in _DEFORMER_MAPS:
        raise TypeError("Unsupported deformer type: {0}".format(src_type))

    cmds.undoInfo(openChunk=True, chunkName="adnCopyWeights")
    try:
        if mirror_connections:
            copy_connections(src_node, dst_node)
        transferred = _transfer_weight_maps(src_node, dst_node, maps=maps)
    finally:
        cmds.undoInfo(closeChunk=True)

    log.info(
        "AdonisFX weight transfer done: %s -> %s | %d map(s): %s",
        src_node, dst_node, len(transferred), transferred,
    )
    return transferred


def copy_scalar_attrs(src_node, dst_node):
    """Copy all scalar (non-weight) solver attributes from src to dst."""
    node_type = cmds.nodeType(src_node)
    attrs = _DEFORMER_SCALAR_ATTRS.get(node_type, [])
    copied = []

    for attr in attrs:
        if not cmds.attributeQuery(attr, node=src_node, exists=True):
            continue
        if not cmds.attributeQuery(attr, node=dst_node, exists=True):
            continue

        if cmds.listConnections("{0}.{1}".format(dst_node, attr), source=True, destination=False):
            log.debug("Skipping %s - incoming connection on destination.", attr)
            continue

        try:
            if attr == _GRAVITY_DIRECTION_ATTR:
                val = cmds.getAttr("{0}.{1}".format(src_node, attr))[0]
                cmds.setAttr("{0}.{1}".format(dst_node, attr), val[0], val[1], val[2], type="double3")
            else:
                val = cmds.getAttr("{0}.{1}".format(src_node, attr))
                cmds.setAttr("{0}.{1}".format(dst_node, attr), val)
            copied.append(attr)
        except Exception as exc:
            log.warning("Could not copy attr '%s': %s", attr, exc)

    log.debug("Copied %d scalar attrs from %s -> %s.", len(copied), src_node, dst_node)
    return copied


def copy_connections(src_node, dst_node):
    """Replicate every incoming connection of src_node onto dst_node."""
    node_type = cmds.nodeType(src_node)
    summary = {}

    if node_type == "AdnSkin":
        # targets[] is an indexed compound — connect worldMesh + worldMatrix per target.
        # Targets are the fat/muscle meshes driving the skin simulation.
        raw_targets = cmds.listConnections("{0}.targets".format(src_node)) or []
        seen = set()
        targets = []
        for t in raw_targets:
            if t not in seen:
                seen.add(t)
                targets.append(t)

        connected_targets = []
        for i, target in enumerate(targets):
            try:
                cmds.connectAttr(
                    "{0}.worldMesh[0]".format(target),
                    "{0}.targets[{1}].targetWorldMesh".format(dst_node, i),
                    force=True,
                )
                cmds.connectAttr(
                    "{0}.worldMatrix[0]".format(target),
                    "{0}.targets[{1}].targetWorldMatrix".format(dst_node, i),
                    force=True,
                )
                connected_targets.append(target)
                log.debug("Connected target[%d]: %s -> %s", i, target, dst_node)
            except Exception as exc:
                log.warning("Could not connect target '%s' to %s: %s", target, dst_node, exc)

        if connected_targets:
            summary["targets"] = connected_targets

    elif node_type == "AdnFat":
        # baseMesh is a single (non-indexed) connection from the fascia mesh.
        # baseMatrix is the corresponding world matrix.
        # The generic mirror handles these too, but explicit connection ensures
        # the fascia→fat dependency survives even if the attribute is lazily initialized.
        for mesh_attr, matrix_attr in (("baseMesh", "baseMatrix"),):
            if not cmds.attributeQuery(mesh_attr, node=src_node, exists=True):
                continue
            src_meshes = cmds.listConnections(
                "{0}.{1}".format(src_node, mesh_attr), shapes=True
            ) or []
            if not src_meshes:
                continue
            fascia_shape = src_meshes[0]
            fascia_xform = (
                cmds.listRelatives(fascia_shape, parent=True, fullPath=True) or [None]
            )[0]
            try:
                cmds.connectAttr(
                    "{0}.worldMesh[0]".format(fascia_shape),
                    "{0}.{1}".format(dst_node, mesh_attr),
                    force=True,
                )
                if fascia_xform and cmds.attributeQuery(matrix_attr, node=dst_node, exists=True):
                    cmds.connectAttr(
                        "{0}.worldMatrix[0]".format(fascia_xform),
                        "{0}.{1}".format(dst_node, matrix_attr),
                        force=True,
                    )
                summary["base_mesh"] = fascia_shape
                log.debug("Connected base mesh '%s' -> %s", fascia_shape, dst_node)
            except Exception as exc:
                log.warning("Could not connect base mesh '%s' to %s: %s",
                            fascia_shape, dst_node, exc)

    elif node_type == "AdnMuscle":
        # targets[] drives muscle-to-geometry attachments (same compound pattern as AdnSkin).
        raw_targets = cmds.listConnections("{0}.targets".format(src_node)) or []
        seen = set()
        targets = []
        for t in raw_targets:
            if t not in seen:
                seen.add(t)
                targets.append(t)

        connected_targets = []
        for i, target in enumerate(targets):
            try:
                cmds.connectAttr(
                    "{0}.worldMesh[0]".format(target),
                    "{0}.targets[{1}].targetWorldMesh".format(dst_node, i),
                    force=True,
                )
                cmds.connectAttr(
                    "{0}.worldMatrix[0]".format(target),
                    "{0}.targets[{1}].targetWorldMatrix".format(dst_node, i),
                    force=True,
                )
                connected_targets.append(target)
            except Exception as exc:
                log.warning("Could not connect target '%s' to %s: %s", target, dst_node, exc)

        if connected_targets:
            summary["targets"] = connected_targets

    skip = _INDEXED_COMPOUND_ATTRS.get(node_type, set())
    mirrored = _mirror_incoming_connections(src_node, dst_node, skip_attrs=skip)
    if mirrored:
        summary["mirrored"] = mirrored
        log.info("Mirrored %d incoming connection(s) from %s to %s.",
                 len(mirrored), src_node, dst_node)

    return summary


def apply_and_copy(src_node, dst_shape, maps=None):
    """Apply same deformer type to dst_shape, then mirror everything."""
    if not cmds.objExists(src_node):
        raise ValueError("Source node does not exist: {0}".format(src_node))

    deformer_type = cmds.nodeType(src_node)
    if deformer_type not in _DEFORMER_MAPS:
        raise TypeError("Unsupported deformer type: {0}".format(deformer_type))

    shape = _get_mesh_shape(dst_shape)
    if not shape:
        raise RuntimeError("Not a mesh: {0}".format(dst_shape))

    cmds.undoInfo(openChunk=True, chunkName="adnApplyAndCopy")
    try:
        dst_node = cmds.deformer(shape, type=deformer_type, frontOfChain=True)[0]
        log.info("Created %s '%s' on '%s'.", deformer_type, dst_node, shape)

        copy_scalar_attrs(src_node, dst_node)
        copy_connections(src_node, dst_node)
        transferred = _transfer_weight_maps(src_node, dst_node, maps=maps)
    except Exception:
        cmds.undoInfo(closeChunk=True)
        raise

    cmds.undoInfo(closeChunk=True)

    log.info(
        "apply_and_copy done: %s -> %s (%s) | %d map(s): %s",
        src_node, dst_node, shape, len(transferred), transferred,
    )
    return dst_node, transferred


def copy_from_selection(maps=None, mirror_connections=True):
    """Transfer AdonisFX weights based on active selection (source, dest)."""
    sel = cmds.ls(selection=True, long=True)
    if len(sel) != 2:
        raise RuntimeError(
            "Select exactly 2 meshes (source first, then destination). "
            "Currently selected: {0}".format(sel)
        )

    src_transform, dst_transform = sel

    src_shape = _get_mesh_shape(src_transform)
    dst_shape = _get_mesh_shape(dst_transform)

    if not src_shape:
        raise RuntimeError("Source is not a mesh: {0}".format(src_transform))
    if not dst_shape:
        raise RuntimeError("Destination is not a mesh: {0}".format(dst_transform))

    src_node, src_type = _find_deformer(src_shape)
    if not src_node:
        raise RuntimeError(
            "No AdonisFX deformer found in source mesh history: {0}".format(src_shape)
        )

    dst_node, dst_type = _find_deformer(dst_shape)

    if not dst_node:
        log.info(
            "Destination '%s' has no AdonisFX deformer. "
            "Applying %s and copying from '%s'.",
            dst_shape, src_type, src_node,
        )
        return apply_and_copy(src_node, dst_shape, maps=maps)

    if src_type != dst_type:
        raise TypeError(
            "Deformer type mismatch: source has {0}, destination has {1}.".format(
                src_type, dst_type
            )
        )

    log.info(
        "copy_from_selection: %s (%s) -> %s (%s) | maps=%s | mirror_conns=%s",
        src_node, src_type, dst_node, dst_type, maps or "all", mirror_connections,
    )
    return copy_weights(src_node, dst_node, maps=maps,
                        mirror_connections=mirror_connections)


def copy_from_selection_multi(plan, mirror_connections=True):
    """
    Process multiple deformers in one undo chunk.

    *plan* is a list of dicts:
        {
          "src_node": "adnSkin1",
          "src_type": "AdnSkin",
          "dst_shape": "bodyShape",
          "maps":     ["weightMap", ...]  # None = all
        }
    """
    if not plan:
        raise RuntimeError("Empty plan - nothing to transfer.")

    summary = {"transferred": [], "created": [], "skipped": []}

    cmds.undoInfo(openChunk=True, chunkName="adnCopyMulti")
    try:
        for entry in plan:
            src_node  = entry["src_node"]
            src_type  = entry["src_type"]
            dst_shape = entry["dst_shape"]
            maps      = entry.get("maps")

            if not cmds.objExists(src_node):
                summary["skipped"].append((src_node, "source node no longer exists"))
                continue

            existing = [(n, t) for n, t in _find_all_deformers_in_history(dst_shape)
                        if t == src_type]

            if existing:
                dst_node = existing[0][0]
                try:
                    transferred = copy_weights(
                        src_node, dst_node, maps=maps,
                        mirror_connections=mirror_connections,
                    )
                    summary["transferred"].append((src_node, dst_node, transferred))
                except Exception as exc:
                    summary["skipped"].append(
                        (src_node, "copy_weights failed: {0}".format(exc))
                    )
                    log.exception("copy_weights failed for %s -> %s", src_node, dst_node)
            else:
                try:
                    dst_node, transferred = apply_and_copy(
                        src_node, dst_shape, maps=maps,
                    )
                    summary["created"].append((src_node, dst_node, transferred))
                except Exception as exc:
                    summary["skipped"].append(
                        (src_node, "apply_and_copy failed: {0}".format(exc))
                    )
                    log.exception("apply_and_copy failed for %s -> %s",
                                  src_node, dst_shape)
    finally:
        cmds.undoInfo(closeChunk=True)

    log.info(
        "copy_from_selection_multi done: transferred=%d, created=%d, skipped=%d.",
        len(summary["transferred"]), len(summary["created"]), len(summary["skipped"]),
    )
    return summary


# ---------------------------------------------------------------------------
# Public API - clipboard-style copy/paste with optional X-mirror
# ---------------------------------------------------------------------------

_weights_buffer = None


def _buffer_is_valid():
    if not _weights_buffer:
        return False
    return cmds.objExists(_weights_buffer.get("src_shape", ""))


def clear_buffer():
    global _weights_buffer
    _weights_buffer = None
    log.info("Weight buffer cleared.")


def copy_to_buffer(maps=None):
    """Copy all (or selected) weight maps into an in-memory buffer."""
    global _weights_buffer

    sel = cmds.ls(selection=True, long=True)
    if len(sel) != 1:
        raise RuntimeError(
            "Select exactly 1 mesh to copy from. Currently selected: {0}".format(sel)
        )

    shape = _get_mesh_shape(sel[0])
    if not shape:
        raise RuntimeError("Selection is not a mesh: {0}".format(sel[0]))

    deformer_node, deformer_type = _find_deformer(shape)
    if not deformer_node:
        raise RuntimeError(
            "No AdonisFX deformer found on '{0}'.".format(shape)
        )

    registry = _available_maps(deformer_node)
    maps_to_copy = list(registry.keys()) if maps is None else maps

    unknown = [m for m in maps_to_copy if m not in registry]
    if unknown:
        raise ValueError(
            "Unknown or unavailable map(s) for {0}: {1}. Available: {2}".format(
                deformer_type, unknown, sorted(registry.keys())
            )
        )

    vtx = _vertex_count(shape)
    snapshot = {}
    for map_name in maps_to_copy:
        list_attr, elem_attr = registry[map_name]
        snapshot[map_name] = _get_weights(deformer_node, list_attr, elem_attr, vtx)

    _weights_buffer = {
        "deformer_type": deformer_type,
        "src_node":      deformer_node,
        "src_shape":     shape,
        "src_vtx":       vtx,
        "maps":          snapshot,
    }

    log.info(
        "Copied %d map(s) from %s (%s, %d verts) into buffer.",
        len(snapshot), deformer_node, deformer_type, vtx,
    )
    return list(snapshot.keys())


def paste_from_buffer(maps=None, mirror_x=False):
    """
    Paste buffered weights onto the deformer on the currently selected mesh.

    *maps*     - subset of the buffered maps to paste (default: all buffered).
    *mirror_x* - sample the source at X-flipped positions (R<->L flip).
    """
    if not _weights_buffer:
        raise RuntimeError("Nothing in buffer. Copy weights first.")
    if not _buffer_is_valid():
        raise RuntimeError(
            "Buffer source mesh no longer exists: '{0}'. "
            "Re-copy from a valid mesh.".format(_weights_buffer.get("src_shape"))
        )

    sel = cmds.ls(selection=True, long=True)
    if len(sel) != 1:
        raise RuntimeError(
            "Select exactly 1 destination mesh to paste onto. "
            "Currently selected: {0}".format(sel)
        )

    dst_shape = _get_mesh_shape(sel[0])
    if not dst_shape:
        raise RuntimeError("Selection is not a mesh: {0}".format(sel[0]))

    dst_node, dst_type = _find_deformer(dst_shape)
    if not dst_node:
        raise RuntimeError(
            "Destination mesh '{0}' has no AdonisFX deformer.".format(dst_shape)
        )

    buf_type = _weights_buffer["deformer_type"]
    if dst_type != buf_type:
        raise TypeError(
            "Deformer type mismatch: buffer is {0}, destination is {1}.".format(
                buf_type, dst_type
            )
        )

    src_shape = _weights_buffer["src_shape"]
    src_vtx   = _weights_buffer["src_vtx"]
    dst_vtx   = _vertex_count(dst_shape)
    registry  = _available_maps(dst_node)
    buf_maps  = _weights_buffer["maps"]

    maps_to_paste = list(buf_maps.keys()) if maps is None else maps
    unknown = [m for m in maps_to_paste if m not in buf_maps]
    if unknown:
        raise ValueError(
            "Map(s) not in buffer: {0}. Buffered: {1}".format(
                unknown, sorted(buf_maps.keys())
            )
        )
    missing_on_dst = [m for m in maps_to_paste if m not in registry]
    if missing_on_dst:
        raise ValueError(
            "Map(s) not available on destination deformer: {0}".format(missing_on_dst)
        )

    if mirror_x:
        log.info(
            "Pasting with X-mirror: %s -> %s (%d -> %d verts).",
            src_shape, dst_shape, src_vtx, dst_vtx,
        )
        spatial_map = _build_spatial_map(src_shape, dst_shape, flip_x=True)
        same_topo = False
    else:
        same_topo = (src_vtx == dst_vtx)
        if not same_topo:
            log.info(
                "Vertex count mismatch (%d vs %d) - using spatial map.",
                src_vtx, dst_vtx,
            )
            spatial_map = _build_spatial_map(src_shape, dst_shape, flip_x=False)

    cmds.undoInfo(openChunk=True, chunkName="adnPasteWeights")
    try:
        pasted = []
        for map_name in maps_to_paste:
            list_attr, elem_attr = registry[map_name]
            src_weights = buf_maps[map_name]

            if same_topo:
                dst_weights = list(src_weights)
            else:
                dst_weights = []
                for tri_verts, bary in spatial_map:
                    w = sum(bary[k] * src_weights[tri_verts[k]] for k in range(3))
                    dst_weights.append(max(0.0, min(1.0, w)))

            _set_weights(dst_node, list_attr, elem_attr, dst_weights)
            pasted.append(map_name)
            log.debug("Pasted map '%s'.", map_name)
    finally:
        cmds.undoInfo(closeChunk=True)

    log.info(
        "Pasted %d map(s) onto %s (mirror_x=%s): %s",
        len(pasted), dst_node, mirror_x, pasted,
    )
    return pasted


# ---------------------------------------------------------------------------
# Public API - mirror L_ -> R_ for AdnRelax / AdnPush / AdnMush
# ---------------------------------------------------------------------------

_L_TOKEN_RE = re.compile(r'(?<![A-Za-z0-9])L_')

_SCALAR_COPY_BLACKLIST = {
    "caching", "frozen", "isHistoricallyInteresting", "nodeState",
    "binMembership", "message",
    "input", "outputGeometry", "originalGeometry",
    "weightList", "blendWeights",
}


def _swap_l_to_r(name):
    if not _L_TOKEN_RE.search(name):
        return None
    return _L_TOKEN_RE.sub("R_", name)


def _short_name(node):
    if not node:
        return ""
    return node.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def _is_copyable_scalar_attr(node, attr):
    if attr in _SCALAR_COPY_BLACKLIST:
        return False
    plug = "{0}.{1}".format(node, attr)
    try:
        if cmds.attributeQuery(attr, node=node, multi=True):
            return False
        children = cmds.attributeQuery(attr, node=node, listChildren=True)
        if children:
            return False
        if not cmds.getAttr(plug, settable=True):
            return False
        attr_type = cmds.getAttr(plug, type=True)
        if attr_type in (None, "message"):
            return False
    except Exception:
        return False
    return True


def _discover_scalar_attrs(node):
    all_attrs = cmds.listAttr(node, write=True, scalar=True) or []
    return [a for a in all_attrs if _is_copyable_scalar_attr(node, a)]


def _copy_scalars_freeform(src_node, dst_node):
    attrs = _discover_scalar_attrs(src_node)
    copied = []
    skipped = []

    for attr in attrs:
        if not cmds.attributeQuery(attr, node=dst_node, exists=True):
            continue
        dst_plug = "{0}.{1}".format(dst_node, attr)
        if cmds.listConnections(dst_plug, source=True, destination=False):
            skipped.append(attr)
            continue
        try:
            value = cmds.getAttr("{0}.{1}".format(src_node, attr))
            cmds.setAttr(dst_plug, value)
            copied.append(attr)
        except Exception as exc:
            log.debug("Could not copy attr '%s': %s", attr, exc)

    log.debug("Freeform scalar copy %s -> %s : %d copied, %d skipped (connected).",
              src_node, dst_node, len(copied), len(skipped))
    return copied


def _gather_meshes_under(node):
    if not cmds.objExists(node):
        return []
    node_type = cmds.nodeType(node)
    if node_type == "mesh":
        return [node]
    shapes = cmds.listRelatives(
        node, allDescendents=True, shapes=True, type="mesh", fullPath=True
    ) or []
    shapes = [s for s in shapes if not cmds.getAttr(s + ".intermediateObject")]
    return shapes


def _find_all_deformers(mesh_shape, types):
    found = []
    seen = set()
    for node in (cmds.listHistory(mesh_shape, pruneDagObjects=True) or []):
        ntype = cmds.nodeType(node)
        if ntype in types and node not in seen:
            seen.add(node)
            found.append((node, ntype))
    return found


def scan_mirror_candidates(roots=None, types=_MIRROR_LR_TYPES):
    """
    Walk *roots* and return candidate deformers to mirror L -> R.
    Each entry: {"src_node", "src_type", "src_mesh", "dst_node", "dst_exists"}
    """
    if roots is None:
        roots = cmds.ls(selection=True, long=True) or []
    if not roots:
        raise RuntimeError("Nothing selected. Pick a transform/group or a mesh.")

    candidates = []
    seen_nodes = set()
    for root in roots:
        meshes = _gather_meshes_under(root)
        for mesh in meshes:
            for node, ntype in _find_all_deformers(mesh, types):
                if node in seen_nodes:
                    continue
                seen_nodes.add(node)

                short = _short_name(node)
                mirrored = _swap_l_to_r(short)
                if mirrored is None:
                    log.debug("Skipping '%s' - no L_ token in name.", node)
                    continue

                candidates.append({
                    "src_node":   node,
                    "src_type":   ntype,
                    "src_mesh":   mesh,
                    "dst_node":   mirrored,
                    "dst_exists": cmds.objExists(mirrored),
                })

    return candidates


def mirror_l_to_r(roots=None, types=_MIRROR_LR_TYPES, create_missing=True):
    """
    For each Adn(Relax|Push|Mush) deformer under *roots* whose name has a
    whole-word 'L_' token: find or create the matching 'R_' deformer and
    copy all scalar attributes. Weights are NOT touched.
    """
    candidates = scan_mirror_candidates(roots=roots, types=types)
    if not candidates:
        log.info("Mirror L->R: no L_ deformers of types %s found under selection.", types)
        return {"created": [], "updated": [], "skipped": []}

    summary = {"created": [], "updated": [], "skipped": []}

    cmds.undoInfo(openChunk=True, chunkName="adnMirrorLtoR")
    try:
        for c in candidates:
            src_node = c["src_node"]
            src_type = c["src_type"]
            dst_name = c["dst_node"]

            src_mesh_transform = cmds.listRelatives(c["src_mesh"], parent=True,
                                                    fullPath=True)
            src_mesh_transform = src_mesh_transform[0] if src_mesh_transform else None

            if c["dst_exists"]:
                dst_type = cmds.nodeType(dst_name)
                if dst_type != src_type:
                    msg = "name collision: '{0}' exists but is {1}, not {2}".format(
                        dst_name, dst_type, src_type
                    )
                    summary["skipped"].append((src_node, msg))
                    log.warning("Skip %s: %s", src_node, msg)
                    continue
                dst_node = dst_name
                _copy_scalars_freeform(src_node, dst_node)
                summary["updated"].append((src_node, dst_node))
                log.info("Updated scalars: %s -> %s", src_node, dst_node)
                continue

            if not create_missing:
                summary["skipped"].append(
                    (src_node, "R_ deformer missing and create_missing=False")
                )
                continue

            r_mesh_transform = None
            if src_mesh_transform:
                r_mesh_transform = _swap_l_to_r(_short_name(src_mesh_transform))
            if not r_mesh_transform or not cmds.objExists(r_mesh_transform):
                msg = "no R_ mesh found (expected '{0}')".format(r_mesh_transform)
                summary["skipped"].append((src_node, msg))
                log.warning("Skip %s: %s", src_node, msg)
                continue

            r_shape = _get_mesh_shape(r_mesh_transform)
            if not r_shape:
                msg = "R_ object '{0}' has no mesh shape".format(r_mesh_transform)
                summary["skipped"].append((src_node, msg))
                log.warning("Skip %s: %s", src_node, msg)
                continue

            try:
                created = cmds.deformer(r_shape, type=src_type,
                                         name=dst_name, frontOfChain=True)
                dst_node = created[0]
            except Exception as exc:
                msg = "could not create {0} on '{1}': {2}".format(
                    src_type, r_shape, exc
                )
                summary["skipped"].append((src_node, msg))
                log.warning("Skip %s: %s", src_node, msg)
                continue

            _copy_scalars_freeform(src_node, dst_node)
            summary["created"].append((src_node, dst_node))
            log.info("Created %s '%s' on '%s' and copied scalars.",
                     src_type, dst_node, r_shape)

    finally:
        cmds.undoInfo(closeChunk=True)

    log.info(
        "Mirror L->R done: created=%d, updated=%d, skipped=%d.",
        len(summary["created"]), len(summary["updated"]), len(summary["skipped"]),
    )
    return summary


# ---------------------------------------------------------------------------
# Deformer graph capture / restore  (used by Replace Mesh)
# ---------------------------------------------------------------------------

_NON_AUX_NODE_TYPES = frozenset({
    "mesh", "nurbsCurve", "nurbsSurface", "lattice", "bezierCurve",
    "joint", "transform", "ikHandle", "ikEffector", "locator",
    "camera", "light", "ambientLight", "directionalLight", "pointLight",
    "spotLight", "areaLight", "volumeLight",
    "skinCluster", "dagPose", "tweak",
    "objectSet", "groupId", "groupParts",
    "shadingEngine", "renderPartition", "partition",
    "time", "expression",
})


def _iter_incoming_plugs(node):
    """Yield (src_plug, dst_attr) for every incoming connection on node."""
    raw = cmds.listConnections(
        node, connections=True, source=True, destination=False, plugs=True
    ) or []
    for i in range(0, len(raw), 2):
        yield raw[i + 1], raw[i].split(".", 1)[1]


def _iter_outgoing_plugs(node):
    """Yield (src_attr, dst_plug) for every outgoing connection from node."""
    raw = cmds.listConnections(
        node, connections=True, source=False, destination=True, plugs=True
    ) or []
    for i in range(0, len(raw), 2):
        yield raw[i].split(".", 1)[1], raw[i + 1]


def _node_is_capturable_aux(node):
    """Return True for utility/helper nodes (andNodes, conditions, etc.) that
    should be captured alongside the deformer they feed into."""
    if not cmds.objExists(node):
        return False
    ntype = cmds.nodeType(node)
    if ntype in _NON_AUX_NODE_TYPES:
        return False
    if ntype.startswith("animCurve"):
        return False
    if ntype in _DEFORMER_MAPS:
        return False
    return True


def _capture_deformer_full_state(adn_node):
    """
    Snapshot an AdonisFX deformer and its auxiliary input graph.

    Returns a dict with:
      node, node_type, vtx_count, weight_maps, scalar_attrs,
      incoming [(src_plug, dst_attr), ...],
      outgoing [(src_attr, dst_plug), ...],
      aux_nodes {name: {type, incoming, outgoing}}
    """
    node_type = cmds.nodeType(adn_node)

    registry  = _available_maps(adn_node)
    geo       = cmds.deformer(adn_node, q=True, geometry=True) or []
    vtx_count = _vertex_count(geo[0]) if geo else 0

    weight_maps = {}
    for map_name, (list_attr, elem_attr) in registry.items():
        try:
            weight_maps[map_name] = _get_weights(adn_node, list_attr, elem_attr, vtx_count)
        except Exception as exc:
            log.warning("Capture: map '%s' on %s: %s", map_name, adn_node, exc)

    scalar_attrs = {}
    for attr in _DEFORMER_SCALAR_ATTRS.get(node_type, []):
        if not cmds.attributeQuery(attr, node=adn_node, exists=True):
            continue
        try:
            if attr == _GRAVITY_DIRECTION_ATTR:
                scalar_attrs[attr] = list(cmds.getAttr("{0}.{1}".format(adn_node, attr))[0])
            else:
                scalar_attrs[attr] = cmds.getAttr("{0}.{1}".format(adn_node, attr))
        except Exception:
            pass

    incoming = list(_iter_incoming_plugs(adn_node))
    outgoing = list(_iter_outgoing_plugs(adn_node))

    aux_nodes = {}
    for src_plug, _ in incoming:
        src_node = src_plug.split(".")[0]
        if src_node == adn_node or src_node in aux_nodes:
            continue
        if not _node_is_capturable_aux(src_node):
            continue
        aux_nodes[src_node] = {
            "type":     cmds.nodeType(src_node),
            "incoming": list(_iter_incoming_plugs(src_node)),
            "outgoing": list(_iter_outgoing_plugs(src_node)),
        }

    return {
        "node":         adn_node,
        "node_type":    node_type,
        "vtx_count":    vtx_count,
        "weight_maps":  weight_maps,
        "scalar_attrs": scalar_attrs,
        "incoming":     incoming,
        "outgoing":     outgoing,
        "aux_nodes":    aux_nodes,
    }


def _remap_plug(plug, remap):
    """Replace the node portion of *plug* using *remap*, or return unchanged."""
    node, sep, attr = plug.partition(".")
    return remap.get(node, node) + sep + attr if sep else remap.get(node, node)


def _restore_deformer_maps(new_node, state, old_shape, new_shape):
    """Write captured weight maps onto *new_node*, resampling for topology change."""
    registry  = _available_maps(new_node)
    geo       = cmds.deformer(new_node, q=True, geometry=True) or []
    dst_vtx   = _vertex_count(geo[0]) if geo else 0
    src_vtx   = state["vtx_count"]
    same_topo = (src_vtx == dst_vtx)

    spatial_map = None
    if not same_topo and src_vtx > 0 and dst_vtx > 0:
        log.info("Vertex count mismatch (%d vs %d) - building spatial map.", src_vtx, dst_vtx)
        spatial_map = _build_spatial_map(old_shape, new_shape)

    for map_name, src_weights in state["weight_maps"].items():
        if map_name not in registry:
            log.debug("Map '%s' not on %s, skipping.", map_name, new_node)
            continue
        list_attr, elem_attr = registry[map_name]

        if same_topo:
            dst_weights = list(src_weights)
        elif spatial_map:
            dst_weights = []
            for tri_verts, bary in spatial_map:
                w = sum(bary[k] * src_weights[tri_verts[k]] for k in range(3))
                dst_weights.append(max(0.0, min(1.0, w)))
        else:
            continue

        _set_weights(new_node, list_attr, elem_attr, dst_weights)
        log.debug("Restored map '%s' on %s.", map_name, new_node)


def _restore_deformer_connections(new_node, state, remap):
    """Reconnect captured incoming connections to *new_node* with *remap* applied."""
    for src_plug, dst_attr in state["incoming"]:
        remapped_src = _remap_plug(src_plug, remap)

        root_attr = dst_attr.split(".")[0].split("[")[0]
        if root_attr in _NEVER_MIRROR_ATTRS:
            continue
        if not cmds.attributeQuery(root_attr, node=new_node, exists=True):
            log.debug("Attr '%s' missing on %s, skipping.", dst_attr, new_node)
            continue
        if not cmds.objExists(remapped_src):
            log.warning("Restore: source plug '%s' not found.", remapped_src)
            continue

        dst_plug = "{0}.{1}".format(new_node, dst_attr)
        if cmds.listConnections(dst_plug, source=True, destination=False, plugs=True):
            continue

        try:
            cmds.connectAttr(remapped_src, dst_plug, force=True)
            log.debug("Restored: %s -> %s", remapped_src, dst_plug)
        except Exception as exc:
            log.warning("Restore conn failed %s -> %s: %s", remapped_src, dst_plug, exc)


def _restore_aux_node_connections(all_aux_nodes, remap):
    """
    Rewire aux nodes (andNodes, condition nodes, etc.) whose connections
    pointed to old deformer/mesh nodes, updating them to the remapped replacements.
    Called after all new deformers have been created and added to remap.
    """
    for aux_node, state in all_aux_nodes.items():
        if not cmds.objExists(aux_node):
            log.warning("Aux node '%s' no longer exists, skipping.", aux_node)
            continue

        # Outgoing: rewire destinations that map to new nodes
        for src_attr, dst_plug in state["outgoing"]:
            dst_node = dst_plug.split(".")[0]
            if dst_node not in remap:
                continue
            new_dst_plug = _remap_plug(dst_plug, remap)
            old_src_plug  = "{0}.{1}".format(aux_node, src_attr)

            if not cmds.objExists(new_dst_plug):
                continue
            if cmds.listConnections(new_dst_plug, source=True, destination=False):
                continue
            try:
                cmds.connectAttr(old_src_plug, new_dst_plug, force=True)
                log.debug("Aux rewired out: %s -> %s", old_src_plug, new_dst_plug)
            except Exception as exc:
                log.warning("Aux out rewire failed %s -> %s: %s", old_src_plug, new_dst_plug, exc)

        # Incoming: rewire sources that map to new nodes
        for src_plug, dst_attr in state["incoming"]:
            src_node = src_plug.split(".")[0]
            if src_node not in remap:
                continue
            new_src_plug  = _remap_plug(src_plug, remap)
            dst_plug_full = "{0}.{1}".format(aux_node, dst_attr)

            if not cmds.objExists(new_src_plug):
                continue
            current = cmds.listConnections(
                dst_plug_full, source=True, destination=False, plugs=True
            ) or []
            if current and current[0] == src_plug:
                try:
                    cmds.disconnectAttr(src_plug, dst_plug_full)
                    cmds.connectAttr(new_src_plug, dst_plug_full, force=True)
                    log.debug("Aux rewired in: %s -> %s", new_src_plug, dst_plug_full)
                except Exception as exc:
                    log.warning("Aux in rewire failed %s -> %s: %s", new_src_plug, dst_plug_full, exc)


def _update_mesh_downstream_consumers(old_shape, old_transform, new_shape, new_transform, remap):
    """
    Find nodes that use old_shape / old_transform as inputs and redirect them
    to new_shape / new_transform.

    This is the critical step for the fat->skin dependency: if we replaced the
    fat mesh, any AdnSkin using old fat as a target must now point to new fat.
    """
    for old_node, new_node in ((old_shape, new_shape), (old_transform, new_transform)):
        if not old_node or not cmds.objExists(old_node):
            continue
        raw = cmds.listConnections(
            old_node, connections=True, source=False, destination=True, plugs=True
        ) or []
        for i in range(0, len(raw), 2):
            src_plug = raw[i]
            dst_plug = raw[i + 1]
            src_attr = src_plug.split(".", 1)[1]
            dst_node = dst_plug.split(".")[0]

            if dst_node in remap.values():
                continue
            if dst_node == new_node:
                continue

            new_src_plug = "{0}.{1}".format(new_node, src_attr)
            if not cmds.objExists(new_src_plug):
                log.debug("No matching attr on new node: %s", new_src_plug)
                continue
            try:
                cmds.disconnectAttr(src_plug, dst_plug)
                cmds.connectAttr(new_src_plug, dst_plug, force=True)
                log.info("Downstream updated: %s -> %s (was %s)", new_src_plug, dst_plug, src_plug)
            except Exception as exc:
                log.warning("Downstream update failed %s -> %s: %s", new_src_plug, dst_plug, exc)


# ---------------------------------------------------------------------------
# Public API - Replace Mesh in Rig Setup
# ---------------------------------------------------------------------------

def _get_skin_cluster(mesh_shape):
    """Return the skinCluster node on *mesh_shape*, or None."""
    for node in (cmds.listHistory(mesh_shape, pruneDagObjects=True) or []):
        if cmds.nodeType(node) == "skinCluster":
            return node
    return None


def _transfer_skin_cluster(old_shape, new_shape):
    """
    Copy skinCluster weights from *old_shape* to *new_shape*.

    Creates a new skinCluster on *new_shape* with the same joints and
    skinning method, then copies weights using closestPoint surface
    association (handles different topology automatically).

    Returns the new skinCluster node name, or None if old had none.
    """
    old_cluster = _get_skin_cluster(old_shape)
    if not old_cluster:
        log.info("No skinCluster on '%s' - skipping skin transfer.", old_shape)
        return None

    # Check destination is clean
    existing = _get_skin_cluster(new_shape)
    if existing:
        log.warning(
            "New mesh '%s' already has skinCluster '%s'. "
            "Delete it first for a clean transfer.",
            new_shape, existing,
        )

    influences = cmds.skinCluster(old_cluster, query=True, influence=True) or []
    if not influences:
        log.warning("skinCluster '%s' has no influences.", old_cluster)
        return None

    method  = cmds.getAttr("{0}.skinningMethod".format(old_cluster))
    max_inf = cmds.getAttr("{0}.maxInfluences".format(old_cluster))

    new_cluster = cmds.skinCluster(
        influences + [new_shape],
        toSelectedBones=True,
        skinMethod=method,
        maximumInfluences=max_inf,
        normalizeWeights=1,
    )[0]

    cmds.copySkinWeights(
        sourceSkin=old_cluster,
        destinationSkin=new_cluster,
        noMirror=True,
        surfaceAssociation="closestPoint",
        influenceAssociation=["label", "oneToOne", "closestJoint"],
    )

    log.info(
        "Skin transferred: %s -> %s (%d joints, method=%d).",
        old_cluster, new_cluster, len(influences), method,
    )
    return new_cluster


def replace_mesh_in_setup(old_transform, new_transform,
                           transfer_skin=True,
                           transfer_adonis=True,
                           reparent=True,
                           rename=True,
                           delete_old=False):
    """
    Replace *old_transform* with *new_transform* in the rig setup.

    Steps (each independently toggled):
      1. transfer_skin   - copy skinCluster weights; closestPoint handles
                           different vertex counts automatically.
      2. transfer_adonis - full capture/restore of all AdonisFX deformers:
                           weight maps, scalar attrs, all connections, and
                           auxiliary nodes (andNodes, condition nodes…).
                           Also updates downstream consumers of the old mesh
                           (e.g. an AdnSkin that used the old fat as a target).
      3. reparent        - parent new mesh under old mesh's parent transform.
      4. rename          - new nodes take old names; old nodes get '__ORIG' suffix.
      5. delete_old      - delete old mesh (False = only hide it).

    The operation is wrapped in a single undo chunk.
    Returns the final node name of the replacement mesh.
    """
    old_shape = _get_mesh_shape(old_transform)
    new_shape = _get_mesh_shape(new_transform)

    if not old_shape:
        raise RuntimeError("Old transform has no mesh shape: {0}".format(old_transform))
    if not new_shape:
        raise RuntimeError("New transform has no mesh shape: {0}".format(new_transform))

    old_t_short = _short_name(old_transform)
    old_s_short = _short_name(old_shape)

    cmds.undoInfo(openChunk=True, chunkName="adnReplaceMesh")
    try:
        # ── 1. Capture full Adonis state BEFORE any changes ──────────────────
        # Must happen first so we snapshot connections against the original graph.
        captured    = {}   # {old_node: state_dict}
        all_aux     = {}   # merged aux nodes across all deformers
        deformer_order = []  # in listHistory order (most downstream first)

        if transfer_adonis:
            for node, ntype in _find_all_deformers_in_history(old_shape):
                state = _capture_deformer_full_state(node)
                captured[node] = state
                all_aux.update(state["aux_nodes"])
                deformer_order.append(node)

        # ── 2. skinCluster transfer ──────────────────────────────────────────
        if transfer_skin:
            _transfer_skin_cluster(old_shape, new_shape)

        # ── 3. AdonisFX capture → restore ────────────────────────────────────
        remap = {old_shape: new_shape, old_transform: new_transform}

        if transfer_adonis and captured:
            # Create deformers bottom-up (oldest in history = deepest in stack)
            # so that successive frontOfChain=True inserts reproduce the same order.
            for old_node in reversed(deformer_order):
                state     = captured[old_node]
                node_type = state["node_type"]

                new_node = cmds.deformer(new_shape, type=node_type, frontOfChain=True)[0]
                remap[old_node] = new_node
                log.info("Created %s '%s' on '%s'.", node_type, new_node, new_shape)

                # Scalar attrs
                for attr, val in state["scalar_attrs"].items():
                    if not cmds.attributeQuery(attr, node=new_node, exists=True):
                        continue
                    try:
                        if attr == _GRAVITY_DIRECTION_ATTR:
                            cmds.setAttr("{0}.{1}".format(new_node, attr),
                                         val[0], val[1], val[2], type="double3")
                        else:
                            cmds.setAttr("{0}.{1}".format(new_node, attr), val)
                    except Exception as exc:
                        log.debug("Could not restore attr '%s': %s", attr, exc)

                # Weight maps (resampled if topology differs)
                _restore_deformer_maps(new_node, state, old_shape, new_shape)

                # Incoming connections with remap applied
                _restore_deformer_connections(new_node, state, remap)

            # Rewire aux nodes (andNodes etc.) now that remap is complete
            _restore_aux_node_connections(all_aux, remap)

            # Update nodes downstream of the old mesh that depended on it
            # (e.g. AdnSkin using old fat mesh as a target)
            _update_mesh_downstream_consumers(
                old_shape, old_transform, new_shape, new_transform, remap
            )

        elif transfer_adonis:
            log.info("No AdonisFX deformers found on '%s'.", old_shape)

        # ── 4. Re-parent ─────────────────────────────────────────────────────
        if reparent:
            old_parents = cmds.listRelatives(old_transform, parent=True, fullPath=True) or []
            if old_parents:
                cmds.parent(new_transform, old_parents[0])
            else:
                cmds.parent(new_transform, world=True)

        # Re-resolve new_transform path after parenting (DAG path changes)
        new_t_short = _short_name(new_transform)
        resolved = cmds.ls(new_t_short, long=True)
        if resolved:
            new_transform = resolved[0]

        # ── 5. Rename ────────────────────────────────────────────────────────
        current_old_transform = old_transform
        if rename:
            current_old_transform = cmds.rename(old_transform, old_t_short + "__ORIG")
            old_shapes_now = cmds.listRelatives(current_old_transform, shapes=True) or []
            if old_shapes_now:
                cmds.rename(old_shapes_now[0], old_s_short + "__ORIG")

            new_shapes_now = cmds.listRelatives(new_transform, shapes=True) or []
            if new_shapes_now:
                cmds.rename(new_shapes_now[0], old_s_short)
            new_transform = cmds.rename(new_transform, old_t_short)

        # ── 6. Hide / delete old ─────────────────────────────────────────────
        if delete_old:
            cmds.delete(current_old_transform)
            log.info("Deleted old mesh '%s'.", old_t_short + ("__ORIG" if rename else ""))
        else:
            try:
                cmds.setAttr("{0}.visibility".format(current_old_transform), 0)
            except Exception:
                pass

    finally:
        cmds.undoInfo(closeChunk=True)

    log.info("replace_mesh_in_setup done: '%s' replaced by '%s'.",
             old_t_short, new_transform)
    return new_transform


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

WINDOW_NAME = "adnCopyWeightsWin"

_ui_state = {
    # Transfer tab
    "src_field":         None,
    "dst_field":         None,
    "info_field":        None,
    "map_layout":        None,
    "mirror_conns_cb":   None,
    "deformer_sections": [],
    "dst_shape":         None,

    # Copy/Paste tab
    "cp_checkboxes":   {},
    "cp_buffer_field": None,
    "cp_target_field": None,
    "cp_info_field":   None,
    "cp_map_layout":   None,
    "cp_mirror_cb":    None,

    # Mirror L->R tab
    "mr_type_checkboxes": {},
    "mr_create_cb":       None,
    "mr_preview_scroll":  None,
    "mr_preview_layout":  None,
    "mr_info_field":      None,
    "mr_candidates":      [],

    # Replace Mesh tab
    "rp_old_field":     None,
    "rp_new_field":     None,
    "rp_skin_cb":       None,
    "rp_adonis_cb":     None,
    "rp_reparent_cb":   None,
    "rp_rename_cb":     None,
    "rp_delete_cb":     None,
    "rp_info_field":    None,
    "rp_old_transform": None,
    "rp_new_transform": None,
}


def _ui_short(name):
    if not name:
        return ""
    return name.rsplit("|", 1)[-1]


def _ui_set_info(message, warn=False):
    color = [0.9, 0.5, 0.4] if warn else [0.6, 0.85, 0.6]
    cmds.text(_ui_state["info_field"], edit=True, label=message, backgroundColor=color)


def _cp_set_info(message, warn=False):
    color = [0.9, 0.5, 0.4] if warn else [0.6, 0.85, 0.6]
    cmds.text(_ui_state["cp_info_field"], edit=True, label=message, backgroundColor=color)


def _rp_set_info(message, warn=False):
    color = [0.9, 0.5, 0.4] if warn else [0.6, 0.85, 0.6]
    cmds.text(_ui_state["rp_info_field"], edit=True, label=message, backgroundColor=color)


# --- Transfer tab callbacks ------------------------------------------------

def _ui_clear_sections():
    layout = _ui_state["map_layout"]
    children = cmds.columnLayout(layout, query=True, childArray=True) or []
    for c in children:
        cmds.deleteUI(c)
    _ui_state["deformer_sections"] = []


def _ui_build_sections_placeholder(message):
    _ui_clear_sections()
    cmds.text(label="  " + message, parent=_ui_state["map_layout"], align="left")


def _ui_build_deformer_sections(src_deformers, dst_deformer_types):
    _ui_clear_sections()
    layout = _ui_state["map_layout"]

    for src_node, src_type in src_deformers:
        will_create = src_type not in dst_deformer_types
        action_tag = "will create" if will_create else "exists, will update"

        frame = cmds.frameLayout(
            label="{0}  ({1})  -  {2}".format(_ui_short(src_node), src_type, action_tag),
            collapsable=True, collapse=False,
            marginWidth=4, marginHeight=4,
            parent=layout,
        )
        body = cmds.columnLayout(adjustableColumn=True, rowSpacing=2, parent=frame)

        header_cb = cmds.checkBox(
            label="Process this deformer", value=True, parent=body,
        )

        maps_dict = _DEFORMER_MAPS.get(src_type, {})
        map_cbs = {}

        if maps_dict:
            cmds.separator(height=4, style="none", parent=body)
            cmds.text(label="Maps:", align="left", parent=body)

            grid = cmds.rowLayout(numberOfColumns=2, columnWidth2=(190, 190),
                                   adjustableColumn=2, parent=body)
            col_a = cmds.columnLayout(adjustableColumn=True, parent=grid)
            col_b = cmds.columnLayout(adjustableColumn=True, parent=grid)

            for i, map_name in enumerate(sorted(maps_dict.keys())):
                parent = col_a if i % 2 == 0 else col_b
                cb = cmds.checkBox(label=map_name, value=True, parent=parent)
                map_cbs[map_name] = cb
        else:
            cmds.text(
                label="  (no weight maps - only scalar/connection transfer)",
                align="left", parent=body,
            )

        _ui_state["deformer_sections"].append({
            "src_node":  src_node,
            "src_type":  src_type,
            "header_cb": header_cb,
            "map_cbs":   map_cbs,
        })


def _ui_refresh_from_selection(*_):
    sel = cmds.ls(selection=True, long=True)
    _ui_state["dst_shape"] = None

    if len(sel) == 0:
        _ui_set_info("Nothing selected. Pick source mesh, then dest mesh.", warn=True)
        cmds.textField(_ui_state["src_field"], edit=True, text="")
        cmds.textField(_ui_state["dst_field"], edit=True, text="")
        _ui_build_sections_placeholder("(select meshes to see available deformers)")
        return

    if len(sel) == 1:
        src_shape = _get_mesh_shape(sel[0])
        cmds.textField(_ui_state["src_field"], edit=True, text=_ui_short(sel[0]))
        cmds.textField(_ui_state["dst_field"], edit=True, text="(select destination)")
        if not src_shape:
            _ui_set_info("Source is not a mesh.", warn=True)
            _ui_build_sections_placeholder("(source has no mesh shape)")
            return
        src_deformers = _find_all_deformers_in_history(src_shape)
        if not src_deformers:
            _ui_set_info("Source has no AdonisFX deformer in its history.", warn=True)
            _ui_build_sections_placeholder("(no Adn deformers on source)")
            return
        _ui_set_info(
            "Source: {0} deformer(s) found. Shift-select destination to continue.".format(
                len(src_deformers)
            )
        )
        _ui_build_deformer_sections(src_deformers, dst_deformer_types=set())
        return

    if len(sel) > 2:
        _ui_set_info("Select exactly 2 meshes (got {0}).".format(len(sel)), warn=True)
        cmds.textField(_ui_state["src_field"], edit=True, text=_ui_short(sel[0]))
        cmds.textField(_ui_state["dst_field"], edit=True, text=_ui_short(sel[1]) + "  (+ extras)")
        return

    src, dst = sel
    src_shape = _get_mesh_shape(src)
    dst_shape = _get_mesh_shape(dst)
    cmds.textField(_ui_state["src_field"], edit=True, text=_ui_short(src))
    cmds.textField(_ui_state["dst_field"], edit=True, text=_ui_short(dst))

    if not src_shape:
        _ui_set_info("Source is not a mesh.", warn=True)
        _ui_build_sections_placeholder("(source is not a mesh)")
        return
    if not dst_shape:
        _ui_set_info("Destination is not a mesh.", warn=True)
        _ui_build_sections_placeholder("(destination is not a mesh)")
        return

    src_deformers = _find_all_deformers_in_history(src_shape)
    if not src_deformers:
        _ui_set_info("No AdonisFX deformer found on source.", warn=True)
        _ui_build_sections_placeholder("(no Adn deformers on source)")
        return

    dst_deformers = _find_all_deformers_in_history(dst_shape)
    dst_types = {t for _, t in dst_deformers}

    _ui_state["dst_shape"] = dst_shape

    n_create = sum(1 for _, t in src_deformers if t not in dst_types)
    n_update = len(src_deformers) - n_create
    msg = "Ready: {0} deformer(s) - {1} to update, {2} to create.".format(
        len(src_deformers), n_update, n_create
    )
    _ui_set_info(msg)
    _ui_build_deformer_sections(src_deformers, dst_types)


def _ui_toggle_all(value):
    for section in _ui_state["deformer_sections"]:
        cmds.checkBox(section["header_cb"], edit=True, value=value)
        for cb in section["map_cbs"].values():
            cmds.checkBox(cb, edit=True, value=value)


def _ui_build_transfer_plan():
    dst_shape = _ui_state.get("dst_shape")
    if not dst_shape:
        return None

    plan = []
    for section in _ui_state["deformer_sections"]:
        if not cmds.checkBox(section["header_cb"], query=True, value=True):
            continue

        src_type = section["src_type"]
        all_maps = sorted(_DEFORMER_MAPS.get(src_type, {}).keys())

        if section["map_cbs"]:
            selected = [m for m, cb in section["map_cbs"].items()
                        if cmds.checkBox(cb, query=True, value=True)]
            if not selected:
                continue
            maps_arg = None if set(selected) == set(all_maps) else selected
        else:
            maps_arg = None

        plan.append({
            "src_node":  section["src_node"],
            "src_type":  src_type,
            "dst_shape": dst_shape,
            "maps":      maps_arg,
        })

    return plan


def _ui_execute(*_):
    if not _ui_state["deformer_sections"]:
        cmds.warning("No deformers detected. Refresh selection first.")
        return
    if not _ui_state.get("dst_shape"):
        cmds.warning("Select source AND destination mesh before running.")
        return

    plan = _ui_build_transfer_plan()
    if not plan:
        cmds.warning("Nothing to do - no deformer/maps selected.")
        return

    mirror_conns = cmds.checkBox(_ui_state["mirror_conns_cb"], query=True, value=True)

    try:
        summary = copy_from_selection_multi(plan, mirror_connections=mirror_conns)
    except Exception as exc:
        cmds.confirmDialog(title="AdonisFX Copy - Error",
                           message=str(exc), button=["OK"], icon="critical")
        log.exception("copy_from_selection_multi failed")
        return

    n_xfer = len(summary["transferred"])
    n_new  = len(summary["created"])
    n_skip = len(summary["skipped"])

    parts = []
    if n_xfer:
        parts.append("{0} updated".format(n_xfer))
    if n_new:
        parts.append("{0} created".format(n_new))
    if n_skip:
        parts.append("{0} skipped".format(n_skip))
    msg = "Done: " + (", ".join(parts) if parts else "nothing to do") + "."

    _ui_set_info(msg, warn=(n_skip > 0 and not (n_xfer or n_new)))
    cmds.inViewMessage(
        amg='<hl>AdonisFX:</hl> ' + msg,
        pos='midCenter', fade=True, fadeStayTime=2500,
    )

    if n_skip:
        for src, reason in summary["skipped"]:
            log.warning("Skipped %s: %s", src, reason)

    _ui_refresh_from_selection()


# --- Copy/Paste tab callbacks ----------------------------------------------

def _cp_refresh_buffer_field():
    if _weights_buffer and _buffer_is_valid():
        text = "{0}  ({1}, {2} verts, {3} map(s))".format(
            _ui_short(_weights_buffer["src_node"]),
            _weights_buffer["deformer_type"],
            _weights_buffer["src_vtx"],
            len(_weights_buffer["maps"]),
        )
        cmds.textField(_ui_state["cp_buffer_field"], edit=True, text=text)
    else:
        cmds.textField(_ui_state["cp_buffer_field"], edit=True, text="(empty)")


def _cp_build_map_checkboxes(map_names):
    layout = _ui_state["cp_map_layout"]
    children = cmds.columnLayout(layout, query=True, childArray=True) or []
    for c in children:
        cmds.deleteUI(c)
    _ui_state["cp_checkboxes"] = {}

    if not map_names:
        cmds.text(label="  (copy from a mesh to see its maps)",
                  parent=layout, align="left")
        return

    grid = cmds.rowLayout(numberOfColumns=2, columnWidth2=(190, 190),
                          adjustableColumn=2, parent=layout)
    col_a = cmds.columnLayout(adjustableColumn=True, parent=grid)
    col_b = cmds.columnLayout(adjustableColumn=True, parent=grid)

    for i, map_name in enumerate(sorted(map_names)):
        parent = col_a if i % 2 == 0 else col_b
        cb = cmds.checkBox(label=map_name, value=True, parent=parent)
        _ui_state["cp_checkboxes"][map_name] = cb


def _cp_refresh_target_field(*_):
    sel = cmds.ls(selection=True, long=True)
    if len(sel) != 1:
        cmds.textField(_ui_state["cp_target_field"], edit=True,
                       text="(select 1 destination mesh)")
        return

    cmds.textField(_ui_state["cp_target_field"], edit=True, text=_ui_short(sel[0]))

    dst_shape = _get_mesh_shape(sel[0])
    if not dst_shape:
        _cp_set_info("Selection is not a mesh.", warn=True)
        return

    dst_node, dst_type = _find_deformer(dst_shape)
    if not dst_node:
        _cp_set_info("Destination has no AdonisFX deformer.", warn=True)
        return

    if _weights_buffer and dst_type != _weights_buffer["deformer_type"]:
        _cp_set_info(
            "Type mismatch: buffer is {0}, destination is {1}.".format(
                _weights_buffer["deformer_type"], dst_type
            ),
            warn=True,
        )
        return

    if _weights_buffer:
        _cp_set_info("Ready to paste onto {0}.".format(dst_node))
    else:
        _cp_set_info("Buffer is empty. Copy from a mesh first.", warn=True)


def _cp_toggle_all(value):
    for cb in _ui_state["cp_checkboxes"].values():
        cmds.checkBox(cb, edit=True, value=value)


def _cp_get_selected_maps():
    return [m for m, cb in _ui_state["cp_checkboxes"].items()
            if cmds.checkBox(cb, query=True, value=True)]


def _cp_do_copy(*_):
    try:
        copied = copy_to_buffer()
    except Exception as exc:
        cmds.confirmDialog(title="AdonisFX Copy/Paste - Error",
                           message=str(exc), button=["OK"], icon="critical")
        log.exception("copy_to_buffer failed")
        return

    _cp_refresh_buffer_field()
    _cp_build_map_checkboxes(copied)
    _cp_set_info("Copied {0} map(s) into buffer.".format(len(copied)))
    cmds.inViewMessage(
        amg='<hl>AdonisFX:</hl> Copied {0} map(s).'.format(len(copied)),
        pos='midCenter', fade=True, fadeStayTime=1500,
    )


def _cp_do_paste(*_):
    if not _weights_buffer:
        cmds.warning("Buffer is empty. Copy weights first.")
        return

    selected = _cp_get_selected_maps()
    if not selected:
        cmds.warning("Select at least one map to paste.")
        return

    all_buf = set(_weights_buffer["maps"].keys())
    maps_arg = None if set(selected) == all_buf else selected
    mirror_x = cmds.checkBox(_ui_state["cp_mirror_cb"], query=True, value=True)

    try:
        pasted = paste_from_buffer(maps=maps_arg, mirror_x=mirror_x)
    except Exception as exc:
        cmds.confirmDialog(title="AdonisFX Copy/Paste - Error",
                           message=str(exc), button=["OK"], icon="critical")
        log.exception("paste_from_buffer failed")
        return

    msg = "Pasted {0} map(s){1}.".format(
        len(pasted), " (X-mirrored)" if mirror_x else ""
    )
    _cp_set_info(msg)
    cmds.inViewMessage(
        amg='<hl>AdonisFX:</hl> ' + msg,
        pos='midCenter', fade=True, fadeStayTime=2000,
    )


def _cp_do_clear(*_):
    clear_buffer()
    _cp_refresh_buffer_field()
    _cp_build_map_checkboxes(None)
    _cp_set_info("Buffer cleared.")


# --- Mirror L->R tab callbacks ---------------------------------------------

def _mr_set_info(message, warn=False):
    color = [0.9, 0.5, 0.4] if warn else [0.6, 0.85, 0.6]
    cmds.text(_ui_state["mr_info_field"], edit=True,
              label=message, backgroundColor=color)


def _mr_get_selected_types():
    return tuple(
        t for t, cb in _ui_state["mr_type_checkboxes"].items()
        if cmds.checkBox(cb, query=True, value=True)
    )


def _mr_clear_preview():
    layout = _ui_state["mr_preview_layout"]
    children = cmds.columnLayout(layout, query=True, childArray=True) or []
    for c in children:
        cmds.deleteUI(c)


def _mr_render_preview(candidates):
    layout = _ui_state["mr_preview_layout"]
    _mr_clear_preview()

    if not candidates:
        cmds.text(label="  (no L_ deformers found - scan with selection)",
                  parent=layout, align="left")
        return

    header = cmds.rowLayout(numberOfColumns=3,
                             columnWidth3=(220, 220, 60),
                             adjustableColumn=2,
                             parent=layout)
    cmds.text(label="Source (L_)", align="left", font="boldLabelFont", parent=header)
    cmds.text(label="Target (R_)", align="left", font="boldLabelFont", parent=header)
    cmds.text(label="Status", align="left", font="boldLabelFont", parent=header)

    for c in candidates:
        row = cmds.rowLayout(numberOfColumns=3,
                              columnWidth3=(220, 220, 60),
                              adjustableColumn=2,
                              parent=layout)
        cmds.text(label=_ui_short(c["src_node"]) + "  ({0})".format(c["src_type"]),
                  align="left", parent=row)
        cmds.text(label=_ui_short(c["dst_node"]), align="left", parent=row)
        status = "update" if c["dst_exists"] else "create"
        cmds.text(label=status, align="left", parent=row)


def _mr_do_scan(*_):
    types = _mr_get_selected_types()
    if not types:
        _mr_set_info("Select at least one deformer type.", warn=True)
        _mr_render_preview([])
        _ui_state["mr_candidates"] = []
        return

    try:
        candidates = scan_mirror_candidates(types=types)
    except Exception as exc:
        _mr_set_info(str(exc), warn=True)
        _mr_render_preview([])
        _ui_state["mr_candidates"] = []
        return

    _ui_state["mr_candidates"] = candidates
    _mr_render_preview(candidates)

    if not candidates:
        _mr_set_info("No L_ deformers of selected types found in selection.", warn=True)
    else:
        to_create = sum(1 for c in candidates if not c["dst_exists"])
        to_update = len(candidates) - to_create
        _mr_set_info(
            "Found {0} candidate(s): {1} to create, {2} to update.".format(
                len(candidates), to_create, to_update
            )
        )


def _mr_do_execute(*_):
    candidates = _ui_state["mr_candidates"]
    if not candidates:
        cmds.warning("Nothing to mirror. Click Scan first.")
        return

    create_missing = cmds.checkBox(_ui_state["mr_create_cb"], query=True, value=True)
    types = _mr_get_selected_types()

    try:
        summary = mirror_l_to_r(types=types, create_missing=create_missing)
    except Exception as exc:
        cmds.confirmDialog(title="AdonisFX Mirror - Error",
                           message=str(exc), button=["OK"], icon="critical")
        log.exception("mirror_l_to_r failed")
        return

    msg = "Mirror done: created={0}, updated={1}, skipped={2}.".format(
        len(summary["created"]), len(summary["updated"]), len(summary["skipped"])
    )
    _mr_set_info(msg)
    cmds.inViewMessage(
        amg='<hl>AdonisFX:</hl> ' + msg,
        pos='midCenter', fade=True, fadeStayTime=2500,
    )

    _mr_do_scan()


# --- Replace Mesh tab callbacks --------------------------------------------

def _rp_refresh_from_selection(*_):
    sel = cmds.ls(selection=True, long=True)
    _ui_state["rp_old_transform"] = None
    _ui_state["rp_new_transform"] = None
    cmds.textField(_ui_state["rp_old_field"], edit=True, text="")
    cmds.textField(_ui_state["rp_new_field"], edit=True, text="")

    if len(sel) != 2:
        _rp_set_info(
            "Select exactly 2 meshes (OLD first, NEW second). Got {0}.".format(len(sel)),
            warn=True,
        )
        return

    old, new = sel
    old_shape = _get_mesh_shape(old)
    new_shape = _get_mesh_shape(new)

    cmds.textField(_ui_state["rp_old_field"], edit=True, text=_ui_short(old))
    cmds.textField(_ui_state["rp_new_field"], edit=True, text=_ui_short(new))

    if not old_shape:
        _rp_set_info("OLD selection is not a mesh.", warn=True)
        return
    if not new_shape:
        _rp_set_info("NEW selection is not a mesh.", warn=True)
        return

    old_skin      = _get_skin_cluster(old_shape)
    old_deformers = _find_all_deformers_in_history(old_shape)

    parts = []
    if old_skin:
        parts.append("skinCluster")
    if old_deformers:
        parts.append("{0} Adn deformer(s)".format(len(old_deformers)))

    if parts:
        _rp_set_info("Ready. Found on OLD mesh: {0}.".format(", ".join(parts)))
    else:
        _rp_set_info("Old mesh has no skinCluster or AdonisFX deformers - nothing to transfer.",
                     warn=True)

    _ui_state["rp_old_transform"] = old
    _ui_state["rp_new_transform"] = new


def _rp_do_execute(*_):
    old_t = _ui_state.get("rp_old_transform")
    new_t = _ui_state.get("rp_new_transform")

    if not old_t or not new_t:
        cmds.warning("Refresh selection first (select OLD mesh then SHIFT+NEW mesh).")
        return
    if not cmds.objExists(old_t) or not cmds.objExists(new_t):
        cmds.warning("One or both nodes no longer exist. Refresh selection.")
        return

    transfer_skin  = cmds.checkBox(_ui_state["rp_skin_cb"],     query=True, value=True)
    transfer_adns  = cmds.checkBox(_ui_state["rp_adonis_cb"],   query=True, value=True)
    do_reparent    = cmds.checkBox(_ui_state["rp_reparent_cb"], query=True, value=True)
    do_rename      = cmds.checkBox(_ui_state["rp_rename_cb"],   query=True, value=True)
    delete_old     = cmds.checkBox(_ui_state["rp_delete_cb"],   query=True, value=True)

    action_str = "deleted" if delete_old else "hidden"
    result = cmds.confirmDialog(
        title="Replace Mesh - Confirm",
        message=(
            "This will replace:\n"
            "  OLD: {0}\n"
            "with:\n"
            "  NEW: {1}\n\n"
            "Old mesh will be {2}. This operation supports Undo.\n\n"
            "Proceed?"
        ).format(_ui_short(old_t), _ui_short(new_t), action_str),
        button=["Replace", "Cancel"],
        defaultButton="Replace",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if result != "Replace":
        return

    try:
        result_node = replace_mesh_in_setup(
            old_t, new_t,
            transfer_skin=transfer_skin,
            transfer_adonis=transfer_adns,
            reparent=do_reparent,
            rename=do_rename,
            delete_old=delete_old,
        )
    except Exception as exc:
        cmds.confirmDialog(title="Replace Mesh - Error",
                           message=str(exc), button=["OK"], icon="critical")
        log.exception("replace_mesh_in_setup failed")
        return

    msg = "Replaced: {0}  ->  {1}.".format(_ui_short(old_t), result_node)
    _rp_set_info(msg)
    cmds.inViewMessage(
        amg='<hl>AdonisFX:</hl> ' + msg,
        pos='midCenter', fade=True, fadeStayTime=3000,
    )

    # Clear state: old node may no longer exist after delete/rename
    _ui_state["rp_old_transform"] = None
    _ui_state["rp_new_transform"] = None
    cmds.textField(_ui_state["rp_old_field"], edit=True, text="")
    cmds.textField(_ui_state["rp_new_field"], edit=True, text="")


# --- Tab builders ----------------------------------------------------------

def _build_transfer_tab(parent):
    root = cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                             columnAttach=("both", 8), parent=parent)

    cmds.text(label="Transfer between two meshes", height=24,
              font="boldLabelFont", align="left", parent=root)
    cmds.text(label="Select source mesh, then shift-select destination mesh.",
              align="left", parent=root)
    cmds.separator(height=8, style="in", parent=root)

    form = cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 330),
                          adjustableColumn=2, parent=root)
    cmds.text(label="Source:", align="right", parent=form)
    _ui_state["src_field"] = cmds.textField(editable=False, parent=form)

    form2 = cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 330),
                           adjustableColumn=2, parent=root)
    cmds.text(label="Dest:", align="right", parent=form2)
    _ui_state["dst_field"] = cmds.textField(editable=False, parent=form2)

    cmds.button(label="Refresh from current selection",
                command=_ui_refresh_from_selection, parent=root)

    cmds.separator(height=8, style="in", parent=root)
    cmds.text(label="Deformers detected on source:", align="left",
              font="boldLabelFont", parent=root)

    toggle_row = cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 200),
                                adjustableColumn=2, parent=root)
    cmds.button(label="All",  command=lambda *_: _ui_toggle_all(True),
                parent=toggle_row)
    cmds.button(label="None", command=lambda *_: _ui_toggle_all(False),
                parent=toggle_row)

    scroll = cmds.scrollLayout(height=240, childResizable=True, parent=root)
    _ui_state["map_layout"] = cmds.columnLayout(adjustableColumn=True,
                                                 rowSpacing=4, parent=scroll)
    _ui_build_sections_placeholder("(select meshes to see available deformers)")

    cmds.separator(height=8, style="in", parent=root)

    _ui_state["mirror_conns_cb"] = cmds.checkBox(
        label="Mirror source connections onto destination "
              "(attenuationMatrix, targets, colliders, drivers...)",
        value=True,
        parent=root,
    )

    cmds.separator(height=8, style="in", parent=root)

    _ui_state["info_field"] = cmds.text(
        label="Select meshes and click Refresh.",
        align="left", height=28,
        backgroundColor=[0.3, 0.3, 0.3],
        parent=root,
    )

    cmds.separator(height=4, style="none", parent=root)

    cmds.button(label="COPY WEIGHTS",
                height=44,
                backgroundColor=[0.3, 0.55, 0.85],
                command=_ui_execute,
                parent=root)

    cmds.separator(height=4, style="none", parent=root)
    return root


def _build_copy_paste_tab(parent):
    root = cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                             columnAttach=("both", 8), parent=parent)

    cmds.text(label="Copy / Paste with in-memory buffer", height=24,
              font="boldLabelFont", align="left", parent=root)
    cmds.text(label="Select source mesh -> COPY. "
                    "Select dest mesh -> PASTE (X-mirror for L<->R).",
              align="left", parent=root)
    cmds.separator(height=8, style="in", parent=root)

    form = cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 330),
                          adjustableColumn=2, parent=root)
    cmds.text(label="Buffer:", align="right", parent=form)
    _ui_state["cp_buffer_field"] = cmds.textField(editable=False, text="(empty)",
                                                   parent=form)

    form2 = cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 330),
                           adjustableColumn=2, parent=root)
    cmds.text(label="Target:", align="right", parent=form2)
    _ui_state["cp_target_field"] = cmds.textField(editable=False,
                                                   text="(select 1 destination mesh)",
                                                   parent=form2)

    cmds.button(label="Refresh target from current selection",
                command=_cp_refresh_target_field, parent=root)

    cmds.separator(height=8, style="in", parent=root)
    cmds.text(label="Maps in buffer:", align="left",
              font="boldLabelFont", parent=root)

    toggle_row = cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 200),
                                adjustableColumn=2, parent=root)
    cmds.button(label="All",  command=lambda *_: _cp_toggle_all(True),
                parent=toggle_row)
    cmds.button(label="None", command=lambda *_: _cp_toggle_all(False),
                parent=toggle_row)

    _ui_state["cp_map_layout"] = cmds.columnLayout(adjustableColumn=True,
                                                    rowSpacing=2, parent=root)
    _cp_build_map_checkboxes(None)

    cmds.separator(height=8, style="in", parent=root)

    _ui_state["cp_mirror_cb"] = cmds.checkBox(
        label="Mirror in X on paste (R<->L flip via closest-point on -X)",
        value=True,
        parent=root,
    )

    cmds.separator(height=8, style="in", parent=root)

    _ui_state["cp_info_field"] = cmds.text(
        label="Buffer is empty. Copy from a mesh first.",
        align="left", height=28,
        backgroundColor=[0.3, 0.3, 0.3],
        parent=root,
    )

    cmds.separator(height=4, style="none", parent=root)

    btn_row = cmds.rowLayout(numberOfColumns=3,
                              columnWidth3=(135, 135, 90),
                              adjustableColumn=2,
                              columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2)],
                              parent=root)
    cmds.button(label="COPY",
                height=40,
                backgroundColor=[0.3, 0.55, 0.85],
                command=_cp_do_copy,
                parent=btn_row)
    cmds.button(label="PASTE",
                height=40,
                backgroundColor=[0.35, 0.7, 0.4],
                command=_cp_do_paste,
                parent=btn_row)
    cmds.button(label="Clear",
                height=40,
                command=_cp_do_clear,
                parent=btn_row)

    cmds.separator(height=4, style="none", parent=root)
    return root


def _build_mirror_tab(parent):
    root = cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                             columnAttach=("both", 8), parent=parent)

    cmds.text(label="Mirror L_ -> R_  (AdnRelax / AdnPush / AdnMush)",
              height=24, font="boldLabelFont", align="left", parent=root)
    cmds.text(label="Select a transform/group (or a mesh). The tool finds "
                    "every deformer with 'L_' in its name and copies its "
                    "scalar values to the 'R_' equivalent. Weights are NOT "
                    "touched.",
              align="left", wordWrap=True, parent=root)
    cmds.separator(height=8, style="in", parent=root)

    cmds.text(label="Deformer types to mirror:", align="left",
              font="boldLabelFont", parent=root)

    type_row = cmds.rowLayout(numberOfColumns=3,
                               columnWidth3=(130, 130, 130),
                               parent=root)
    _ui_state["mr_type_checkboxes"] = {
        "AdnRelax": cmds.checkBox(label="AdnRelax", value=True, parent=type_row),
        "AdnPush":  cmds.checkBox(label="AdnPush",  value=True, parent=type_row),
        "AdnMush":  cmds.checkBox(label="AdnMush",  value=True, parent=type_row),
    }

    _ui_state["mr_create_cb"] = cmds.checkBox(
        label="Create R_ deformer on R_ mesh if it doesn't exist yet",
        value=True,
        parent=root,
    )

    cmds.separator(height=8, style="in", parent=root)

    cmds.button(label="Scan from current selection",
                command=_mr_do_scan, parent=root)

    cmds.text(label="Preview:", align="left", font="boldLabelFont", parent=root)

    _ui_state["mr_preview_scroll"] = cmds.scrollLayout(
        height=200, childResizable=True, parent=root,
    )
    _ui_state["mr_preview_layout"] = cmds.columnLayout(
        adjustableColumn=True, rowSpacing=2,
        parent=_ui_state["mr_preview_scroll"],
    )
    _mr_render_preview([])

    cmds.separator(height=8, style="in", parent=root)

    _ui_state["mr_info_field"] = cmds.text(
        label="Select a root node and click Scan.",
        align="left", height=28,
        backgroundColor=[0.3, 0.3, 0.3],
        parent=root,
    )

    cmds.separator(height=4, style="none", parent=root)

    cmds.button(label="MIRROR L -> R",
                height=44,
                backgroundColor=[0.85, 0.55, 0.3],
                command=_mr_do_execute,
                parent=root)

    cmds.separator(height=4, style="none", parent=root)
    return root


def _build_replace_tab(parent):
    root = cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                             columnAttach=("both", 8), parent=parent)

    cmds.text(label="Replace Mesh in Rig Setup", height=24,
              font="boldLabelFont", align="left", parent=root)
    cmds.text(
        label="Select OLD mesh first, then SHIFT+select NEW mesh.\n"
              "Transfers skinCluster + all AdonisFX deformers to the new mesh\n"
              "and substitutes it in the rig hierarchy.",
        align="left", parent=root,
    )
    cmds.separator(height=8, style="in", parent=root)

    form1 = cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 330),
                           adjustableColumn=2, parent=root)
    cmds.text(label="Old mesh:", align="right", parent=form1)
    _ui_state["rp_old_field"] = cmds.textField(editable=False, parent=form1)

    form2 = cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 330),
                           adjustableColumn=2, parent=root)
    cmds.text(label="New mesh:", align="right", parent=form2)
    _ui_state["rp_new_field"] = cmds.textField(editable=False, parent=form2)

    cmds.button(label="Refresh from current selection",
                command=_rp_refresh_from_selection, parent=root)

    cmds.separator(height=8, style="in", parent=root)
    cmds.text(label="What to transfer:", align="left",
              font="boldLabelFont", parent=root)

    _ui_state["rp_skin_cb"] = cmds.checkBox(
        label="Transfer skinCluster  (joint weights, closestPoint for diff. topology)",
        value=True, parent=root,
    )
    _ui_state["rp_adonis_cb"] = cmds.checkBox(
        label="Transfer AdonisFX deformers  (weight maps + connections)",
        value=True, parent=root,
    )

    cmds.separator(height=8, style="in", parent=root)
    cmds.text(label="Substitution options:", align="left",
              font="boldLabelFont", parent=root)

    _ui_state["rp_reparent_cb"] = cmds.checkBox(
        label="Re-parent new mesh under old mesh's parent",
        value=True, parent=root,
    )
    _ui_state["rp_rename_cb"] = cmds.checkBox(
        label="Rename: new mesh takes old names  (old gets '__ORIG' suffix)",
        value=True, parent=root,
    )
    _ui_state["rp_delete_cb"] = cmds.checkBox(
        label="Delete old mesh after replace  (unchecked = hide only)",
        value=False, parent=root,
    )

    cmds.separator(height=8, style="in", parent=root)

    _ui_state["rp_info_field"] = cmds.text(
        label="Select OLD mesh, SHIFT+select NEW mesh, then click Refresh.",
        align="left", height=28,
        backgroundColor=[0.3, 0.3, 0.3],
        parent=root,
    )

    cmds.separator(height=4, style="none", parent=root)

    cmds.button(
        label="REPLACE MESH IN SETUP",
        height=48,
        backgroundColor=[0.7, 0.35, 0.75],
        command=_rp_do_execute,
        parent=root,
    )

    cmds.separator(height=4, style="none", parent=root)
    return root


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def show():
    """Build and show the AdonisFX copy-weights UI."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(WINDOW_NAME, title="AdonisFX - Copy Weights",
                      widthHeight=(480, 740), sizeable=True)

    outer = cmds.columnLayout(adjustableColumn=True, rowSpacing=4,
                               columnAttach=("both", 4), parent=win)

    cmds.text(label="AdonisFX Copy Weights", height=28,
              font="boldLabelFont", align="left", parent=outer)
    cmds.separator(height=4, style="none", parent=outer)

    tabs = cmds.tabLayout(innerMarginWidth=4, innerMarginHeight=4, parent=outer)

    transfer    = _build_transfer_tab(tabs)
    copy_paste  = _build_copy_paste_tab(tabs)
    mirror_lr   = _build_mirror_tab(tabs)
    replace_tab = _build_replace_tab(tabs)

    cmds.tabLayout(tabs, edit=True,
                   tabLabel=[
                       (transfer,    "Transfer"),
                       (copy_paste,  "Copy / Paste"),
                       (mirror_lr,   "Mirror L->R"),
                       (replace_tab, "Replace Mesh"),
                   ])

    cmds.showWindow(win)

    _ui_refresh_from_selection()
    _cp_refresh_buffer_field()
    _cp_refresh_target_field()


# ---------------------------------------------------------------------------
# Drag-and-drop launcher
# ---------------------------------------------------------------------------

def onMayaDroppedPythonFile(*_):
    show()


if __name__ == "__main__":
    show()
