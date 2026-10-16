"""Fit skin/wrap/blendshape/Delta Mush stacks to LBS with held-out validation."""
import json
import math
import os
import tempfile

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import numpy as np

from tools import proximity_wrap

SUPPORTED_STACK = ("skinCluster", "proximityWrap", "blendShape", "deltaMush")


def direct_deformers(shape):
    return proximity_wrap.direct_deformers(shape, SUPPORTED_STACK)


def points(shape):
    selection = om.MSelectionList()
    selection.add(proximity_wrap.mesh_shape(shape))
    return np.asarray(om.MFnMesh(selection.getDagPath(0)).getPoints(om.MSpace.kWorld))[:, :3].copy()


def selected_targets():
    targets = []
    for node in cmds.ls(selection=True, long=True) or []:
        geometries = (cmds.deformer(node, query=True, geometry=True) or []
                      if cmds.nodeType(node) in SUPPORTED_STACK else [node])
        targets.extend(proximity_wrap.mesh_shape(item) for item in geometries)
    targets = list(dict.fromkeys(targets))
    if not targets:
        raise RuntimeError("Select polygon meshes with skin, wrap, corrective or Delta Mush deformation.")
    for shape in targets:
        types = [cmds.nodeType(n) for n,_ in direct_deformers(shape)]
        if not types or any(t not in SUPPORTED_STACK for t in types):
            raise RuntimeError("Supported stacks: skinCluster, proximityWrap, blendShape and deltaMush: " + shape)
    return targets


def candidate_joints(shape):
    """Use driver skin weights near the target to limit the fit's joint count."""
    drivers = [shape] if any(cmds.nodeType(n) == "skinCluster" for n,_ in direct_deformers(shape)) else []
    for wrap, _ in direct_deformers(shape):
        if cmds.nodeType(wrap) != "proximityWrap":
            continue
        for index in cmds.proximityWrap(wrap, query=True, driverIndices=True) or []:
            drivers.extend(cmds.listConnections(
                "{}.drivers[{}].driverGeometry".format(wrap, index),
                source=True, destination=False, shapes=True) or [])
    joints = []
    target = points(shape)
    for driver in dict.fromkeys(drivers):
        driver = proximity_wrap.mesh_shape(driver)
        positions = points(driver)
        nearest = []
        if driver == shape:
            nearest = list(range(len(positions)))
        for start in range(0, 0 if nearest else len(target), 128):
            batch = target[start:start + 128]
            distances = (np.sum(batch ** 2, axis=1)[:, None]
                         + np.sum(positions ** 2, axis=1)[None, :]
                         - 2 * batch @ positions.T)
            k = min(8, len(positions))
            nearest.extend(np.argpartition(distances, k - 1, axis=1)[:, :k].ravel())
        selection = om.MSelectionList()
        selection.add(driver)
        path = selection.getDagPath(0)
        component_fn = om.MFnSingleIndexedComponent()
        component = component_fn.create(om.MFn.kMeshVertComponent)
        component_fn.addElements(sorted(set(int(i) for i in nearest)))
        for skin, _ in direct_deformers(driver):
            if cmds.nodeType(skin) != "skinCluster":
                continue
            selection = om.MSelectionList()
            selection.add(skin)
            fn = oma.MFnSkinCluster(selection.getDependNode(0))
            weights, stride = fn.getWeights(path, component)
            weights = np.asarray(weights).reshape(-1, stride)
            active = np.flatnonzero(weights.max(axis=0) > 1e-4)
            influences = fn.influenceObjects()
            joints.extend(influences[i].fullPathName() for i in active
                          if influences[i].node().hasFn(om.MFn.kJoint))
    joints = list(dict.fromkeys(joints))
    if not joints:
        raise RuntimeError("No se encontraron joints en los skins de los drivers de " + shape)
    return joints


def project_simplex(values):
    ordered = np.sort(values, axis=1)[:, ::-1]
    cumulative = np.cumsum(ordered, axis=1) - 1
    counts = np.arange(1, values.shape[1] + 1)
    rho = (ordered - cumulative / counts > 0).sum(axis=1) - 1
    threshold = cumulative[np.arange(len(values)), rho] / (rho + 1)
    return np.maximum(values - threshold[:, None], 0)


