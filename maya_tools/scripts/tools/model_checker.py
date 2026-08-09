"""
Minimo Model Checker
Based on Modeling QC Standards (Roure Osso, 24/01/2023)

Usage (Maya Script Editor):
    from tools.model_checker import show
    show()
"""

import maya.cmds as cmds
import maya.OpenMaya as om

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Qt
    from shiboken2 import wrapInstance
    import maya.OpenMayaUI as omui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Qt
    from shiboken6 import wrapInstance
    import maya.OpenMayaUI as omui

from utils import ui_utils


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_meshes():
    return cmds.ls(type='mesh', long=True) or []


def _short_name(full_path):
    parent = cmds.listRelatives(full_path, parent=True, fullPath=True) or []
    node = parent[0] if parent else full_path
    return node.split('|')[-1]


def _mesh_fn(mesh):
    sel = om.MSelectionList()
    sel.add(mesh)
    dag = om.MDagPath()
    sel.getDagPath(0, dag)
    return om.MFnMesh(dag)


# ── Auto Check Functions ──────────────────────────────────────────────────────
# Each function returns a list of (label, [selectable_components]) tuples.

def check_ngons():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        counts, _ = om.MIntArray(), om.MIntArray()
        fn.getVertices(counts, _)
        idx = [i for i, c in enumerate(counts) if c > 4]
        if idx:
            t = _short_name(mesh)
            issues.append((f"{t}: {len(idx)} n-gon(s)", [f"{t}.f[{i}]" for i in idx]))
    return issues


def check_tris():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        counts, _ = om.MIntArray(), om.MIntArray()
        fn.getVertices(counts, _)
        idx = [i for i, c in enumerate(counts) if c == 3]
        if idx:
            t = _short_name(mesh)
            issues.append((f"{t}: {len(idx)} tri(s)", [f"{t}.f[{i}]" for i in idx]))
    return issues


def check_nonmanifold():
    issues = []
    for mesh in _get_meshes():
        t = _short_name(mesh)
        nm_v = cmds.polyInfo(mesh, nmv=True) or []
        nm_e = cmds.polyInfo(mesh, nme=True) or []
        sel = []
        for info in nm_v:
            parts = info.strip().split()
            sel.append(f"{t}.vtx[{parts[2].rstrip(':')}]")
        for info in nm_e:
            parts = info.strip().split()
            sel.append(f"{t}.e[{parts[2].rstrip(':')}]")
        if sel:
            issues.append((f"{t}: {len(nm_v)} nm-vert(s), {len(nm_e)} nm-edge(s)", sel))
    return issues


def check_history():
    issues = []
    for mesh in _get_meshes():
        if cmds.listConnections(f"{mesh}.inMesh") or []:
            history = cmds.listHistory(mesh, pruneDagObjects=True) or []
            history = [h for h in history if cmds.nodeType(h) != 'mesh']
            if history:
                t = _short_name(mesh)
                issues.append((f"{t}: {len(history)} history node(s)", [t]))
    return issues


def check_frozen_transforms():
    issues = []
    tol = 0.0001
    for t in (cmds.ls(type='transform', long=True) or []):
        if not (cmds.listRelatives(t, shapes=True, type='mesh') or []):
            continue
        tx, ty, tz = cmds.getAttr(f"{t}.translate")[0]
        rx, ry, rz = cmds.getAttr(f"{t}.rotate")[0]
        sx, sy, sz = cmds.getAttr(f"{t}.scale")[0]
        if (abs(tx) > tol or abs(ty) > tol or abs(tz) > tol or
                abs(rx) > tol or abs(ry) > tol or abs(rz) > tol or
                abs(sx - 1) > tol or abs(sy - 1) > tol or abs(sz - 1) > tol):
            name = t.split('|')[-1]
            issues.append((name, [name]))
    return issues


def check_pivots():
    issues = []
    tol = 0.0001
    for t in (cmds.ls(type='transform', long=True) or []):
        if not (cmds.listRelatives(t, shapes=True, type='mesh') or []):
            continue
        rp = cmds.getAttr(f"{t}.rotatePivot")[0]
        sp = cmds.getAttr(f"{t}.scalePivot")[0]
        if any(abs(v) > tol for v in rp) or any(abs(v) > tol for v in sp):
            name = t.split('|')[-1]
            issues.append((name, [name]))
    return issues


def check_duplicate_names():
    seen = {}
    for node in (cmds.ls(type='transform') or []):
        short = node.split('|')[-1]
        seen.setdefault(short, []).append(node)
    issues = []
    for name, nodes in seen.items():
        if len(nodes) > 1:
            issues.append((f"{name}  ({len(nodes)} duplicates)", nodes))
    return issues


def check_multiple_shapes():
    issues = []
    for t in (cmds.ls(type='transform', long=True) or []):
        shapes = cmds.listRelatives(t, shapes=True) or []
        if len(shapes) > 1:
            name = t.split('|')[-1]
            issues.append((f"{name}: {len(shapes)} shapes", [name]))
    return issues


def check_mesh_under_mesh():
    issues = []
    for mesh in _get_meshes():
        parent = cmds.listRelatives(mesh, parent=True, fullPath=True) or []
        if not parent:
            continue
        grandparent = cmds.listRelatives(parent[0], parent=True, fullPath=True) or []
        if grandparent:
            gp_shapes = cmds.listRelatives(grandparent[0], shapes=True, type='mesh') or []
            if gp_shapes:
                t = _short_name(mesh)
                issues.append((f"{t} parented under {grandparent[0].split('|')[-1]}", [t]))
    return issues


def check_overlapping_verts():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        points = om.MPointArray()
        fn.getPoints(points, om.MSpace.kObject)
        pos_map = {}
        for i in range(points.length()):
            p = points[i]
            key = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
            pos_map.setdefault(key, []).append(i)
        dup_idx = [i for indices in pos_map.values() if len(indices) > 1 for i in indices]
        if dup_idx:
            t = _short_name(mesh)
            issues.append((f"{t}: {len(dup_idx)} overlapping vert(s)", [f"{t}.vtx[{i}]" for i in dup_idx]))
    return issues


