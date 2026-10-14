"""Character-independent wrinkle regions, local controls and portable presets."""
from collections import deque
import copy
import json
import math
from pathlib import Path

from maya import cmds
from maya.api import OpenMaya as om

from maya_tools.scripts.tools import bifrost_wrinkles as wrinkles
from maya_tools.scripts.tools import pose_blendshapes as poses
from maya_tools.scripts.tools import rig_validation


def setup_record(settings):
    records = wrinkles.export_setups()
    return next((r for r in records if cmds.ls(r["prefix"] + "_Settings", long=True) == cmds.ls(settings, long=True)), None)


def _source(settings):
    source = cmds.connectionInfo(settings + ".sourceMesh", sourceFromDestination=True).split(".")[0]
    return wrinkles._mesh_fn(source)


def _rest_geometry(mesh):
    transform = poses.mesh_transform(mesh)
    root = "|" + transform.split("|")[1]
    values, skipped = rig_validation._neutral_values(root)
    with poses._temporary_values(values):
        shape, path, fn = wrinkles._mesh_fn(transform)
        points = [[p.x, p.y, p.z] for p in fn.getPoints(om.MSpace.kObject)]
        counts, indices = fn.getVertices()
    return {"points": points, "polygon_counts": list(counts), "polygon_connects": list(indices)}


@poses.undoable
def create(mesh, prefix="CharacterWrinkles", hide_source=False):
    """Empty portable setup; the artist assigns regions from selected vertices."""
    geometry = _rest_geometry(mesh)
    values, _ = rig_validation._neutral_values("|" + poses.mesh_transform(mesh).split("|")[1])
    with poses._temporary_values(values):
        return wrinkles.build(mesh, prefix, {r: [0.] * len(geometry["points"]) for r in wrinkles.REGIONS},
                              hide_source=hide_source)


@poses.undoable
def set_patterns(settings, patterns):
    shape, path, fn = _source(settings)
    record = setup_record(settings)
    if not record:
        raise ValueError("Choose a valid wrinkle setup.")
    graph = record["prefix"] + "GraphShape"
    for region, values in patterns.items():
        if region not in wrinkles.REGIONS or len(values) != fn.numVertices:
            raise ValueError("Region arrays must match the source topology.")
        if any(not math.isfinite(v) or abs(v) > 1 for v in values):
            raise ValueError("Flow values must be finite and inside [-1, 1].")
    for region, values in patterns.items():
        for start in range(0, len(values), 2048):
            batch = [float(v) + 2 for v in values[start:start+2048]]
            cmds.setAttr("%s.%sFlowEncoded[%d:%d]" % (graph, region, start, start+len(batch)-1),
                         *batch, size=len(batch))


def selected_vertices(mesh):
    mesh = poses.mesh_transform(mesh)
    result = []
    for vertex in cmds.filterExpand(cmds.ls(selection=True, flatten=True, long=True), selectionMask=31) or []:
        if poses.mesh_transform(vertex.split(".vtx[")[0]) == mesh:
            result.append(int(vertex.split(".vtx[")[1].rstrip("]")))
    if not result:
        raise ValueError("Select vertices on the wrinkle source mesh.")
    return sorted(set(result))


def region_pattern(mesh, vertices, angle=0, wavelength=1., feather_rings=2, plane="XY"):
    """Signed fold field with selected-vertex support and smooth boundary taper."""
    if plane not in ("XY", "XZ", "YZ") or wavelength <= 0 or not math.isfinite(wavelength) or not math.isfinite(angle):
        raise ValueError("Choose a projection plane, finite angle and positive wavelength.")
    if feather_rings < 0:
        raise ValueError("Feather rings cannot be negative.")
    shape, path, fn = wrinkles._mesh_fn(mesh)
    vertex_count = fn.numVertices
    vertices = set(int(i) for i in vertices)
    if not vertices or min(vertices) < 0 or max(vertices) >= vertex_count:
        raise ValueError("Choose valid source vertices.")
    geometry = _rest_geometry(mesh)
    adjacency = {}
    iterator = om.MItMeshVertex(path)
    while not iterator.isDone():
        adjacency[iterator.index()] = list(iterator.getConnectedVertices()); iterator.next()
    boundary = [i for i in vertices if any(n not in vertices for n in adjacency[i])]
    distances = {i: 0 for i in boundary}
    queue = deque(boundary)
    while queue:
        i = queue.popleft()
        for j in adjacency[i]:
            if j in vertices and j not in distances:
                distances[j] = distances[i] + 1; queue.append(j)
    axes = ["XYZ".index(a) for a in plane]
    center = [sum(geometry["points"][i][a] for i in vertices) / len(vertices) for a in axes]
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    result = [0.] * vertex_count
    for i in vertices:
        u = geometry["points"][i][axes[0]] - center[0]
        v = geometry["points"][i][axes[1]] - center[1]
        feather = min(1., (distances.get(i, feather_rings) + 1.) / (feather_rings + 1.))
        feather = feather * feather * (3 - 2 * feather)
        result[i] = feather * math.cos(2 * math.pi * (u*c + v*s) / wavelength)
    return result