def solve_simplex_quadratic(hessian, linear, iterations=1800):
    weights = np.full(linear.shape, 1 / linear.shape[1])
    extrapolated = weights.copy()
    factor = 1.0
    lipschitz = np.maximum(np.linalg.eigvalsh(hessian)[:, -1], 1e-10)
    for iteration in range(iterations):
        gradient = np.einsum("vij,vj->vi", hessian, extrapolated) - linear
        updated = project_simplex(extrapolated - gradient / lipschitz[:, None])
        next_factor = (1 + math.sqrt(1 + 4 * factor * factor)) / 2
        extrapolated = updated + ((factor - 1) / next_factor) * (updated - weights)
        delta = np.max(np.abs(updated - weights))
        weights, factor = updated, next_factor
        if iteration > 200 and delta < 2e-7:
            break
    return weights


def fit_weights(samples, matrices, max_influences):
    count, frames = matrices.shape[:2]
    relative = np.linalg.inv(matrices[:, 0])[:, None] @ matrices - np.eye(4)[None, None]
    if np.max(np.abs(relative)) < 1e-6:
        raise RuntimeError("Los joints no cambian entre poses. Anima un rango de movimiento antes del bake.")
    design = relative[:, :, :, :3].transpose(0, 2, 1, 3).reshape(count * 4, frames * 3)
    homogeneous = np.column_stack((samples[0], np.ones(len(samples[0]))))
    displacements = (samples - samples[0]).transpose(0, 2, 1).reshape(frames * 3, len(samples[0]))
    gram = (design @ design.T).reshape(count, 4, count, 4) / frames
    # Bound memory use for large meshes by fitting vertices in batches.
    result = []
    for start in range(0, len(homogeneous), 256):
        p = homogeneous[start:start + 256]
        hessian = np.einsum("va,jakb,vb->vjk", p, gram, p, optimize=True)
        linear = np.einsum("jav,va->vj", (design @ displacements[:, start:start + 256])
                           .reshape(count, 4, len(p)), p) / frames
        reg = max(float(np.max(np.diagonal(hessian, axis1=1, axis2=2))) * 1e-9, 1e-10)
        hessian += np.eye(count)[None] * reg
        linear += reg / count
        weights = solve_simplex_quadratic(hessian, linear)
        if count > max_influences:
            support = np.argsort(weights, axis=1)[:, -max_influences:]
            rows = np.arange(len(weights))[:, None, None]
            restricted = hessian[rows, support[:, :, None], support[:, None, :]]
            sparse = solve_simplex_quadratic(restricted, np.take_along_axis(linear, support, axis=1), 900)
            weights[:] = 0
            weights[np.arange(len(weights))[:, None], support] = sparse
        result.append(weights)
        check_cancel()
    return np.concatenate(result)


def check_cancel():
    if cmds.progressWindow(query=True, isCancelled=True):
        raise RuntimeError("Bake cancelado.")


def bind_copy(shape, joints, weights, max_influences):
    transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    short = transform.rsplit("|", 1)[-1]
    duplicate = cmds.duplicate(transform, name=short + "_BAKED", returnRootsOnly=True)[0]
    cmds.delete(duplicate, constructionHistory=True)
    for child in cmds.listRelatives(duplicate, shapes=True, fullPath=True) or []:
        if cmds.getAttr(child + ".intermediateObject"):
            cmds.delete(child)
    skin = cmds.skinCluster(joints, duplicate, toSelectedBones=True, skinMethod=0,
                            maximumInfluences=max_influences, normalizeWeights=1,
                            name=short + "_BAKED_SKC")[0]
    selection = om.MSelectionList()
    selection.add(skin)
    fn = oma.MFnSkinCluster(selection.getDependNode(0))
    selection = om.MSelectionList()
    selection.add(proximity_wrap.mesh_shape(duplicate))
    path = selection.getDagPath(0)
    component_fn = om.MFnSingleIndexedComponent()
    component = component_fn.create(om.MFn.kMeshVertComponent)
    component_fn.setCompleteData(len(weights))
    columns = [joints.index(item.fullPathName()) for item in fn.influenceObjects()]
    fn.setWeights(path, component, om.MIntArray(range(len(columns))),
                  om.MDoubleArray(weights[:, columns].ravel().tolist()), False)
    return duplicate, skin