def check_vertex_tweaks():
    issues = []
    for mesh in _get_meshes():
        tweak_nodes = cmds.listConnections(mesh, type='tweak') or []
        for tw in tweak_nodes:
            pnts = cmds.getAttr(f"{tw}.vlist[0].vertex") or []
            dirty_idx = [i for i, p in enumerate(pnts) if any(abs(v) > 0.0001 for v in p)]
            if dirty_idx:
                t = _short_name(mesh)
                issues.append((f"{t}: {len(dirty_idx)} dirty vertex tweak(s)",
                                [f"{t}.vtx[{i}]" for i in dirty_idx]))
    return issues


def check_empty_groups():
    issues = []
    for t in (cmds.ls(type='transform', long=True) or []):
        children = cmds.listRelatives(t, children=True, fullPath=True) or []
        if not children:
            name = t.split('|')[-1]
            issues.append((name, [name]))
    return issues


def check_unused_shaders():
    issues = []
    default_ses = {'initialShadingGroup', 'initialParticleSE'}
    for se in (cmds.ls(type='shadingEngine') or []):
        if se in default_ses:
            continue
        members = cmds.sets(se, query=True) or []
        if not members:
            issues.append((f"Unused shader: {se}", [se]))
    return issues


def check_unused_textures():
    issues = []
    for node in (cmds.ls(type='file') or []):
        if not (cmds.listConnections(node, destination=True, source=False) or []):
            issues.append((f"Unused texture: {node}", [node]))
    return issues


def check_pasted_nodes():
    issues = []
    for node in (cmds.ls(long=True) or []):
        short = node.split('|')[-1]
        if 'pasted__' in short:
            issues.append((short, [short]))
    return issues


def check_namespaces():
    issues = []
    default_ns = {':'}
    for ns in (cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []):
        if ns in ('UI', 'shared'):
            continue
        nodes = cmds.ls(f"{ns}:*") or []
        if nodes:
            issues.append((f"Namespace '{ns}': {len(nodes)} node(s)", nodes[:20]))
    return issues


# ── Fix Functions ────────────────────────────────────────────────────────────
# Each takes (label, sel) and returns a human-readable log string. May raise.

def fix_history(label, sel):
    node = sel[0]
    cmds.delete(node, constructionHistory=True)
    return f"Deleted construction history from  {node}"


def fix_frozen(label, sel):
    node = sel[0]
    cmds.makeIdentity(node, apply=True, translate=True, rotate=True, scale=True)
    return f"Frozen T/R/S on  {node}"


def fix_pivots(label, sel):
    node = sel[0]
    cmds.xform(node, worldSpace=True, pivots=[0, 0, 0])
    return f"Reset pivot to world origin:  {node}"


def fix_mesh_under_mesh(label, sel):
    node = sel[0]
    cmds.parent(node, world=True)
    return f"Parented to world:  {node}"


def fix_overlapping_verts(label, sel):
    mesh = sel[0].split('.')[0]
    cmds.select(sel)
    cmds.polyMergeVertex(distance=0.001, alwaysMergeTwoVertices=True)
    cmds.select(clear=True)
    cmds.delete(mesh, constructionHistory=True)
    return f"Merged {len(sel)} overlapping vert(s) on  {mesh}  (history cleared)"


def fix_nonmanifold(label, sel):
    mesh = sel[0].split('.')[0]
    cmds.polyClean(mesh, cleanNonManifoldEdges=True, cleanNonManifoldVertices=True, flag=1)
    cmds.delete(mesh, constructionHistory=True)
    return f"Cleaned non-manifold geometry on  {mesh}  (history cleared)"


def fix_vertex_tweaks(label, sel):
    mesh = sel[0].split('.')[0]
    for tw in (cmds.listConnections(mesh, type='tweak') or []):
        n = cmds.polyEvaluate(mesh, vertex=True)
        for i in range(n):
            try:
                cmds.setAttr(f"{tw}.vlist[0].vertex[{i}]", 0, 0, 0)
            except Exception:
                pass
    return f"Cleaned vertex tweaks on  {mesh}"


def fix_duplicate_names(label, sel):
    count = 0
    base = sel[0].split('|')[-1]
    for i, node in enumerate(sel[1:], 1):
        cmds.rename(node, f"{base}_{i:02d}")
        count += 1
    return f"Renamed {count} duplicate(s) of  '{base}'"


def fix_empty_groups(label, sel):
    node = sel[0]
    cmds.delete(node)
    return f"Deleted empty group:  {node}"


def fix_unused_shaders(label, sel):
    node = sel[0]
    cmds.delete(node)
    return f"Deleted unused shader:  {node}"


def fix_unused_textures(label, sel):
    node = sel[0]
    cmds.delete(node)
    return f"Deleted unused texture node:  {node}"


def fix_pasted_nodes(label, sel):
    node = sel[0]
    new_name = node.replace('pasted__', '')
    cmds.rename(node, new_name)
    return f"Renamed  '{node}'  →  '{new_name}'"


def fix_namespaces(label, sel):
    ns = label.split("'")[1]
    cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
    return f"Removed namespace:  '{ns}'"


FIX_FUNCS = {
    "history":        fix_history,
    "frozen":         fix_frozen,
    "pivots":         fix_pivots,
    "meshparent":     fix_mesh_under_mesh,
    "overlap":        fix_overlapping_verts,
    "nonmanifold":    fix_nonmanifold,
    "tweaks":         fix_vertex_tweaks,
    "dupenames":      fix_duplicate_names,
    "emptygroups":    fix_empty_groups,
    "unusedshaders":  fix_unused_shaders,
    "unusedtex":      fix_unused_textures,
    "pastednodes":    fix_pasted_nodes,
    "namespaces":     fix_namespaces,
}

