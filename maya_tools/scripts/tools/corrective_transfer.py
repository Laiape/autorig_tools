"""Transfer captured corrective sculpts with surface mapping and optional landmarks.

Registration/fitting happens once during authoring. Destination runtime uses
the existing SDK or shared native orientation pose and ordinary blendshapes.
Both rest meshes must use aligned object-space coordinates, or supply paired
landmarks to register target coordinates to the source.
"""
import json
import math

import numpy as np
from maya import cmds
from maya.api import OpenMaya as om

from maya_tools.scripts.tools import pose_blendshapes as poses
from maya_tools.scripts.tools import orientation_correctives as orientation
from maya_tools.scripts.tools import rig_validation


def landmark_warp(points, target_landmarks, source_landmarks):
    """Affine + Gaussian residual RBF registration, with displacement Jacobians."""
    x, y = np.asarray(target_landmarks, dtype=float), np.asarray(source_landmarks, dtype=float)
    points = np.asarray(points, dtype=float)
    if x.shape != y.shape or x.ndim != 2 or x.shape[1] != 3 or len(x) < 4:
        raise ValueError("Provide at least four paired 3D landmarks.")
    if not all(np.isfinite(a).all() for a in (x, y, points)):
        raise ValueError("Landmarks and points must be finite.")
    distances = np.linalg.norm(x[:, None] - x[None], axis=2)
    if np.any(distances[np.triu_indices(len(x), 1)] < 1e-8):
        raise ValueError("Target landmarks must be distinct.")
    center = x.mean(axis=0)
    scale = max(float(np.median(distances[distances > 1e-8])), 1e-8)
    basis = np.column_stack(((x - center) / scale, np.ones(len(x))))
    affine = np.linalg.lstsq(basis, y - x, rcond=None)[0]
    residual = y - x - basis @ affine
    kernel = np.exp(-(distances / scale) ** 2)
    coefficients = np.linalg.solve(kernel + np.eye(len(x)) * 1e-8, residual)
    delta = points[:, None] - x[None]
    values = np.exp(-np.sum(delta ** 2, axis=2) / scale ** 2)
    mapped = points + np.column_stack(((points - center) / scale, np.ones(len(points)))) @ affine + values @ coefficients
    gradients = -2 * delta / scale ** 2 * values[:, :, None]
    jacobian = np.eye(3)[None] + affine[:3][None] / scale + np.einsum("vni,nj->vij", gradients, coefficients)
    if np.any(np.linalg.cond(jacobian) > 1e6):
        raise ValueError("Landmarks collapse a region; choose better distributed correspondences.")
    return mapped, np.linalg.inv(jacobian)


def surface_deltas(source_points, counts, indices, source_deltas, target_points, landmarks=None, max_distance=None):
    points = np.asarray(target_points, dtype=float)
    inverse = np.broadcast_to(np.eye(3), (len(points), 3, 3))
    if landmarks:
        points, inverse = landmark_warp(points, landmarks["target"], landmarks["source"])
    if max_distance is not None and (not math.isfinite(max_distance) or max_distance <= 0):
        raise ValueError("Maximum match distance must be positive and finite.")
    data = om.MFnMeshData().create()
    fn = om.MFnMesh()
    mesh = fn.create([om.MPoint(*p) for p in source_points], counts, indices, parent=data)
    intersector = om.MMeshIntersector(); intersector.create(mesh, om.MMatrix())
    source_deltas = np.asarray(source_deltas)
    result, distances = [], []
    for i, p in enumerate(points):
        hit = intersector.getClosestPoint(om.MPoint(*p))
        triangle = fn.getPolygonTriangleVertices(hit.face, hit.triangle)
        u, v = hit.barycentricCoords
        coefficients = np.maximum([u, v, 1 - u - v], 0)
        coefficients /= coefficients.sum()
        distance = (om.MPoint(*p) - om.MPoint(hit.point)).length()
        distances.append(distance)
        delta = coefficients @ source_deltas[list(triangle)]
        if max_distance is not None and distance > max_distance:
            delta = np.zeros(3)
        result.append(delta @ inverse[i])
    return np.asarray(result), distances


def _destination_controller(source, target_mesh, explicit=None):
    if explicit:
        return orientation._transform(explicit)
    root = "|" + poses.mesh_transform(target_mesh).split("|")[1]
    from maya_tools.scripts.tools import rig_roles
    root = rig_roles.root_for(target_mesh) or root
    matched = rig_roles.counterpart(source, destination_root=root)
    if matched:
        return matched
    leaf = source.rsplit("|", 1)[-1].split(":")[-1]
    matches = [n for n in cmds.ls(type="transform", long=True) or []
               if n.startswith(root + "|") and n.rsplit("|", 1)[-1].split(":")[-1] == leaf]
    if len(matches) != 1:
        raise ValueError("Choose the matching destination controller explicitly.")
    return matches[0]