@poses.undoable
def assign_region(settings, region, vertices, angle=0, wavelength=1., feather_rings=2, plane="XY"):
    source = _source(settings)[0]
    pattern = region_pattern(source, vertices, angle, wavelength, feather_rings, plane)
    set_patterns(settings, {region: pattern})
    return pattern


def _resolve_control(name, mesh):
    root = "|" + poses.mesh_transform(mesh).split("|")[1]
    leaf = name.rsplit("|", 1)[-1].split(":")[-1]
    matches = [c for c in rig_validation._controls(root) if c.rsplit("|", 1)[-1].split(":")[-1] == leaf]
    return matches[0] if len(matches) == 1 else None


@poses.undoable
def assign_controls(settings, region, controllers, radius=None):
    """Partition a region between selected controls, independent of asset scale."""
    record = setup_record(settings)
    if not record or region not in wrinkles.REGIONS:
        raise ValueError("Choose a wrinkle setup and region.")
    shape, path, fn = _source(settings)
    controllers = list(dict.fromkeys(orientation_transform(c) for c in controllers))
    if not controllers:
        raise ValueError("Select at least one controller.")
    points = _rest_geometry(shape)["points"]
    inverse = path.inclusiveMatrixInverse()
    neutral, _ = rig_validation._neutral_values("|" + poses.mesh_transform(shape).split("|")[1])
    with poses._temporary_values(neutral):
        inverse = path.inclusiveMatrixInverse()
        centers = [om.MPoint(*cmds.xform(c, query=True, worldSpace=True, translation=True)) * inverse for c in controllers]
    if radius is None:
        spans = [max(p[a] for p in points) - min(p[a] for p in points) for a in range(3)]
        radius = max(max(spans) * .15, 1e-5)
    if radius <= 0 or not math.isfinite(radius):
        raise ValueError("Controller falloff radius must be positive and finite.")
    masks = [[] for c in controllers]
    for point in points:
        distances = [(om.MPoint(*point) - c).length() ** 2 for c in centers]
        minimum = min(distances)
        weights = [math.exp(-(d-minimum)/(radius*radius)) for d in distances]
        total = sum(weights)
        for array, weight in zip(masks, weights): array.append(weight/total)
    fields = []
    for field in record.get("controls", []):
        field = copy.deepcopy(field); field["masks"].pop(region, None)
        if field["masks"]: fields.append(field)
    by_control = {f["controller"]: f for f in fields}
    for control, mask in zip(controllers, masks):
        field = by_control.get(control)
        if field is None:
            field = {"controller": control, "masks": {}}; fields.append(field)
        field["masks"][region] = mask
    record["controls"] = fields
    source_transform = poses.mesh_transform(shape)
    visible = cmds.getAttr(source_transform + ".visibility")
    result = wrinkles.import_setups([record], replace_existing=True)[0]
    cmds.setAttr(source_transform + ".visibility", visible)
    return result


def orientation_transform(node):
    from maya_tools.scripts.tools import orientation_correctives
    return orientation_correctives._transform(node)