# Checks that inspect geometry topology — after fixing any of these,
# all of them must be re-run to catch cascading errors.
TOPOLOGY_CHECKS = {"ngons", "tris", "nonmanifold", "overlap", "tweaks"}


# ── Check Definitions ─────────────────────────────────────────────────────────

AUTO_CHECKS = [
    dict(id="ngons",       label="No N-gons",                     severity="MUST",   fn=check_ngons,
         tip="Meshes with non-rigid deformations must not have n-gons."),
    dict(id="tris",        label="No tris in deformed areas",      severity="SHOULD", fn=check_tris,
         tip="Tris should be avoided, especially in heavily deformed areas."),
    dict(id="nonmanifold", label="No non-manifold geometry",       severity="MUST",   fn=check_nonmanifold,
         tip="Non-manifold geometry prevents some operations from being performed."),
    dict(id="history",     label="No deformation history",         severity="MUST",   fn=check_history,
         tip="Meshes must not have any deformation history unless requested."),
    dict(id="frozen",      label="Transforms frozen (T/R/S)",      severity="MUST",   fn=check_frozen_transforms,
         tip="All transformations must be frozen: Translate, Rotate, Scale."),
    dict(id="pivots",      label="Pivots at world center",         severity="SHOULD", fn=check_pivots,
         tip="Pivots should be at the world center."),
    dict(id="dupenames",   label="No duplicate names",             severity="MUST",   fn=check_duplicate_names,
         tip="Duplicate names must be avoided."),
    dict(id="multishapes", label="Single shape per transform",     severity="MUST",   fn=check_multiple_shapes,
         tip="Each transform must have a single shape under it."),
    dict(id="meshparent",  label="No mesh parented under mesh",    severity="MUST",   fn=check_mesh_under_mesh,
         tip="Meshes can't be parented under other meshes."),
    dict(id="overlap",     label="No overlapping vertices",        severity="SHOULD", fn=check_overlapping_verts,
         tip="The same mesh should not have two or more vertices on the exact same position."),
    dict(id="tweaks",       label="Vertex local transforms clean",  severity="MUST",   fn=check_vertex_tweaks,
         tip="All vertex local transformations must be cleaned, set to 0."),
    dict(id="emptygroups",  label="No empty groups",                severity="SHOULD", fn=check_empty_groups,
         tip="Empty transform groups should be deleted before delivery."),
    dict(id="unusedshaders",label="No unused shaders",              severity="SHOULD", fn=check_unused_shaders,
         tip="Unused shading engines add noise to the scene."),
    dict(id="unusedtex",    label="No unused textures",             severity="SHOULD", fn=check_unused_textures,
         tip="Unused file texture nodes should be removed."),
    dict(id="pastednodes",  label="No 'pasted__' nodes",            severity="MUST",   fn=check_pasted_nodes,
         tip="Nodes prefixed with 'pasted__' indicate pasted content that was not renamed."),
    dict(id="namespaces",   label="No namespaces",                  severity="MUST",   fn=check_namespaces,
         tip="All namespaces must be removed before delivery."),
]

# ── Topology Auto-Check Functions ─────────────────────────────────────────────

def check_topo_ground_contact():
    meshes = _get_meshes()
    if not meshes:
        return []
    min_y = min(cmds.exactWorldBoundingBox(m)[1] for m in meshes)
    if abs(min_y) > 0.5:
        return [(f"Lowest point Y = {min_y:.3f}  (should be ~0.0)", [])]
    return []


def check_topo_symmetry():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        pts = om.MPointArray()
        fn.getPoints(pts, om.MSpace.kWorld)
        left  = sum(1 for i in range(pts.length()) if pts[i].x >  0.001)
        right = sum(1 for i in range(pts.length()) if pts[i].x < -0.001)
        if left > 10 and right > 10:
            ratio = abs(left - right) / max(left, right)
            if ratio > 0.05:
                t = _short_name(mesh)
                issues.append((f"{t}: {left} L-verts vs {right} R-verts  ({ratio*100:.0f}% diff)", [t]))
    return issues


def check_topo_poles():
    issues = []
    for mesh in _get_meshes():
        sel = om.MSelectionList()
        sel.add(mesh)
        dag = om.MDagPath()
        sel.getDagPath(0, dag)
        it = om.MItMeshVertex(dag)
        pole_idx = []
        while not it.isDone():
            if not it.onBoundary() and it.numConnectedEdges() != 4:
                pole_idx.append(it.index())
            it.next()
        if pole_idx:
            t = _short_name(mesh)
            issues.append((f"{t}: {len(pole_idx)} pole(s)",
                           [f"{t}.vtx[{i}]" for i in pole_idx[:300]]))
    return issues


_DEFAULT_CAMERAS = {'front', 'side', 'top', 'persp',
                    'frontShape', 'sideShape', 'topShape', 'perspShape'}

def check_topo_illegal_nodes():
    issues = []
    deformer_types = ['cluster', 'lattice', 'wrap', 'blendShape', 'skinCluster',
                      'nonLinear', 'sculpt', 'softMod', 'jiggle', 'wire', 'deltaMush']
    for dtype in deformer_types:
        for node in (cmds.ls(type=dtype) or []):
            issues.append((f"Deformer node: {node}  ({dtype})", [node]))
    for cam in (cmds.ls(type='camera') or []):
        if cam not in _DEFAULT_CAMERAS:
            parent = (cmds.listRelatives(cam, parent=True) or [cam])[0]
            issues.append((f"Extra camera: {parent}", [parent]))
    return issues


TOPO_AUTO_CHECKS = [
    dict(id="t_ground",   label="Character touches ground",         severity="SHOULD",
         fn=check_topo_ground_contact,
         tip="The character should be in contact with the ground (min bounding box Y ≈ 0)."),
    dict(id="t_symmetry", label="Body is symmetrical",              severity="SHOULD",
         fn=check_topo_symmetry,
         tip="The underlying body should be symmetrical along the X axis."),
    dict(id="t_poles",    label="No poles in mesh",                 severity="SHOULD",
         fn=check_topo_poles,
         tip="Meshes should not have poles (vertices with != 4 edges) in deformed areas."),
    dict(id="t_illegal",  label="No illegal nodes",                 severity="MUST",
         fn=check_topo_illegal_nodes,
         tip="Remove deformers, extra cameras, and unused shaders from the scene."),
]