def export_baked_snapshot(manager, snapshot, records, output):
    """Replace only baked targets' entries; leave all other scene data intact."""
    key = manager.SCENE_DEFORMERS_KEY
    metadata = snapshot[key]
    removed = set()
    with tempfile.TemporaryDirectory(prefix="proximity_bake_") as temp:
        cmds.select([record["destination"] for record in records], replace=True)
        path = os.path.join(temp, "copies.skc")
        manager.export_skins(in_path=path)
        with open(path) as stream:
            baked = json.load(stream)
    for record in records:
        source = record["source"]
        transform = cmds.listRelatives(source, parent=True, fullPath=True)[0]
        # Match shapes by their full/partial DAG paths, even with duplicate leaf names.
        for name in list(snapshot):
            if name == key:
                continue
            if source in (cmds.ls(name, long=True) or []):
                snapshot.pop(name)
        removed.update(node for node, _ in direct_deformers(source))
        copy_shape = proximity_wrap.mesh_shape(record["destination"])
        copy_key = next(name for name in baked if name != key
                        and copy_shape in (cmds.ls(name, long=True) or []))
        snapshot[transform] = baked[copy_key]
        metadata["geometry_stacks"][source] = [record["skin"]]
    metadata["nodes"] = [node for node in metadata["nodes"] if node["name"] not in removed]
    metadata["pose_targets"] = [pose for pose in metadata.get("pose_targets", [])
                                if pose["blendShape"] not in removed]
    metadata["bake_validation"] = records
    for stack in metadata["geometry_stacks"].values():
        stack[:] = [node for node in stack if node not in removed]
    # Exclusive creation ensures an existing version is never overwritten.
    with open(output, "x") as stream:
        json.dump(snapshot, stream, separators=(",", ":"))


def error_colors(mesh, per_vertex, limit=None):
    """Color the baked copy only; originals and their color sets are untouched."""
    shape = proximity_wrap.mesh_shape(mesh)
    name = "bakeError"
    if name not in (cmds.polyColorSet(shape, query=True, allColorSets=True) or []):
        cmds.polyColorSet(shape, create=True, colorSet=name)
    cmds.polyColorSet(shape, currentColorSet=True, colorSet=name)
    selection = om.MSelectionList(); selection.add(shape)
    fn = om.MFnMesh(selection.getDagPath(0))
    scale = limit or max(float(max(per_vertex, default=0)), 1e-8)
    colors = [om.MColor((min(1., float(e) / scale), 1. - min(1., float(e) / scale), .1, 1.)) for e in per_vertex]
    fn.setVertexColors(om.MColorArray(colors), om.MIntArray(range(len(colors))))
    cmds.setAttr(proximity_wrap.mesh_shape(mesh) + ".displayColors", True)


