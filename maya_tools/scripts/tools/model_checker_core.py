"""Read-only modeling QC, structured reports and explicit, undoable repairs.

Checklist GPU counts are advisory values from the supplied document, not a
claim about the eligibility of a particular Maya deformer or graphics card.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import product
import hashlib
import math
import re

from maya import cmds
import maya.api.OpenMaya as om


class SkipCheck(Exception):
    """The check is not applicable to this scope."""


@dataclass
class Options:
    tolerance: float = 0.001
    ground_tolerance: float = 0.5
    gpu_min_vertices: int = 2000


@dataclass
class Issue:
    label: str
    selection: list = field(default_factory=list)


@dataclass
class Result:
    id: str
    status: str = "NOT RUN"
    issues: list = field(default_factory=list)
    message: str = ""


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    severity: str
    category: str
    tip: str
    scene_only: bool = False


CHECKS = (
    Check("ngons", "N-gons", "MUST", "Geometry", "No n-gons on meshes intended for non-rigid deformation."),
    Check("tris", "Triangles", "SHOULD", "Geometry", "Review triangles in heavily deformed areas; rigid parts may be acceptable."),
    Check("nonmanifold", "Non-manifold geometry", "MUST", "Geometry", "Select and repair non-manifold vertices and edges manually."),
    Check("lamina", "Lamina faces", "MUST", "Geometry", "Duplicate faces sharing all vertices can prevent mesh operations."),
    Check("zeroarea", "Zero-area faces", "MUST", "Geometry", "World-space face area below the squared position tolerance."),
    Check("overlap", "Overlapping vertices", "SHOULD", "Geometry", "Vertices within the position tolerance. Review intentional seams before merging."),
    Check("tweaks", "Vertex local transforms", "MUST", "Geometry", "Nonzero mesh point offsets and sparse tweak-node offsets; do not zero them blindly."),
    Check("history", "Construction / deformation history", "MUST", "Scene", "History is a blocker for pre-rig delivery unless explicitly requested."),
    Check("frozen", "Frozen transforms (including groups)", "MUST", "Scene", "All scoped transforms should have identity translate, rotate and scale."),
    Check("pivots", "Pivots at world origin", "SHOULD", "Scene", "Rotate and scale pivots are measured in world space."),
    Check("dupenames", "Duplicate DAG names", "MUST", "Scene", "Compare against the whole DAG; report scoped nodes using unambiguous full paths."),
    Check("multishapes", "Single output shape per transform", "MUST", "Scene", "Ignore intermediate shapes used by Maya's construction and deformation history."),
    Check("meshparent", "Meshes parented under meshes", "MUST", "Scene", "A mesh transform must not have another mesh transform as an ancestor."),
    Check("emptygroups", "Empty transform groups", "SHOULD", "Scene", "Empty transforms are candidates for cleanup; inspect their purpose before removal."),
    Check("unusedshaders", "Unused shading engines", "SHOULD", "Scene", "Scene-wide only. Default Maya shading engines are excluded.", True),
    Check("unusedtex", "Unused file textures", "SHOULD", "Scene", "Scene-wide only. File nodes without outgoing connections.", True),
    Check("pastednodes", "Pasted node names", "MUST", "Scene", "Names containing pasted__ should be reviewed and renamed."),
    Check("namespaces", "Delivery namespaces", "MUST", "Scene", "Scene-wide only. Pipeline or reference namespaces may be accepted as an exception.", True),
    Check("t_illegal", "Deformers and extra cameras", "MUST", "Scene", "Pre-rig delivery candidates; intentional deformers and cameras need a documented exception."),
    Check("t_ground", "Ground contact", "SHOULD", "Model design", "Combined bounding box on Maya's current up axis, in scene units."),
    Check("t_symmetry", "Positional symmetry across world X", "SHOULD", "Model design", "Compare reflected positions within tolerance on meshes crossing X=0. Does not validate edge connectivity."),
    Check("t_poles", "Interior pole candidates", "INFO", "Model design", "Interior vertices with valence other than four. Only poles in deforming regions need correction."),
    Check("gpu", "Small meshes (checklist GPU guidance)", "INFO", "Model design", "Checklist guidance: 2000 vertices for NVIDIA, 500 for AMD. This is not a runtime GPU eligibility test."),
)
BY_ID = {check.id: check for check in CHECKS}

# States are explicit: an unchecked row is pending, never an implicit pass.
MANUAL_CHECKS = (
    ("feet_z", "Pose & alignment", "SHOULD", "Feet tips point along positive Z"),
    ("knees_z", "Pose & alignment", "SHOULD", "Knees point along positive Z"),
    ("legs_parallel", "Pose & alignment", "SHOULD", "Left and right legs are parallel"),
    ("sole_topo", "Body topology", "MUST", "Sole and shoe have matching topology"),
    ("foot_loops", "Body topology", "MUST", "Foot / shoe loops are parallel to the ground"),
    ("elbow_cloth", "Body topology", "MUST", "Body and clothing elbows align"),
    ("cloth_topo", "Body topology", "SHOULD", "Clothing appendages follow the body topology"),
    ("fold_loops", "Body topology", "MUST", "Straight loops at knuckles, elbows and finger folds"),
    ("knuckle_style", "Body topology", "SHOULD", "Consistent knuckle topology"),
    ("finger_topo", "Body topology", "SHOULD", "Index, middle, ring and pinky share topology"),
    ("deform_poles", "Body topology", "SHOULD", "Pole candidates are clear of heavily deformed areas"),
    ("lips_match", "Face", "MUST", "Upper / lower lip vertex count and placement match"),
    ("eyelids_match", "Face", "MUST", "Upper / lower eyelid vertex count and placement match"),
    ("neutralized", "Face", "SHOULD", "Lips, eyelids and brows have a neutral expression"),
    ("lips_loop", "Face", "MUST", "Continuous sealing loop through the lip contact line"),
    ("eyelids_loop", "Face", "MUST", "Continuous sealing loop through the eyelid contact line"),
    ("inner_lips", "Face", "SHOULD", "Inner lip loops run parallel to outer lip loops"),
    ("commissures", "Face", "INFO", "Jaw-open inspection of lip corners and thickness"),
    ("lip_intersect", "Face", "INFO", "Lip intersections are limited and suitable for rendering"),
    ("lip_bumps", "Face", "INFO", "No unwanted bumps on lips"),
    ("cornea_bulge", "Eyes", "SHOULD", "Corneal eye bulge is left for rigging"),
    ("cornea_topo", "Eyes", "SHOULD", "Cornea and eyeball loops align (counts may differ)"),
    ("eyebrow_topo", "Eyes", "SHOULD", "Eyebrow topology follows the body"),
    ("eyelashes_topo", "Eyes", "SHOULD", "Eyelashes follow the underlying topology"),
)
REVIEW_STATES = ("Pending", "Pass", "Fail", "N/A")


def selection_roots():
    nodes = cmds.ls(selection=True, objectsOnly=True, long=True) or []
    return list(dict.fromkeys(node for node in nodes if cmds.objectType(node, isAType="dagNode")))


class Context:
    def __init__(self, roots=None, options=None):
        self.options = options or Options()
        if not math.isfinite(self.options.tolerance) or self.options.tolerance <= 0:
            raise ValueError("Position tolerance must be finite and greater than zero.")
        if not math.isfinite(self.options.ground_tolerance) or self.options.ground_tolerance < 0:
            raise ValueError("Ground tolerance must be finite and nonnegative.")
        if self.options.gpu_min_vertices < 1:
            raise ValueError("The vertex advisory threshold must be greater than zero.")
        self.roots = None if roots is None else list(roots)
        if self.roots is not None:
            if not self.roots:
                raise ValueError("Load one or more mesh / group roots from the Maya selection.")
            missing = [node for node in self.roots if not cmds.objExists(node)]
            if missing:
                raise ValueError("Scope no longer exists: " + ", ".join(missing))
        args = [] if self.roots is None else [self.roots]
        self.meshes = sorted(set(cmds.ls(*args, dag=True, type="mesh", long=True,
                                       noIntermediate=True, allPaths=True) or []))
        if not self.meshes:
            raise ValueError("No non-intermediate polygon meshes in this scope.")
        self.transforms = set(cmds.ls(*args, dag=True, type="transform", long=True) or [])
        # A selected shape must include its owner for transform checks.
        self.transforms.update(parent(mesh) for mesh in self.meshes)
        defaults = set()
        for camera in cmds.ls(type="camera", long=True) or []:
            if cmds.camera(camera, query=True, startupCamera=True):
                defaults.add(parent(camera))
        self.transforms = sorted(self.transforms - defaults)
        self._functions = {}

    def fn(self, mesh):
        if mesh not in self._functions:
            selection = om.MSelectionList()
            selection.add(mesh)
            self._functions[mesh] = om.MFnMesh(selection.getDagPath(0))
        return self._functions[mesh]


def parent(node):
    return (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]


def components(mesh, kind, indices):
    return ["{}.{}[{}]".format(mesh, kind, index) for index in indices]


def mesh_issue(mesh, indices, kind, label):
    return Issue("{}: {} {}".format(parent(mesh).split("|")[-1], len(indices), label),
                 components(mesh, kind, indices))


def history(mesh):
    return [node for node in (cmds.listHistory(mesh, pruneDagObjects=True) or [])
            if cmds.nodeType(node) != "mesh"]


def _cells(point, tolerance):
    return tuple(math.floor(value / tolerance) for value in point[:3])


def nearby_indices(points, targets, tolerance):
    """Find all source vertices within tolerance of a target, using spatial bins."""
    bins = {}
    for index, point in enumerate(targets):
        bins.setdefault(_cells(point, tolerance), []).append(index)
    tolerance2 = tolerance * tolerance
    result = []
    for index, point in enumerate(points):
        cell = _cells(point, tolerance)
        found = False
        for offset in product((-1, 0, 1), repeat=3):
            key = tuple(cell[axis] + offset[axis] for axis in range(3))
            if any(sum((point[a] - targets[j][a]) ** 2 for a in range(3)) <= tolerance2
                   for j in bins.get(key, ())):
                found = True
                break
        if not found:
            result.append(index)
    return result


def _mesh_check(context, check_id):
    issues = []
    for mesh in context.meshes:
        fn = context.fn(mesh)
        indices, kind, label = [], "vtx", "vertices"
        if check_id in ("ngons", "tris"):
            counts, _ = fn.getVertices()
            indices = [i for i, count in enumerate(counts)
                       if (count > 4 if check_id == "ngons" else count == 3)]
            kind, label = "f", check_id
        elif check_id == "nonmanifold":
            lines = (cmds.polyInfo(mesh, nonManifoldVertices=True) or []) + (cmds.polyInfo(mesh, nonManifoldEdges=True) or [])
            targets = sorted(set(mesh + suffix for line in lines
                                 for suffix in re.findall(r"\.(?:vtx|e)\[\d+(?::\d+)?\]", line)))
            if targets:
                issues.append(Issue(parent(mesh).split("|")[-1] + ": non-manifold components", targets))
            continue
        elif check_id in ("lamina", "zeroarea"):
            iterator = om.MItMeshPolygon(fn.dagPath())
            while not iterator.isDone():
                bad = iterator.isLamina() if check_id == "lamina" else iterator.getArea(om.MSpace.kWorld) <= context.options.tolerance ** 2
                if bad:
                    indices.append(iterator.index())
                iterator.next()
            kind, label = "f", "lamina faces" if check_id == "lamina" else "zero-area faces"
        elif check_id == "overlap":
            points = [tuple(p)[:3] for p in fn.getPoints(om.MSpace.kWorld)]
            bins, overlap = {}, set()
            tolerance = context.options.tolerance
            for i, point in enumerate(points):
                cell = _cells(point, tolerance)
                for offset in product((-1, 0, 1), repeat=3):
                    key = tuple(cell[a] + offset[a] for a in range(3))
                    for j in bins.get(key, ()):
                        if sum((point[a] - points[j][a]) ** 2 for a in range(3)) <= tolerance ** 2:
                            overlap.update((i, j))
                bins.setdefault(cell, []).append(i)
            indices, label = sorted(overlap), "overlapping vertices"
        elif check_id == "tweaks":
            indices = set()
            plugs = [mesh + ".pnts"]
            plugs += [node + ".vlist[0].vertex" for node in (cmds.listConnections(mesh, type="tweak") or [])]
            for plug in plugs:
                for i in cmds.getAttr(plug, multiIndices=True) or []:
                    value = cmds.getAttr("{}[{}]".format(plug, i))
                    if value and any(abs(v) > context.options.tolerance for v in value[0]):
                        indices.add(i)
            indices, label = sorted(indices), "nonzero local offsets"
        elif check_id == "t_poles":
            iterator = om.MItMeshVertex(fn.dagPath())
            while not iterator.isDone():
                if not iterator.onBoundary() and iterator.numConnectedEdges() != 4:
                    indices.append(iterator.index())
                iterator.next()
            label = "pole candidates (review deforming regions)"
        elif check_id == "t_symmetry":
            points = [tuple(p)[:3] for p in fn.getPoints(om.MSpace.kWorld)]
            tol = context.options.tolerance
            if not (any(p[0] < -tol for p in points) and any(p[0] > tol for p in points)):
                continue
            reflected = [(-p[0], p[1], p[2]) for p in points]
            indices = nearby_indices(reflected, points, tol)
            label = "vertices without a mirrored position"
        elif check_id == "gpu":
            if fn.numVertices < context.options.gpu_min_vertices:
                issues.append(Issue("{}: {} vertices, below advisory {}".format(
                    parent(mesh).split("|")[-1], fn.numVertices, context.options.gpu_min_vertices), [mesh]))
            continue
        if indices:
            issues.append(mesh_issue(mesh, indices, kind, label))
    if check_id == "t_symmetry" and not any(
            cmds.exactWorldBoundingBox(mesh)[0] < -context.options.tolerance and
            cmds.exactWorldBoundingBox(mesh)[3] > context.options.tolerance for mesh in context.meshes):
        raise SkipCheck("No mesh crosses world X=0. Load the underlying body for symmetry review.")
    return issues


def inspect_check(context, check_id):
    if check_id in {"ngons", "tris", "nonmanifold", "lamina", "zeroarea", "overlap", "tweaks", "t_poles", "t_symmetry", "gpu"}:
        return _mesh_check(context, check_id)
    issues = []
    if check_id == "history":
        for mesh in context.meshes:
            nodes = history(mesh)
            if nodes:
                issues.append(Issue("{}: {} history nodes".format(parent(mesh), len(nodes)), [parent(mesh)]))
    elif check_id in ("frozen", "pivots", "multishapes", "emptygroups", "meshparent"):
        for node in context.transforms:
            bad = False
            if check_id == "frozen":
                values = [v for attr in ("translate", "rotate", "scale") for v in cmds.getAttr(node + "." + attr)[0]]
                bad = any(abs(a - b) > context.options.tolerance for a, b in zip(values, (0, 0, 0, 0, 0, 0, 1, 1, 1)))
            elif check_id == "pivots":
                values = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True) + cmds.xform(node, query=True, worldSpace=True, scalePivot=True)
                bad = any(abs(v) > context.options.tolerance for v in values)
            elif check_id == "multishapes":
                bad = len(cmds.listRelatives(node, shapes=True, noIntermediate=True) or []) > 1
            elif check_id == "emptygroups":
                bad = not cmds.listRelatives(node, children=True)
            elif cmds.listRelatives(node, shapes=True, noIntermediate=True, type="mesh"):
                ancestor = parent(node)
                while ancestor != node:
                    if cmds.listRelatives(ancestor, shapes=True, noIntermediate=True, type="mesh"):
                        bad = True
                        break
                    node_parent = parent(ancestor)
                    if node_parent == ancestor:
                        break
                    ancestor = node_parent
            if bad:
                issues.append(Issue(node, [node]))
    elif check_id == "dupenames":
        names = {}
        for node in cmds.ls(dag=True, long=True) or []:
            names.setdefault(node.split("|")[-1], []).append(node)
        scoped = set(context.transforms) | set(context.meshes)
        for name, nodes in names.items():
            relevant = nodes if context.roots is None else [node for node in nodes if node in scoped]
            if len(nodes) > 1 and relevant:
                issues.append(Issue("{}: {} DAG paths".format(name, len(nodes)), relevant))
    elif check_id == "unusedshaders":
        for node in cmds.ls(type="shadingEngine") or []:
            if node not in ("initialShadingGroup", "initialParticleSE") and not cmds.sets(node, query=True):
                issues.append(Issue(node, [node]))
    elif check_id == "unusedtex":
        issues = [Issue(node, [node]) for node in (cmds.ls(type="file") or [])
                  if not cmds.listConnections(node, source=False, destination=True)]
    elif check_id == "pastednodes":
        nodes = cmds.ls(long=True) if context.roots is None else context.transforms + context.meshes
        issues = [Issue(node, [node]) for node in nodes if "pasted__" in node.split("|")[-1]]
    elif check_id == "namespaces":
        for namespace in cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []:
            if namespace in ("UI", "shared"):
                continue
            nodes = cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True, dagPath=True) or []
            if nodes:
                issues.append(Issue("Namespace " + namespace, nodes))
    elif check_id == "t_illegal":
        nodes = set(cmds.ls(type="geometryFilter") or []) if context.roots is None else set(
            node for mesh in context.meshes for node in (cmds.ls(history(mesh), type="geometryFilter") or []))
        issues = [Issue("Deformer: " + node, [node]) for node in sorted(nodes)]
        for camera in cmds.ls(type="camera", long=True) or []:
            if not cmds.camera(camera, query=True, startupCamera=True) and (context.roots is None or parent(camera) in context.transforms):
                issues.append(Issue("Extra camera: " + parent(camera), [parent(camera)]))
    elif check_id == "t_ground":
        axis = 1 if cmds.upAxis(query=True, axis=True) == "y" else 2
        lowest = min(cmds.exactWorldBoundingBox(mesh)[axis] for mesh in context.meshes)
        if abs(lowest) > context.options.ground_tolerance:
            issues.append(Issue("Lowest point on {}: {:.5g} {}".format("XYZ"[axis], lowest,
                                cmds.currentUnit(query=True, linear=True)), list(context.meshes)))
    else:
        raise KeyError(check_id)
    return issues


def run_check(context, check_id):
    check = BY_ID[check_id]
    if check.scene_only and context.roots is not None:
        return Result(check_id, "SKIP", message="Scene-wide check; switch scope to Whole scene.")
    try:
        issues = inspect_check(context, check_id)
        status = ("INFO" if check.severity == "INFO" else "FAIL" if check.severity == "MUST" else "WARN") if issues else "PASS"
        return Result(check_id, status, issues)
    except SkipCheck as exc:
        return Result(check_id, "SKIP", message=str(exc))
    except Exception as exc:
        return Result(check_id, "ERROR", message=str(exc))


# Deliberately exclude geometry merges, deletion of deformers, namespace removal
# and zeroing vertex offsets. Those operations need an artist's topology review.
FIXABLE = {"history", "frozen", "pivots", "emptygroups", "unusedshaders", "unusedtex"}


def repair(check_id, issue):
    """One explicit repair, one Maya undo step. Refuse stale / protected input."""
    if check_id not in FIXABLE:
        raise ValueError("This finding requires manual repair.")
    if not cmds.undoInfo(query=True, state=True):
        raise ValueError("Enable Maya Undo before applying a repair.")
    if len(issue.selection) != 1 or not cmds.objExists(issue.selection[0]):
        raise ValueError("Finding is stale. Run checks again.")
    node = issue.selection[0]
    if cmds.referenceQuery(node, isNodeReferenced=True) or any(cmds.lockNode(node, query=True, lock=True) or []):
        raise ValueError("Referenced or locked node; repair is unavailable.")
    if check_id in ("history", "frozen", "pivots"):
        meshes = cmds.ls(node, dag=True, type="mesh", noIntermediate=True, long=True) or []
        histories = set(cmds.listHistory(node) or [])
        for mesh in meshes:
            histories.update(cmds.listHistory(mesh) or [])
        if histories and cmds.ls(list(histories), type="geometryFilter"):
            raise ValueError("Live deformers found. Repair manually to preserve the rig.")
        if check_id in ("history", "frozen") and cmds.listRelatives(node, children=True, type="transform"):
            raise ValueError("Transform has child transforms. Repair this hierarchy manually.")
        for attr in ("translate", "rotate", "scale", "rotatePivot", "scalePivot"):
            plug = node + "." + attr
            if cmds.getAttr(plug, lock=True) or cmds.listConnections(plug, source=True, destination=False):
                raise ValueError("Transform is locked or driven: " + plug)
            for axis in "XYZ":
                if cmds.getAttr(plug + axis, lock=True):
                    raise ValueError("Transform channel is locked: " + plug + axis)
    if check_id == "emptygroups" and (cmds.nodeType(node) != "transform" or cmds.listRelatives(node, children=True) or cmds.listConnections(node)):
        raise ValueError("Group now has children / connections or is not a plain transform.")
    if check_id == "unusedshaders" and (node in ("initialShadingGroup", "initialParticleSE") or cmds.sets(node, query=True)):
        raise ValueError("Shading engine is now used or protected.")
    if check_id == "unusedtex" and cmds.listConnections(node, source=False, destination=True):
        raise ValueError("Texture is now connected.")
    cmds.undoInfo(openChunk=True, chunkName="Model Checker: " + check_id)
    try:
        if check_id == "history":
            cmds.delete(node, constructionHistory=True)
        elif check_id == "frozen":
            cmds.makeIdentity(node, apply=True, translate=True, rotate=True, scale=True)
        elif check_id == "pivots":
            cmds.xform(node, worldSpace=True, pivots=(0, 0, 0))
        else:
            cmds.delete(node)
    finally:
        cmds.undoInfo(closeChunk=True)
    return "Applied {} to {}. Run checks to verify.".format(check_id, node)


def mesh_identity():
    identifiers = []
    for mesh in cmds.ls(type="mesh", long=True) or []:
        selection = om.MSelectionList()
        selection.add(mesh)
        identifiers.append(om.MFnDependencyNode(selection.getDependNode(0)).uuid().asString())
    return hashlib.sha256("|".join(sorted(identifiers)).encode("utf-8")).hexdigest()


def build_report(results, manual, roots, options, stale=False):
    automatic = []
    for check in CHECKS:
        result = results.get(check.id, Result(check.id))
        automatic.append(dict(asdict(result), label=check.label, severity=check.severity,
                              category=check.category, guidance=check.tip))
    reviews = [dict(id=key, category=category, severity=severity, label=label,
                    state=manual.get(key, {}).get("state", "Pending"),
                    note=manual.get(key, {}).get("note", ""))
               for key, category, severity, label in MANUAL_CHECKS]
    blockers = sum(row["severity"] == "MUST" and row["status"] == "FAIL" for row in automatic)
    blockers += sum(row["severity"] == "MUST" and row["state"] == "Fail" for row in reviews)
    errors = sum(row["status"] == "ERROR" for row in automatic)
    pending = sum(row["state"] == "Pending" or (row["state"] == "N/A" and not row["note"].strip()) for row in reviews)
    not_run = sum(row["status"] == "NOT RUN" for row in automatic)
    skipped = sum(row["status"] == "SKIP" for row in automatic)
    warnings = sum(row["status"] == "WARN" for row in automatic) + sum(row["severity"] != "MUST" and row["state"] == "Fail" for row in reviews)
    verdict = "STALE" if stale else "BLOCKED" if blockers else "INCOMPLETE" if errors or pending or not_run or skipped else "REVIEW WARNINGS" if warnings else "PASS"
    return dict(schema_version=1, source="Modeling QC Checklist", generated_at=datetime.now(timezone.utc).isoformat(),
                scene=cmds.file(query=True, sceneName=True) or "Untitled", units=cmds.currentUnit(query=True, linear=True),
                mesh_identity=mesh_identity(),
                up_axis=cmds.upAxis(query=True, axis=True), scope="Whole scene" if roots is None else list(roots),
                options=asdict(options), stale=stale, verdict=verdict,
                summary=dict(blockers=blockers, warnings=warnings, errors=errors, pending=pending, not_run=not_run, skipped=skipped),
                automatic=automatic, manual=reviews)


def report_text(report):
    lines = ["MODEL CHECKER - " + report["verdict"], "Scene: " + report["scene"],
             "Scope: " + str(report["scope"]), "Generated: " + report["generated_at"],
             "Source: Modeling QC Checklist", "Options: " + str(report["options"]),
             "Units: {} / up axis: {}".format(report["units"], report["up_axis"]), "", "AUTOMATIC CHECKS"]
    for row in report["automatic"]:
        lines.append("[{}] [{}] {}{}".format(row["severity"], row["status"], row["label"], ": " + row["message"] if row["message"] else ""))
        for issue in row["issues"]:
            lines.append("  " + issue["label"])
            lines.extend("    " + target for target in issue["selection"])
    lines += ["", "VISUAL REVIEW"]
    lines += ["[{}] [{}] {}{}".format(row["severity"], row["state"], row["label"], ": " + row["note"] if row["note"] else "") for row in report["manual"]]
    return "\n".join(lines)


def compare_vertex_sets(first, second, tolerance=0.001):
    """Inspect explicitly loaded lip / eyelid or body / clothing vertex sets.

    Equal counts alone never imply a valid sealing loop or matching topology.
    The distance measure is bidirectional nearest position, not vertex order.
    """
    if not first or not second:
        raise ValueError("Load both vertex sets.")
    for node in first + second:
        if ".vtx[" not in node or not cmds.objExists(node):
            raise ValueError("Vertex set is stale or invalid: " + node)
    points_a = [cmds.pointPosition(node, world=True) for node in first]
    points_b = [cmds.pointPosition(node, world=True) for node in second]
    unmatched = [first[i] for i in nearby_indices(points_a, points_b, tolerance)]
    unmatched += [second[i] for i in nearby_indices(points_b, points_a, tolerance)]
    return dict(count_a=len(first), count_b=len(second), equal_count=len(first) == len(second),
                unmatched=unmatched, tolerance=tolerance)