# Manual-only checks (require visual inspection — cannot be automated)
MANUAL_CHECKS = [
    # Pose & Alignment
    ("SHOULD", "Feet tips point straight +Z",                                    "feet_z"),
    ("SHOULD", "Knees tips point straight +Z",                                   "knees_z"),
    ("SHOULD", "Left/Right legs are parallel (no A-pose)",                       "legs_parallel"),
    # Body Topology
    ("MUST",   "Sole and shoe have matching topology",                           "sole_topo"),
    ("MUST",   "Loops under foot/shoe are parallel & aligned to ground",         "foot_loops"),
    ("MUST",   "Real body and cloth elbows are at the same place",               "elbow_cloth"),
    ("SHOULD", "Clothing appends match the underlying topology",                 "cloth_topo"),
    ("MUST",   "Straight loop at folding positions (knuckles, elbows, fingers)", "fold_loops"),
    ("SHOULD", "Knuckles have the same topology style",                          "knuckle_style"),
    ("SHOULD", "Index/Mid/Ring/Pinky have the same topology",                    "finger_topo"),
    # Face
    ("MUST",   "Upper/lower lips vertices match (count & placement)",            "lips_match"),
    ("MUST",   "Upper/lower eyelids vertices match (count & placement)",         "eyelids_match"),
    ("SHOULD", "Lips, eyelids and eyebrows are neutralized",                     "neutralized"),
    ("MUST",   "Sealing loop through center of lips at contact point",           "lips_loop"),
    ("MUST",   "Sealing loop through center of eyelids at contact point",        "eyelids_loop"),
    ("SHOULD", "Inner lips topology is similar/parallel to outer",               "inner_lips"),
    ("INFO",   "Lip commissures checked (thickness, intersections)",             "commissures"),
    ("INFO",   "Lip intersections not excessive",                                "lip_intersect"),
    ("INFO",   "No bumps on the lips",                                           "lip_bumps"),
    # Eyes
    ("MUST",   "Cornea eye-bulge NOT modeled (rigging will handle it)",          "cornea_bulge"),
    ("SHOULD", "Cornea and eyeball have matching topology loops",                "cornea_topo"),
    ("SHOULD", "Eyebrow topology matches underlying body topology",              "eyebrow_topo"),
    ("SHOULD", "Eyelashes topology matches underlying topology",                 "eyelashes_topo"),
]

MANUAL_CATEGORIES = [
    ("Pose & Alignment",  ["feet_z", "knees_z", "legs_parallel"]),
    ("Body Topology",     ["sole_topo", "foot_loops", "elbow_cloth", "cloth_topo",
                           "fold_loops", "knuckle_style", "finger_topo"]),
    ("Face",              ["lips_match", "eyelids_match", "neutralized", "lips_loop",
                           "eyelids_loop", "inner_lips", "commissures", "lip_intersect", "lip_bumps"]),
    ("Eyes",              ["cornea_bulge", "cornea_topo", "eyebrow_topo", "eyelashes_topo"]),
]


# ── Styles ────────────────────────────────────────────────────────────────────

C = {
    "MUST":     "#c94f4f",
    "SHOULD":   "#c88c30",
    "INFO":     "#6a6a6a",
    "PASS":     "#4a9e4a",
    "IDLE":     "#555555",
    "BG":       "#282828",
    "BG2":      "#303030",
    "BG3":      "#383838",
    "TEXT":     "#d8d8d8",
    "SUBTEXT":  "#888888",
    "BORDER":   "#404040",
    "ACCENT":   "#4a7cbf",
}

STYLESHEET = f"""
QWidget {{
    background-color: {C['BG']};
    color: {C['TEXT']};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {C['BG']};
    border: none;
}}
QGroupBox {{
    border: 1px solid {C['BORDER']};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: bold;
    color: {C['TEXT']};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {C['SUBTEXT']};
}}
QPushButton {{
    background-color: {C['BG3']};
    color: {C['TEXT']};
    border: 1px solid {C['BORDER']};
    border-radius: 3px;
    padding: 5px 14px;
    min-height: 22px;
}}
QPushButton:hover  {{ background-color: #464646; }}
QPushButton:pressed {{ background-color: {C['BG2']}; }}
QPushButton:disabled {{ color: #555; }}
QCheckBox {{
    color: {C['TEXT']};
    spacing: 6px;
    font-size: 11px;
}}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border-radius: 2px;
    border: 1px solid #555;
    background: #3c3c3c;
}}
QCheckBox::indicator:checked {{
    background-color: {C['PASS']};
    border-color: {C['PASS']};
}}
QTextEdit {{
    background-color: {C['BG2']};
    color: {C['TEXT']};
    border: 1px solid {C['BORDER']};
    border-radius: 3px;
    font-family: Consolas, monospace;
    font-size: 10px;
}}
QTabWidget::pane {{
    border: 1px solid {C['BORDER']};
    border-radius: 3px;
    background: {C['BG']};
}}
QTabBar::tab {{
    background: {C['BG2']};
    color: {C['SUBTEXT']};
    padding: 6px 18px;
    border: 1px solid {C['BORDER']};
    border-bottom: none;
    border-radius: 3px 3px 0 0;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {C['BG3']};
    color: {C['TEXT']};
}}
QSplitter::handle {{ background: {C['BORDER']}; }}
"""


# ── Widgets ───────────────────────────────────────────────────────────────────

SEV_COLOR = {"MUST": C["MUST"], "SHOULD": C["SHOULD"], "INFO": C["INFO"]}