def bake_selected(start, end, step=1, bind_frame=None, max_influences=8, export_path=None,
                  validation_frames=None, error_limit=None, color_error=False):
    targets = selected_targets()
    if end <= start or step <= 0 or max_influences < 1:
        raise RuntimeError("Usa un rango de varias poses, paso positivo e influencias >= 1.")
    if not all(math.isfinite(v) for v in (start,end,step)):
        raise RuntimeError("Frame range and step must be finite.")
    if error_limit is not None and (not math.isfinite(error_limit) or error_limit <= 0):
        raise RuntimeError("Maximum accepted error must be positive and finite.")
    if export_path and os.path.exists(export_path):
        raise RuntimeError("El archivo ya existe. Elige una nueva version: " + export_path)
    if not cmds.undoInfo(query=True, state=True):
        raise RuntimeError("Activa Undo antes del bake.")
    bind_frame = start if bind_frame is None else bind_frame
    if not math.isfinite(bind_frame):
        raise RuntimeError("Bind frame must be finite.")
    frames = list(dict.fromkeys([float(bind_frame)] + np.arange(start, end, step).tolist() + [float(end)]))
    ordered = sorted(set(frames))
    held_out = [(a+b)*.5 for a,b in zip(ordered,ordered[1:])] if validation_frames is None else list(validation_frames)
    if any(not math.isfinite(f) or f in frames for f in held_out):
        raise RuntimeError("Validation frames must be finite and excluded from the fit frames.")
    held_out = list(dict.fromkeys(float(f) for f in held_out))
    all_frames = frames + held_out
    original_time = cmds.currentTime(query=True)
    selection = cmds.ls(selection=True, long=True) or []
    records = []
    error = None
    progress_open = False
    cmds.undoInfo(openChunk=True, chunkName="Bake_Deformation_To_Skin")
    try:
        cmds.progressWindow(title="Bake Deformation to Skin", progress=0, maxValue=len(all_frames) + len(targets),
                            status="Preparando...", isInterruptable=True)
        progress_open = True
        cmds.currentTime(bind_frame)
        snapshot = manager = None
        if export_path:
            from tools.skin_manager_api import SkinManager
            manager = SkinManager()
            cmds.select(clear=True)
            with tempfile.TemporaryDirectory(prefix="proximity_bake_") as temp:
                path = os.path.join(temp, "source.skc")
                manager.export_skins(in_path=path)
                with open(path) as stream:
                    snapshot = json.load(stream)
            # Shared target deformers cannot be removed from a rebuild independently.
            for shape in targets:
                if any(members != {shape} for _, members in direct_deformers(shape)):
                    raise RuntimeError("Export no admite deformers compartidos: " + shape)
                stack = snapshot[manager.SCENE_DEFORMERS_KEY]["geometry_stacks"].get(shape, [])
                types = {node["name"]: node["type"]
                         for node in snapshot[manager.SCENE_DEFORMERS_KEY]["nodes"]}
                if any(types.get(node) not in SUPPORTED_STACK for node in stack):
                    raise RuntimeError("Export supports skin, wrap, blendshape and Delta Mush stacks: " + shape)
        candidates = {shape: candidate_joints(shape) for shape in targets}
        joints = list(dict.fromkeys(joint for group in candidates.values() for joint in group))
        world = {joint: [] for joint in joints}
        samples = {shape: [] for shape in targets}
        for index, frame in enumerate(all_frames):
            check_cancel()
            cmds.currentTime(frame)
            for joint in joints:
                world[joint].append(cmds.xform(joint, query=True, worldSpace=True, matrix=True))
            for shape in targets:
                samples[shape].append(points(shape))
            cmds.progressWindow(edit=True, progress=index + 1, status="Pose {}/{}".format(index + 1, len(all_frames)))
        for index, shape in enumerate(targets):
            check_cancel()
            cmds.progressWindow(edit=True, status="Ajustando " + shape.rsplit("|", 1)[-1])
            matrices = np.asarray([world[joint][:len(frames)] for joint in candidates[shape]]).reshape(-1, len(frames), 4, 4)
            weights = fit_weights(np.asarray(samples[shape][:len(frames)]), matrices, max_influences)
            cmds.currentTime(bind_frame)
            destination, skin = bind_copy(shape, candidates[shape], weights, max_influences)
            metrics = []
            vertex_error = np.zeros(len(weights))
            for frame, expected in zip(all_frames, samples[shape]):
                check_cancel()
                cmds.currentTime(frame)
                distances = np.linalg.norm(points(destination) - expected, axis=1)
                if not np.isfinite(distances).all():
                    raise RuntimeError("Non-finite baked geometry: " + shape)
                vertex_error = np.maximum(vertex_error, distances)
                metrics.append({"frame": frame, "set": "fit" if frame in frames else "held_out",
                                "rms": float(np.sqrt(np.mean(distances ** 2))),
                                "max": float(distances.max())})
            record = {"source": shape, "destination": destination, "skin": skin,
                      "validation": metrics, "worst_rms": max(item["rms"] for item in metrics),
                      "worst_max": max(item["max"] for item in metrics),
                      "vertex_error": vertex_error.tolist(), "units": cmds.currentUnit(query=True, linear=True),
                      "held_out_max": max((m["max"] for m in metrics if m["set"] == "held_out"), default=None)}
            if error_limit is not None and record["worst_max"] > error_limit:
                raise RuntimeError("Bake error %.6g exceeds limit %.6g %s; originals preserved." % (
                    record["worst_max"], error_limit, record["units"]))
            if color_error:
                error_colors(destination, vertex_error, error_limit)
            metadata = cmds.createNode("network", name=skin + "_validation")
            cmds.addAttr(metadata, longName="bakeValidation", dataType="string")
            cmds.setAttr(metadata + ".bakeValidation", json.dumps(record), type="string")
            cmds.addAttr(metadata, longName="destination", attributeType="message")
            cmds.connectAttr(destination + ".message", metadata + ".destination")
            record["metadata"] = metadata
            records.append(record)
            print("Bake {}: RMS {:.6f}, max {:.6f} ({})".format(
                shape, record["worst_rms"], record["worst_max"], cmds.currentUnit(query=True, linear=True)))
            cmds.progressWindow(edit=True, progress=len(all_frames) + index + 1)
        cmds.currentTime(bind_frame)
        if export_path:
            export_baked_snapshot(manager, snapshot, records, export_path)
        cmds.select([record["destination"] for record in records], replace=True)
    except Exception as exc:
        error = exc
    finally:
        cmds.currentTime(original_time)
        if progress_open:
            cmds.progressWindow(endProgress=True)
        cmds.undoInfo(closeChunk=True)
    if error:
        cmds.undo()
        cmds.select(selection, replace=True)
        raise RuntimeError(str(error))
    return {"records": records, "frames": frames, "validation_frames": held_out,
            "bind_frame": bind_frame, "export_path": export_path}