def export_preset(settings, output):
    record = setup_record(settings)
    if not record:
        raise ValueError("Choose a wrinkle setup.")
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a new preset version.")
    preset = {"version": 1, "setup": record, "geometry": _rest_geometry(record["source"]),
              "source_uuid": cmds.ls(record["source"], uuid=True)[0]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(preset, stream, separators=(",", ":"), allow_nan=False)
    return str(output)


def _project(preset, target_geometry):
    """Normalize bounds for surface transfer, then interpolate signed fields."""
    source = preset["geometry"]
    bounds = [(min(p[a] for p in source["points"]), max(p[a] for p in source["points"])) for a in range(3)]
    target_bounds = [(min(p[a] for p in target_geometry["points"]), max(p[a] for p in target_geometry["points"])) for a in range(3)]
    queries = []
    for p in target_geometry["points"]:
        values = []
        for a in range(3):
            lo, hi = target_bounds[a]; s_lo, s_hi = bounds[a]
            t = (p[a]-lo)/(hi-lo) if hi-lo > 1e-8 else .5
            values.append(s_lo + t*(s_hi-s_lo))
        queries.append(om.MPoint(*values))
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    mapping = SkinManager.__new__(SkinManager)._closest_surface_map(source, queries)
    def sample(values):
        return [sum(values[i]*weight for i,weight in samples) for samples in mapping]
    return sample


@poses.undoable
def apply_preset(input_path, mesh, prefix=None, replace_existing=False, remap_topology=False, include_controls=True):
    preset = json.loads(Path(input_path).read_text())
    if preset.get("version") != 1:
        raise ValueError("Unsupported wrinkle preset version.")
    record = copy.deepcopy(preset["setup"])
    shape, path, fn = wrinkles._mesh_fn(mesh)
    vertex_count = fn.numVertices
    same = record["topology"] == wrinkles._topology(fn) and record["vertices"] == vertex_count
    geometry = _rest_geometry(mesh)
    if not same and not remap_topology:
        raise ValueError("Topology differs. Enable region projection to adapt the preset.")
    if not same:
        sample = _project(preset, geometry)
        record["patterns"] = {r: [max(-1., min(1., v)) for v in sample(values)] for r,values in record["patterns"].items()}
        for field in record.get("controls", []):
            field["masks"] = {r: [max(0., min(1., v)) for v in sample(values)] for r,values in field["masks"].items()}
    fields, missing = [], []
    if include_controls:
        for field in record.get("controls", []):
            resolved = _resolve_control(field["controller"], mesh)
            if not resolved:
                missing.append(field["controller"]); continue
            field["controller"] = resolved; fields.append(field)
        # Re-normalize when some template controls are absent on this rig.
        for region in wrinkles.REGIONS if missing else ():
            relevant = [f for f in fields if region in f["masks"]]
            for i in range(vertex_count):
                total = sum(f["masks"][region][i] for f in relevant)
                if total > 1e-8:
                    for f in relevant: f["masks"][region][i] /= total
    prefix = prefix or poses.mesh_transform(mesh).rsplit("|",1)[-1].replace(":", "_") + "Wrinkles"
    if cmds.objExists(prefix + "_GRP") and not replace_existing:
        raise ValueError("Wrinkle setup already exists; enable replacement explicitly.")
    # Preserve calibrated rest fields for the identical mesh; variants must
    # measure their own neutral edge lengths instead of inheriting compression.
    same_source = (cmds.ls(poses.mesh_transform(mesh), uuid=True) or [None])[0] == preset.get("source_uuid")
    identical = same and (same_source or (len(geometry["points"]) == len(preset["geometry"]["points"]) and max(
        abs(a-b) for p,q in zip(geometry["points"],preset["geometry"]["points"]) for a,b in zip(p,q)) < 1e-6
        ))
    values, _ = rig_validation._neutral_values("|" + poses.mesh_transform(mesh).split("|")[1])
    source_transform = poses.mesh_transform(mesh)
    visible = cmds.getAttr(source_transform + ".visibility")
    with poses._temporary_values(values):
        if cmds.objExists(prefix + "_GRP"):
            cmds.delete(prefix + "_GRP")
        if cmds.objExists(prefix + "_ToMaya"):
            cmds.delete(prefix + "_ToMaya")
        result = wrinkles.build(mesh, prefix, patterns=record["patterns"],
            rest_data=record["rest"] if identical else None, control_fields=fields,
            hide_source=False)
        for attr, value in record["settings"].items():
            cmds.setAttr(result["settings"] + "." + attr, value)
        cmds.addAttr(result["settings"], longName="wrinklePreset", dataType="string")
        cmds.setAttr(result["settings"] + ".wrinklePreset", str(Path(input_path).resolve()), type="string")
        cmds.setAttr(result["output"] + ".visibility", record.get("visible", True))
    cmds.setAttr(source_transform + ".visibility", visible)
    result["missing_controls"] = missing
    result["projected"] = not same
    return result
