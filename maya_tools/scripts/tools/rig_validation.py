"""Repeatable combination-pose geometry reports and measured evaluation costs."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from maya import cmds
from maya.api import OpenMaya as om

from maya_tools.scripts.tools import pose_blendshapes as poses

# Values are stress poses, not anatomical limits. Report missing channels.
COMBINATION_POSES = [
    ("neutral", {}),
    ("shoulder_raise_twist", {"{side}_shoulderFk_CTL.rotateZ": 90, "{side}_shoulderFk_CTL.rotateX": 45}),
    ("shoulder_front_elbow", {"{side}_shoulderFk_CTL.rotateY": 60, "{side}_elbowFk_CTL.rotateY": 90}),
    ("hip_flex_twist", {"{side}_hipFk_CTL.rotateZ": 90, "{side}_hipFk_CTL.rotateX": 30}),
    ("hip_abduction_knee", {"{side}_hipFk_CTL.rotateY": 45, "{side}_kneeFk_CTL.rotateZ": 90}),
    ("jaw_open_smile", {"C_jaw_CTL.rotateX": 30, "L_lipCorner_CTL.translateX": 5, "R_lipCorner_CTL.translateX": 5}),
    ("jaw_half_smile", {"C_jaw_CTL.rotateX": 15, "L_lipCorner_CTL.translateX": 2.5, "R_lipCorner_CTL.translateX": 2.5}),
    ("lip_up_jaw", {"C_jaw_CTL.rotateX": 15, "L_lipCorner_CTL.translateY": 3, "R_lipCorner_CTL.translateY": 3}),
    ("brow_frown", {"L_eyebrowIn_CTL.translateY": -2, "R_eyebrowIn_CTL.translateY": -2}),
    ("blink_side_look", {"{side}_eyeDirect_CTL.Upper_Blink": 1, "{side}_eyeDirect_CTL.Lower_Blink": 1,
                          "{side}_eyeDirect_CTL.rotateY": 25}),
]


def mesh_data(mesh):
    mesh = poses.mesh_transform(mesh)
    shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True)[0]
    selection = om.MSelectionList(); selection.add(shape)
    fn = om.MFnMesh(selection.getDagPath(0))
    points = [[p.x, p.y, p.z] for p in fn.getPoints(om.MSpace.kObject)]
    if any(not math.isfinite(v) for p in points for v in p):
        raise ValueError("Non-finite evaluated vertices on " + mesh)
    counts, indices = fn.getVertices()
    signature = hashlib.sha256(json.dumps([list(counts), list(indices)], separators=(",", ":")).encode()).hexdigest()
    return {"points": points, "topology": signature, "vertices": len(points),
            "world_matrix": cmds.xform(mesh,query=True,worldSpace=True,matrix=True)}


def _controls(root):
    root = cmds.ls(root, long=True)[0]
    from maya_tools.scripts.tools import rig_roles
    bound = [b['node'] for b in rig_roles.bindings(root) if b['kind'] == 'control']
    return list(dict.fromkeys(bound + [n for n in cmds.ls(type="transform", long=True) or []
            if (n == root or n.startswith(root + "|")) and n.rsplit("|", 1)[-1].endswith("_CTL")]))


def _neutral_values(root):
    values, skipped = {}, []
    for control in _controls(root):
        for attr in cmds.listAttr(control, keyable=True, scalar=True) or []:
            if attr == "visibility":
                continue
            plug = control + "." + attr
            default = cmds.attributeQuery(attr, node=control, listDefault=True) or []
            if len(default) != 1 or not isinstance(default[0], (int, float)):
                continue
            sources = cmds.listConnections(plug, source=True, destination=False, skipConversionNodes=True) or []
            if cmds.getAttr(plug, lock=True) or any(not cmds.nodeType(n).startswith("animCurve") for n in sources):
                skipped.append(plug)
                continue
            values[plug] = default[0]
    return values, skipped


def resolve_cases(root, cases=None, sides=("L", "R")):
    if isinstance(cases, dict):
        from maya_tools.scripts.tools import rig_profiles
        return rig_profiles.resolve_cases(root, cases, sides)
    from maya_tools.scripts.tools import rig_roles
    controls = _controls(root)
    by_leaf = {}
    for control in controls:
        by_leaf.setdefault(control.rsplit("|", 1)[-1].split(":")[-1], []).append(control)
    neutral, skipped = _neutral_values(root)
    # ROM poses on limbs must evaluate the FK control, regardless of its old state.
    fk_values = {p: 1 for p in neutral if p.endswith(".Ik_Fk")}
    resolved, missing = [], []
    names = set()
    for name, channels in (COMBINATION_POSES if cases is None else cases):
        if name in names or not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise ValueError("Use unique pose names containing letters, digits, underscores or hyphens.")
        if any(not math.isfinite(v) for v in channels.values()):
            raise ValueError("Pose channel values must be finite.")
        names.add(name)
        values = dict(neutral)
        values.update(fk_values)
        used, omitted = [], []
        for template, value in channels.items():
            for side in sides if "{side}" in template else ("",):
                leaf, attr = template.format(side=side).rsplit(".", 1)
                bound = rig_roles.alias_node(root, leaf)
                nodes = [bound] if bound else by_leaf.get(leaf, [])
                plug = nodes[0] + "." + attr if len(nodes) == 1 else None
                if not plug or plug not in neutral:
                    omitted.append(leaf + "." + attr)
                    continue
                values[plug] = value
                used.append(plug)
        missing.extend(omitted)
        resolved.append({"name": name, "values": values, "missing": omitted,
                         "active": bool(used) or not channels})
    return resolved, sorted(set(missing)), skipped


@contextmanager
def _session():
    mode = cmds.evaluationManager(query=True, mode=True)[0]
    frame = cmds.currentTime(query=True)
    selection = cmds.ls(selection=True, long=True) or []
    undo = cmds.undoInfo(query=True, state=True)
    modified = cmds.file(query=True, modified=True)
    evaluators = cmds.evaluator(query=True, enable=True) or []
    cache = "cache" in evaluators
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        if cache:
            cmds.evaluator(name="cache", enable=False)
        yield
    finally:
        cmds.evaluationManager(mode=mode)
        cmds.currentTime(frame)
        if cache:
            cmds.evaluator(name="cache", enable=True)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
        cmds.undoInfo(stateWithoutFlush=undo)
        cmds.file(modified=modified)


def audit_deformers(meshes):
    """Ask Maya about GPU eligibility; flag graph patterns without guessing FPS."""
    result = []
    for mesh in meshes:
        history = cmds.listHistory(mesh) or []
        filters = cmds.ls(history, type="geometryFilter") or []
        item = {"mesh": mesh, "stack": [{"node": n, "type": cmds.nodeType(n)} for n in filters],
                "expressions": cmds.ls(history, type="expression") or [], "live_targets": []}
        for node in cmds.ls(history, type="blendShape") or []:
            for source in cmds.listConnections(node + ".inputTarget", source=True, destination=False, plugs=True) or []:
                if cmds.nodeType(source.split(".")[0]) == "mesh":
                    item["live_targets"].append({"blendShape": node, "source": source})
        if cmds.about(batch=True):
            item["gpu"] = {"status": "unavailable", "reason": "Viewport GPU evaluation is not measured in batch Maya."}
        else:
            try:
                item["gpu"] = {"node_status": cmds.deformerEvaluator(mesh, query=True, nodeStatus=True, asText=True),
                               "messages": cmds.deformerEvaluator(mesh, query=True, message=True)}
            except RuntimeError as exc:
                item["gpu"] = {"status": "unavailable", "reason": str(exc)}
        result.append(item)
    return result


def write_build_health(root, output):
    """Small post-build audit; full pose comparisons remain an explicit Test Rig action."""
    root = cmds.ls(root, long=True)[0]
    shapes = [s for s in cmds.listRelatives(root, allDescendents=True, fullPath=True, type="mesh") or []
              if not cmds.getAttr(s + ".intermediateObject")]
    meshes = [cmds.listRelatives(s, parent=True, fullPath=True)[0] for s in shapes]
    report = {"version": 1, "maya": cmds.about(version=True), "root": root,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "evaluation_mode": cmds.evaluationManager(query=True, mode=True)[0],
              "meshes": len(meshes), "deformers": audit_deformers(meshes)}
    from maya_tools.scripts.tools import rig_roles
    report['role_bindings'] = rig_roles.snapshot(root)
    bound_controls={b['node'] for b in rig_roles.bindings(root) if b['kind']=='control'}
    report['unbound_controls']=[n for n in _controls(root) if n not in bound_controls]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, separators=(",", ":"), allow_nan=False)
    return report


def compare_reports(report, baseline):
    """Same pose definitions, units and topology are required for numeric diffs."""
    if report["units"] != baseline.get("units"):
        raise ValueError("Baseline uses different scene units.")
    old = {(p["name"], mesh): data for p in baseline["poses"] for mesh, data in p["meshes"].items()}
    differences = []
    for pose in report["poses"]:
        for mesh, data in pose["meshes"].items():
            previous = old.get((pose["name"], mesh))
            definition = next((p for p in baseline["poses"] if p["name"] == pose["name"]), None)
            if not previous or not definition or definition.get('definition', definition["channels"]) != pose.get('definition', pose["channels"]):
                differences.append({"pose": pose["name"], "mesh": mesh, "status": "incompatible_pose"})
                continue
            if previous["topology"] != data["topology"] or previous["vertices"] != data["vertices"]:
                differences.append({"pose": pose["name"], "mesh": mesh, "status": "topology_changed"})
                continue
            errors = [sum((a - b) ** 2 for a, b in zip(p, q)) for p, q in zip(data["points"], previous["points"])]
            differences.append({"pose": pose["name"], "mesh": mesh, "status": "compared",
                                "rms": math.sqrt(sum(errors) / max(1, len(errors))),
                                "max": math.sqrt(max(errors, default=0))})
    return differences


def run_report(root, meshes, output, baseline=None, cases=None, modes=("off", "serial", "parallel"), repeats=3, captures=True, sides=("L", "R"), cameras=None):
    """No keys are added. Restore channels, animation connections and Maya state."""
    if repeats < 1 or not modes or any(m not in ("off", "serial", "parallel") for m in modes):
        raise ValueError("Use positive repeats and DG/Serial/Parallel evaluation modes.")
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a new report version; existing reports are preserved.")
    root = cmds.ls(root, long=True)[0]
    meshes = list(dict.fromkeys(poses.mesh_transform(m) for m in meshes))
    if not meshes or any(not (m == root or m.startswith(root + "|")) for m in meshes):
        raise ValueError("Load meshes belonging to the same character root.")
    resolved, missing, skipped = resolve_cases(root, cases, sides)
    old_report = json.loads(Path(baseline).read_text()) if baseline else None
    report = {"version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "maya": cmds.about(version=True), "scene": cmds.file(query=True, sceneName=True),
              "root": root, "units": cmds.currentUnit(query=True, linear=True),
              "measurement": "Control-pose manipulation plus CPU geometry snapshot and validation overhead; excludes viewport drawing. Cached Playback disabled.",
              "missing_channels": missing, "skipped_channels": skipped, "poses": [], "timings": {}}
    active = [case for case in resolved if case["active"]]
    if not active:
        raise ValueError("The pose bank has no applicable cases.")
    initial = {p: cmds.getAttr(p) for p in (resolved[0]["values"] if resolved else {})}
    from maya_tools.scripts.tools import rig_roles
    mesh_keys = {m: next((b['key'] for b in rig_roles.bindings(root) if b['node'] == m and b['kind'] == 'mesh'), m) for m in meshes}
    report['mesh_nodes'] = {v: k for k, v in mesh_keys.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with _session(), poses._temporary_values(initial):
        reference = {}
        for mode in modes:
            cmds.evaluationManager(mode=mode)
            samples = []
            mode_errors = []
            for iteration in range(repeats + 1):
                for case in active:
                    start = time.perf_counter()
                    for plug, value in case["values"].items():
                        cmds.setAttr(plug, value)
                    data = {mesh: mesh_data(mesh) for mesh in meshes}
                    elapsed = (time.perf_counter() - start) * 1000
                    if iteration:
                        samples.append(elapsed)
                    if iteration == 0:
                        if case["name"] not in reference:
                            reference[case["name"]] = data
                            pose = {"name": case["name"], "channels": case["values"], "meshes": {mesh_keys[m]: d for m,d in data.items()},
                                    "missing": case["missing"], "capture": None}
                            if 'definition' in case:
                                pose['definition'] = case['definition']
                            if isinstance(cases, dict):
                                from maya_tools.scripts.tools import rig_profiles
                                pose['checks'] = rig_profiles.checks(root, cases, case['name'])
                            if isinstance(cases, dict) and cases.get('contacts'):
                                from maya_tools.scripts.tools import rig_surface_contact
                                pose['contacts'] = rig_surface_contact.profile_contacts(root, cases)
                            if captures and not cmds.about(batch=True):
                                image = output.with_name(output.stem + "_" + case["name"] + ".png")
                                if image.exists():
                                    raise ValueError("Capture already exists: " + str(image))
                                try:
                                    camera = (cameras or {}).get(case['name'])
                                    if camera:
                                        from maya_tools.scripts.tools import rig_pose_library
                                        pose['capture'] = rig_pose_library.capture_image(image, camera)
                                        pose['camera'] = camera
                                    else:
                                        pose["capture"] = cmds.playblast(format="image", completeFilename=str(image),
                                            frame=cmds.currentTime(query=True), viewer=False, showOrnaments=False,
                                            compression="png", widthHeight=(960, 720), percent=100)
                                except (RuntimeError, ValueError) as exc:
                                    pose["capture_error"] = str(exc)
                            report["poses"].append(pose)
                        else:
                            previous = reference[case["name"]]
                            if any(data[m]["topology"] != previous[m]["topology"] for m in meshes):
                                raise ValueError("Evaluated topology differs between evaluation modes.")
                            max_error = max((math.sqrt(sum((a-b)**2 for a,b in zip(p,q)))
                                for mesh in meshes for p,q in zip(data[mesh]["points"],previous[mesh]["points"])), default=0)
                            mode_errors.append({"pose": case["name"], "max": max_error})
            ordered = sorted(samples)
            report["timings"][mode] = {"mean_ms": statistics.mean(samples),
                "p95_ms": ordered[max(0, math.ceil(len(ordered) * .95) - 1)], "samples": len(samples),
                "geometry_difference": mode_errors}
        report["deformers"] = audit_deformers(meshes)
    if old_report:
        report["comparison"] = compare_reports(report, old_report)
    if isinstance(cases, dict):
        from maya_tools.scripts.tools import rig_profiles
        report['profile'] = cases
        report['transitions'] = rig_profiles.transitions(root, meshes, cases, sides)
        tolerance = cases.get('comparison_tolerance', 1e-4)
        report['quality_pass'] = not missing and not skipped and all(t['pass'] for t in report['transitions']) and all(
            c['status'] == 'compared' and c['max'] <= tolerance for c in report.get('comparison', [])) and all(
            e['max'] <= tolerance for mode in report['timings'].values() for e in mode['geometry_difference']) and all(
            c['pass'] for p in report['poses'] for c in p.get('contacts', []))
        report['quality_pass'] = report['quality_pass'] and all(c['pass'] for p in report['poses'] for c in p.get('checks',[]))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, separators=(",", ":"), allow_nan=False)
    return report