@poses.undoable
def transfer_target(source_mesh, bs, index, target_mesh, destination_bs=None, controller=None,
                    landmarks=None, max_distance=None, vertices=None, destination_orientation_system=None,
                    controller_map=None, _single=False):
    poses._idle()
    source_mesh, target_mesh = poses.mesh_transform(source_mesh), poses.mesh_transform(target_mesh)
    if source_mesh == target_mesh:
        raise ValueError("Choose another destination mesh.")
    source_record = poses.pose_record(bs, index)
    if source_record and not _single:
        from maya_tools.scripts.tools import combination_correctives
        if combination_correctives.data(source_record):
            if controller or destination_orientation_system:
                raise ValueError('Combination transfer needs controller_map, not a single controller or orientation system.')
            return combination_correctives.transfer(source_mesh, bs, index, target_mesh, destination_bs,
                controller_map=controller_map, landmarks=landmarks, max_distance=max_distance, vertices=vertices)
    if not source_record or poses.linked(source_record, "mesh") != source_mesh:
        # Message links can return a short path; compare resolved transforms.
        if not source_record or poses.mesh_transform(poses.linked(source_record, "mesh")) != source_mesh:
            raise ValueError("Choose a captured pose target belonging to the source mesh.")
    control = _destination_controller(poses.linked(source_record, "controller"), target_mesh, controller)
    values = json.loads(cmds.getAttr(source_record + ".channels"))
    if any(not cmds.objExists(control + "." + v["channel"]) for v in values):
        raise ValueError("Destination controller is missing captured channels.")
    roots = {"|" + m.split("|")[1] for m in (source_mesh, target_mesh)}
    neutral = {}
    for root in roots:
        defaults, skipped = rig_validation._neutral_values(root)
        if any(cmds.getAttr(p) != (cmds.attributeQuery(p.rsplit(".", 1)[1], node=p.rsplit(".", 1)[0], listDefault=True) or [0])[0]
               for p in skipped if cmds.getAttr(p, type=True) in ("double", "doubleAngle", "doubleLinear", "float")):
            raise ValueError("Neutralize driven/locked controls before transferring sculpts.")
        neutral.update(defaults)
    neutral.update({bs + ".weight[%d]" % i: 0 for i, _ in poses.targets(bs)})
    selection = cmds.ls(selection=True, long=True) or []
    try:
        with poses._temporary_values(neutral):
            base = poses._mesh_points(source_mesh)
            cmds.setAttr(bs + ".weight[%d]" % index, 1)
            corrected = poses._mesh_points(source_mesh)
            cmds.setAttr(bs + ".weight[%d]" % index, 0)
            target_base = poses._mesh_points(target_mesh)
            source_data = rig_validation.mesh_data(source_mesh)
            target_data = rig_validation.mesh_data(target_mesh)
            selection_list = om.MSelectionList(); selection_list.add(source_mesh)
            path = selection_list.getDagPath(0); path.extendToShape()
            counts, indices = om.MFnMesh(path).getVertices()
            vectors = [[b.x-a.x, b.y-a.y, b.z-a.z] for a,b in zip(base,corrected)]
            deltas, distances = surface_deltas(source_data["points"], counts, indices, vectors,
                                               target_data["points"], landmarks, max_distance)
            if vertices is not None:
                vertex_set = set(int(i) for i in vertices)
                if not vertex_set or min(vertex_set) < 0 or max(vertex_set) >= len(deltas):
                    raise ValueError("Choose valid destination vertex indices.")
                deltas[[i for i in range(len(deltas)) if i not in vertex_set]] = 0
            if not np.any(np.linalg.norm(deltas, axis=1) > 1e-8):
                raise ValueError("No sculpt displacement reaches the destination region.")
            destination_bs = destination_bs or poses.create_blendshape(target_mesh, "post")
            poses.geometry_index(destination_bs, target_mesh)
            new_index, name = poses._create_pose_target(target_mesh, destination_bs, control, values)
            new_record = poses.pose_record(destination_bs, new_index)
            source_name = dict(poses.targets(bs))[index]
            if name != source_name and source_name not in {alias for i,alias in poses.targets(destination_bs) if i != new_index}:
                cmds.aliasAttr(destination_bs + ".weight[%d]" % new_index, remove=True)
                cmds.aliasAttr(source_name, destination_bs + ".weight[%d]" % new_index)
                cmds.setAttr(new_record + ".targetName", source_name, type="string")
                name = source_name
            weight = destination_bs + ".weight[%d]" % new_index
            with poses._temporary_values({weight: 1}):
                cmds.sculptTarget(destination_bs, edit=True, target=new_index)
                try:
                    for i, delta in enumerate(deltas):
                        if np.linalg.norm(delta) > 1e-8:
                            cmds.move(*delta.tolist(), target_mesh + ".vtx[%d]" % i, relative=True, objectSpace=True)
                finally:
                    cmds.sculptTarget(destination_bs, edit=True, target=-1)
            source_system = orientation.linked(source_record, "orientationSystem")
            if destination_orientation_system:
                source_pi = orientation.linked(source_system, "interpolator") if source_system else None
                kind = (cmds.getAttr(source_pi + ".pose[%d].poseType" % cmds.getAttr(source_record + ".orientationPose"))
                        if source_pi else 0)
                pose_type = next(k for k,v in orientation.POSE_TYPES.items() if v == kind)
                with poses._temporary_values({control + "." + v["channel"]: v["pose"] for v in values}):
                    orientation.attach_target(destination_orientation_system, destination_bs, new_index, new_record, pose_type)
            elif source_system and len(roots) == 1:
                orientation.share_target(source_system, cmds.getAttr(source_record + ".orientationPose"),
                                         destination_bs, new_index, new_record)
            metadata = {"version": 1, "source_mesh": source_mesh, "source_target": source_name,
                        "source_topology": source_data["topology"], "target_topology": target_data["topology"],
                        "landmarks": landmarks, "max_distance": max_distance,
                        "max_match_distance": max(distances),
                        "unmatched": sum(d > max_distance for d in distances) if max_distance is not None else 0,
                        "affected_vertices": int(np.count_nonzero(np.linalg.norm(deltas, axis=1) > 1e-8))}
            poses._string(new_record, "transferData", json.dumps(metadata))
        return {"blendShape": destination_bs, "index": new_index, "name": name, "transfer": metadata}
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