class AutoCheckRow(QtWidgets.QWidget):
    def __init__(self, label, severity, tip="", parent=None):
        super().__init__(parent)
        self.severity = severity
        self.setToolTip(tip)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(8)

        badge = QtWidgets.QLabel(severity)
        badge.setFixedWidth(50)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{SEV_COLOR.get(severity, C['INFO'])}; color:white;"
            "border-radius:3px; font-size:9px; font-weight:bold; padding:2px 0;"
        )

        self.dot = QtWidgets.QLabel("●")
        self.dot.setFixedWidth(16)
        self.dot.setAlignment(Qt.AlignCenter)
        self._set_dot(C["IDLE"], "—")

        lbl = QtWidgets.QLabel(label)
        lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        lay.addWidget(badge)
        lay.addWidget(self.dot)
        lay.addWidget(lbl)
        ui_utils.apply_maya_style(self)

    def _set_dot(self, color, tooltip):
        self.dot.setStyleSheet(f"color:{color}; font-size:15px;")
        self.dot.setToolTip(tooltip)

    def set_pass(self):      self._set_dot(C["PASS"],  "PASS")
    def set_idle(self):      self._set_dot(C["IDLE"],  "Not run")
    def set_running(self):   self._set_dot("#aaaaaa",  "Running…")
    def set_fail(self, msg):
        color = C["MUST"] if self.severity == "MUST" else C["SHOULD"]
        self._set_dot(color, f"FAIL: {msg}")


class ManualCheckRow(QtWidgets.QWidget):
    def __init__(self, label, severity, parent=None):
        super().__init__(parent)
        self._row_selected = False
        self.setAutoFillBackground(True)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(8)

        badge = QtWidgets.QLabel(severity)
        badge.setFixedWidth(50)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{SEV_COLOR.get(severity, C['INFO'])}; color:white;"
            "border-radius:3px; font-size:9px; font-weight:bold; padding:2px 0;"
        )

        self.cb = QtWidgets.QCheckBox(label)
        lay.addWidget(badge)
        lay.addWidget(self.cb, 1)
        ui_utils.apply_maya_style(self)

    def mousePressEvent(self, event):
        # Toggle row highlight on click outside the checkbox indicator area
        self._row_selected = not self._row_selected
        self._refresh_bg()
        super().mousePressEvent(event)

    def _refresh_bg(self):
        pal = self.palette()
        color = QtGui.QColor("#3a5070") if self._row_selected else QtGui.QColor("transparent")
        pal.setColor(QtGui.QPalette.Window, color)
        self.setPalette(pal)

    @property
    def row_selected(self):
        return self._row_selected

    @property
    def checked(self):
        return self.cb.isChecked()


class FixIssueRow(QtWidgets.QWidget):
    fix_requested    = QtCore.Signal(tuple)   # (check_id, label, sel)
    select_requested = QtCore.Signal(list)

    def __init__(self, check_id, label, sel, fixable=True, severity="MUST", parent=None):
        super().__init__(parent)
        self.check_id = check_id
        self.label    = label
        self.sel      = sel

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        dot_color = C["MUST"] if severity == "MUST" else C["SHOULD"]
        self._dot = QtWidgets.QLabel("●")
        self._dot.setFixedWidth(14)
        self._dot.setStyleSheet(f"color:{dot_color}; font-size:12px;")

        lbl = QtWidgets.QLabel(label)
        lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        sel_btn = QtWidgets.QPushButton("Select")
        sel_btn.setFixedSize(52, 20)
        sel_btn.setStyleSheet("font-size:10px; padding:1px 4px;")
        sel_btn.clicked.connect(lambda: self.select_requested.emit(self.sel))

        lay.addWidget(self._dot)
        lay.addWidget(lbl, 1)
        lay.addWidget(sel_btn)

        if fixable:
            self._fix_btn = QtWidgets.QPushButton("Fix")
            self._fix_btn.setFixedSize(38, 20)
            self._fix_btn.setStyleSheet(
                "QPushButton{background:#2d5a2d;color:white;font-size:10px;padding:1px 4px;}"
                "QPushButton:hover{background:#3a7a3a;}"
                "QPushButton:disabled{background:#333;color:#555;}"
            )
            self._fix_btn.clicked.connect(
                lambda: self.fix_requested.emit((self.check_id, self.label, self.sel))
            )
            lay.addWidget(self._fix_btn)
        else:
            tag = QtWidgets.QLabel("manual")
            tag.setStyleSheet(f"color:{C['SUBTEXT']}; font-size:9px; font-style:italic;")
            lay.addWidget(tag)

        ui_utils.apply_maya_style(self)

    def mark_fixed(self):
        self._dot.setStyleSheet(f"color:{C['PASS']}; font-size:12px;")
        if hasattr(self, '_fix_btn'):
            self._fix_btn.setEnabled(False)
            self._fix_btn.setText("✓")


# ── Main Window ───────────────────────────────────────────────────────────────

class IssueLog(QtWidgets.QListWidget):
    """Clickable log — issue items select the node in Maya on click."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {C['BG2']};
                color: {C['TEXT']};
                border: 1px solid {C['BORDER']};
                border-radius: 3px;
                font-family: Consolas, monospace;
                font-size: 10px;
                outline: 0;
            }}
            QListWidget::item:selected {{
                background-color: #3a5070;
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: #353535;
            }}
        """)
        self.itemClicked.connect(self._on_click)

    def _on_click(self, item):
        components = item.data(Qt.UserRole)
        if components:
            try:
                cmds.select(components, replace=True)
            except Exception:
                pass

    def add_header(self, text, color):
        item = QtWidgets.QListWidgetItem(f"  {text}")
        item.setForeground(QtGui.QColor(color))
        font = QtGui.QFont("Consolas", 10)
        font.setBold(True)
        item.setFont(font)
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.addItem(item)

    def add_issue(self, text, sel=None):
        item = QtWidgets.QListWidgetItem(f"    • {text}")
        if sel:
            item.setData(Qt.UserRole, sel)
            item.setForeground(QtGui.QColor("#c8c8c8"))
            n = len(sel)
            item.setToolTip(f"Click to select  ({n} component{'s' if n != 1 else ''})")
        else:
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QtGui.QColor("#777777"))
        self.addItem(item)

    def add_info(self, text, color=None):
        item = QtWidgets.QListWidgetItem(f"  {text}")
        item.setForeground(QtGui.QColor(color or C["SUBTEXT"]))
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.addItem(item)

    def add_separator(self):
        item = QtWidgets.QListWidgetItem("")
        item.setFlags(Qt.NoItemFlags)
        self.addItem(item)



class ModelCheckerWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle("Model Checker")
        self.setMinimumSize(500, 720)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self._auto_rows    = {}
        self._topo_rows    = {}
        self._manual_rows  = []
        self._fix_rows     = []
        self._build()
        ui_utils.apply_maya_style(self)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Header
        title = QtWidgets.QLabel("MODEL CHECKER")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:15px; font-weight:bold; letter-spacing:2px; color:white;")
        root.addWidget(title)

        sub = QtWidgets.QLabel("Modeling Standards  ·  Laia Peris  ·  2026")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"font-size:10px; color:{C['SUBTEXT']}; margin-bottom:2px;")
        root.addWidget(sub)

        # Splitter: tabs on top, log on bottom (user-resizable)
        splitter = QtWidgets.QSplitter(Qt.Vertical)
        splitter.setHandleWidth(4)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_auto_tab(),   "Tech Checks  (auto)")
        tabs.addTab(self._build_manual_tab(), "Topology Checks  (manual)")
        tabs.addTab(self._build_fix_tab(),    "Auto Fix")
        splitter.addWidget(tabs)

        log_widget = QtWidgets.QWidget()
        log_lay = QtWidgets.QVBoxLayout(log_widget)
        log_lay.setContentsMargins(0, 4, 0, 0)
        log_lay.setSpacing(4)

        log_header = QtWidgets.QLabel("Results  —  click an error to select in Maya")
        log_header.setStyleSheet(f"color:{C['SUBTEXT']}; font-size:10px;")
        log_lay.addWidget(log_header)

        self.log = IssueLog()
        log_lay.addWidget(self.log)
        splitter.addWidget(log_widget)

        splitter.setSizes([420, 220])
        root.addWidget(splitter, 1)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("▶  Run All Auto Checks")
        self.run_btn.setStyleSheet(
            f"QPushButton{{background:#2d5a2d;color:white;font-weight:bold;}}"
            f"QPushButton:hover{{background:#3a7a3a;}}"
        )
        self.run_btn.clicked.connect(self.run_all)

        clear_btn = QtWidgets.QPushButton("Clear Log")
        clear_btn.clicked.connect(self.log.clear)

        copy_btn = QtWidgets.QPushButton("Copy Report")
        copy_btn.clicked.connect(self._copy_report)

        btn_row.addWidget(self.run_btn, 2)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(copy_btn)
        root.addLayout(btn_row)

    def _build_auto_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 8, 6, 6)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        inner_lay = QtWidgets.QVBoxLayout(inner)
        inner_lay.setSpacing(2)
        inner_lay.setContentsMargins(0, 0, 0, 0)

        for ch in AUTO_CHECKS:
            row = AutoCheckRow(ch["label"], ch["severity"], ch["tip"])
            inner_lay.addWidget(row)
            self._auto_rows[ch["id"]] = row

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        return w

    def _build_manual_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 8, 6, 6)
        lay.setSpacing(6)

        # ── Auto topology checks ───────────────────────────────────────────────
        auto_group = QtWidgets.QGroupBox("Auto Checks")
        auto_group.setStyleSheet(
            f"QGroupBox{{color:{C['HEADER'] if 'HEADER' in C else C['TEXT']};"
            "font-weight:bold;}}"
        )
        auto_g_lay = QtWidgets.QVBoxLayout(auto_group)
        auto_g_lay.setSpacing(2)
        auto_g_lay.setContentsMargins(4, 12, 4, 6)

        for ch in TOPO_AUTO_CHECKS:
            row = AutoCheckRow(ch["label"], ch["severity"], ch["tip"])
            auto_g_lay.addWidget(row)
            self._topo_rows[ch["id"]] = row

        run_topo_btn = QtWidgets.QPushButton("▶  Run Auto Checks")
        run_topo_btn.setStyleSheet(
            f"QPushButton{{background:#2d5a2d;color:white;font-weight:bold;}}"
            f"QPushButton:hover{{background:#3a7a3a;}}"
        )
        run_topo_btn.clicked.connect(self._run_topo_checks)
        auto_g_lay.addWidget(run_topo_btn)
        lay.addWidget(auto_group)

        # ── Manual visual checks ───────────────────────────────────────────────
        manual_lbl = QtWidgets.QLabel("Manual Checks  —  visual inspection required")
        manual_lbl.setStyleSheet(f"color:{C['SUBTEXT']}; font-size:10px; margin-top:4px;")
        lay.addWidget(manual_lbl)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        inner = QtWidgets.QWidget()
        inner_lay = QtWidgets.QVBoxLayout(inner)
        inner_lay.setSpacing(4)
        inner_lay.setContentsMargins(0, 0, 0, 0)

        check_map = {c[2]: (c[0], c[1]) for c in MANUAL_CHECKS}
        for cat_name, ids in MANUAL_CATEGORIES:
            group = QtWidgets.QGroupBox(cat_name)
            g_lay = QtWidgets.QVBoxLayout(group)
            g_lay.setSpacing(2)
            g_lay.setContentsMargins(4, 12, 4, 6)
            for cid in ids:
                if cid in check_map:
                    sev, label = check_map[cid]
                    row = ManualCheckRow(label, sev)
                    g_lay.addWidget(row)
                    self._manual_rows.append((cid, row))
            inner_lay.addWidget(group)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        btn_row = QtWidgets.QHBoxLayout()
        check_sel_btn = QtWidgets.QPushButton("Check Selected")
        check_sel_btn.setToolTip("Mark highlighted rows as checked")
        check_sel_btn.clicked.connect(self._check_selected_manual)
        check_all_btn = QtWidgets.QPushButton("Check All")
        check_all_btn.clicked.connect(lambda: [r.cb.setChecked(True) for _, r in self._manual_rows])
        reset_btn = QtWidgets.QPushButton("Reset")
        reset_btn.clicked.connect(lambda: [r.cb.setChecked(False) for _, r in self._manual_rows])
        btn_row.addWidget(check_sel_btn)
        btn_row.addWidget(check_all_btn)
        btn_row.addWidget(reset_btn)
        lay.addLayout(btn_row)
        return w

    def _run_topo_checks(self):
        for ch in TOPO_AUTO_CHECKS:
            row = self._topo_rows[ch["id"]]
            row.set_running()
            QtWidgets.QApplication.processEvents()
            try:
                issues = ch["fn"]()
            except Exception as e:
                self.log.add_info(f"[ERROR] {ch['label']}: {e}")
                row.set_idle()
                continue
            if issues:
                row.set_fail(f"{len(issues)} issue(s)")
                color = C["MUST"] if ch["severity"] == "MUST" else C["SHOULD"]
                self.log.add_header(f"[{ch['severity']}] {ch['label']}", color)
                for label, sel in issues[:12]:
                    self.log.add_issue(label, sel=sel if sel else None)
            else:
                row.set_pass()
                self.log.add_info(f"✓  {ch['label']}", color=C["PASS"])

    def _check_selected_manual(self):
        for _, row in self._manual_rows:
            if row.row_selected:
                row.cb.setChecked(True)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def run_all(self):
        self.log.clear()
        self.run_btn.setEnabled(False)
        must_fails = should_fails = 0

        for ch in AUTO_CHECKS:
            row = self._auto_rows[ch["id"]]
            row.set_running()
            QtWidgets.QApplication.processEvents()

            try:
                issues = ch["fn"]()
            except Exception as e:
                self.log.add_info(f"[ERROR] {ch['label']}: {e}")
                row.set_idle()
                continue

            if issues:
                row.set_fail(f"{len(issues)} issue(s)")
                if ch["severity"] == "MUST":
                    must_fails += 1
                    color = C["MUST"]
                else:
                    should_fails += 1
                    color = C["SHOULD"]
                self.log.add_header(f"[{ch['severity']}] {ch['label']}", color)
                for label, sel in issues[:12]:
                    self.log.add_issue(label, sel=sel)
                if len(issues) > 12:
                    self.log.add_info(f"    … and {len(issues) - 12} more")
            else:
                row.set_pass()
                self.log.add_info(f"✓  {ch['label']}", color=C["PASS"])

        self.log.add_separator()
        if must_fails == 0 and should_fails == 0:
            self.log.add_info("✓  All checks passed!", color=C["PASS"])
        else:
            if must_fails:
                self.log.add_info(f"✗  {must_fails} MUST failure(s) — blockers", color=C["MUST"])
            if should_fails:
                self.log.add_info(f"⚠  {should_fails} SHOULD warning(s)", color=C["SHOULD"])

        self.run_btn.setEnabled(True)

    def _build_fix_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 8, 6, 6)
        lay.setSpacing(6)

        scan_btn = QtWidgets.QPushButton("⟳   Scan for Issues")
        scan_btn.clicked.connect(self._populate_fix_tab)
        lay.addWidget(scan_btn)

        self._fix_scroll = QtWidgets.QScrollArea()
        self._fix_scroll.setWidgetResizable(True)
        self._fix_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        placeholder = QtWidgets.QLabel("Click  'Scan for Issues'  to populate this list.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color:{C['SUBTEXT']};")
        self._fix_scroll.setWidget(placeholder)
        lay.addWidget(self._fix_scroll, 1)

        self._fix_all_btn = QtWidgets.QPushButton("⚡   Fix All Fixable Issues")
        self._fix_all_btn.setEnabled(False)
        self._fix_all_btn.setStyleSheet(
            f"QPushButton{{background:#4a3a10;color:white;font-weight:bold;}}"
            f"QPushButton:hover{{background:#6a5518;}}"
            f"QPushButton:disabled{{background:#2a2a2a;color:#555;}}"
        )
        self._fix_all_btn.clicked.connect(self._fix_all)
        lay.addWidget(self._fix_all_btn)

        log_lbl = QtWidgets.QLabel("Fix Log")
        log_lbl.setStyleSheet(f"color:{C['SUBTEXT']}; font-size:10px; margin-top:2px;")
        lay.addWidget(log_lbl)

        self.fix_log = QtWidgets.QListWidget()
        self.fix_log.setStyleSheet(f"""
            QListWidget {{
                background:{C['BG2']}; color:{C['TEXT']};
                border:1px solid {C['BORDER']}; border-radius:3px;
                font-family:Consolas,monospace; font-size:10px;
            }}
        """)
        self.fix_log.setMinimumHeight(120)
        self.fix_log.setMaximumHeight(180)
        lay.addWidget(self.fix_log)
        return w

    def _populate_fix_tab(self):
        self._fix_rows = []
        inner = QtWidgets.QWidget()
        inner_lay = QtWidgets.QVBoxLayout(inner)
        inner_lay.setSpacing(4)
        inner_lay.setContentsMargins(0, 0, 0, 0)

        any_issues = False
        for ch in AUTO_CHECKS:
            try:
                issues = ch["fn"]()
            except Exception:
                continue
            if not issues:
                continue

            any_issues = True
            fixable = ch["id"] in FIX_FUNCS
            color = C["MUST"] if ch["severity"] == "MUST" else C["SHOULD"]

            group = QtWidgets.QGroupBox(f"[{ch['severity']}]  {ch['label']}")
            group.setStyleSheet(
                f"QGroupBox{{color:{color};border-color:{color}55;"
                f"border-width:1px;border-style:solid;border-radius:4px;"
                f"margin-top:10px;padding-top:6px;}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 4px;}}"
            )
            g_lay = QtWidgets.QVBoxLayout(group)
            g_lay.setSpacing(2)
            g_lay.setContentsMargins(4, 12, 4, 6)

            for label, sel in issues:
                row = FixIssueRow(ch["id"], label, sel,
                                  fixable=fixable, severity=ch["severity"])
                row.fix_requested.connect(self._on_fix_requested)
                row.select_requested.connect(lambda s: cmds.select(s, replace=True))
                g_lay.addWidget(row)
                self._fix_rows.append(row)

            inner_lay.addWidget(group)

        if not any_issues:
            ok = QtWidgets.QLabel("✓   No issues found!")
            ok.setAlignment(Qt.AlignCenter)
            ok.setStyleSheet(f"color:{C['PASS']}; font-size:13px; font-weight:bold;")
            inner_lay.addWidget(ok)

        inner_lay.addStretch()
        self._fix_scroll.setWidget(inner)
        self._fix_all_btn.setEnabled(any_issues)

    def _on_fix_requested(self, data):
        check_id, label, sel = data
        fn = FIX_FUNCS.get(check_id)
        if not fn:
            return
        try:
            msg = fn(label, sel)
            self._log_fix(f"✓  {msg}", C["PASS"])
            for row in self._fix_rows:
                if row.check_id == check_id and row.label == label:
                    row.mark_fixed()
                    break
            self._recheck_after(check_id)
        except Exception as e:
            self._log_fix(f"✗  {label}:  {e}", C["MUST"])

    def _fix_all(self):
        self.fix_log.clear()
        self._log_fix("── Fix All started ──────────────────", C["SUBTEXT"])
        fixed = errors = 0
        for row in self._fix_rows:
            if not hasattr(row, '_fix_btn') or not row._fix_btn.isEnabled():
                continue
            fn = FIX_FUNCS.get(row.check_id)
            if not fn:
                continue
            try:
                msg = fn(row.label, row.sel)
                self._log_fix(f"✓  {msg}", C["PASS"])
                row.mark_fixed()
                fixed += 1
            except Exception as e:
                self._log_fix(f"✗  {row.label}:  {e}", C["MUST"])
                errors += 1
        self._log_fix(
            f"── Done:  {fixed} fixed,  {errors} error(s) ──────────",
            C["PASS"] if not errors else C["SHOULD"]
        )
        self._log_fix("── Running full QC re-check ─────────", C["SUBTEXT"])
        self._full_recheck()

    def _recheck_after(self, fixed_check_id):
        """After a single fix, re-run that check + all topology checks if applicable."""
        ids_to_run = {fixed_check_id} | (TOPOLOGY_CHECKS if fixed_check_id in TOPOLOGY_CHECKS else set())
        checks = [ch for ch in AUTO_CHECKS if ch["id"] in ids_to_run]
        self._log_fix("  ── Re-check ─────────────────────────", C["SUBTEXT"])
        found = 0
        for ch in checks:
            try:
                issues = ch["fn"]()
                if issues:
                    found += len(issues)
                    color = C["MUST"] if ch["severity"] == "MUST" else C["SHOULD"]
                    for lbl, _ in issues[:4]:
                        self._log_fix(f"  ⚠  [{ch['severity']}] {lbl}", color)
                    if len(issues) > 4:
                        self._log_fix(f"     … and {len(issues) - 4} more", C["SUBTEXT"])
                else:
                    self._log_fix(f"  ✓  {ch['label']}", C["PASS"])
            except Exception:
                pass
        if found:
            self._log_fix(f"  ⚠  {found} issue(s) remain — re-scan recommended", C["SHOULD"])

    def _full_recheck(self):
        """Run every check and report remaining issues in the fix log."""
        self._log_fix("── Full QC re-check ─────────────────", C["SUBTEXT"])
        remaining = 0
        for ch in AUTO_CHECKS:
            try:
                issues = ch["fn"]()
                if issues:
                    remaining += len(issues)
                    color = C["MUST"] if ch["severity"] == "MUST" else C["SHOULD"]
                    self._log_fix(f"⚠  [{ch['severity']}] {ch['label']}  ({len(issues)} issue(s))", color)
                    for lbl, _ in issues[:4]:
                        self._log_fix(f"   • {lbl}", color)
                    if len(issues) > 4:
                        self._log_fix(f"   … and {len(issues) - 4} more", C["SUBTEXT"])
                else:
                    self._log_fix(f"✓  {ch['label']}", C["PASS"])
            except Exception:
                pass
        if not remaining:
            self._log_fix("── Scene is clean! ──────────────────", C["PASS"])
            self._fix_all_btn.setEnabled(False)
        else:
            self._log_fix(f"── {remaining} issue(s) remain ──────────────", C["SHOULD"])

    def _log_fix(self, text, color=None):
        item = QtWidgets.QListWidgetItem(text)
        item.setForeground(QtGui.QColor(color or C["TEXT"]))
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.fix_log.addItem(item)
        self.fix_log.scrollToBottom()

    def _copy_report(self):
        lines = ["Minimo Model Checker — Report", "=" * 44, "", "AUTO CHECKS:"]
        for ch in AUTO_CHECKS:
            row = self._auto_rows[ch["id"]]
            status = row.dot.toolTip() or "Not run"
            lines.append(f"  [{ch['severity']:6}] {ch['label']}: {status}")

        lines += ["", "MANUAL CHECKS:"]
        for _, row in self._manual_rows:
            mark = "X" if row.checked else " "
            lines.append(f"  [{mark}] {row.cb.text()}")

        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
        self.log.add_info("Report copied to clipboard.", color=C["ACCENT"])


# ── Entry Point ───────────────────────────────────────────────────────────────

_window = None


def show():
    global _window
    try:
        _window.close()
        _window.deleteLater()
    except Exception:
        pass
    _window = ModelCheckerWindow()
    _window.show()
