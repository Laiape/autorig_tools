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

def check_ngons():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        counts, verts = om.MIntArray(), om.MIntArray()
        fn.getVertices(counts, verts)
        n = sum(1 for c in counts if c > 4)
        if n:
            issues.append(f"{_short_name(mesh)}: {n} n-gon(s)")
    return issues


def check_tris():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        counts, verts = om.MIntArray(), om.MIntArray()
        fn.getVertices(counts, verts)
        n = sum(1 for c in counts if c == 3)
        if n:
            issues.append(f"{_short_name(mesh)}: {n} tri(s)")
    return issues


def check_nonmanifold():
    issues = []
    for mesh in _get_meshes():
        nm_v = cmds.polyInfo(mesh, nmv=True) or []
        nm_e = cmds.polyInfo(mesh, nme=True) or []
        if nm_v or nm_e:
            issues.append(f"{_short_name(mesh)}: {len(nm_v)} non-manifold vert(s), {len(nm_e)} edge(s)")
    return issues


def check_history():
    issues = []
    for mesh in _get_meshes():
        if cmds.listConnections(f"{mesh}.inMesh") or []:
            history = cmds.listHistory(mesh, pruneDagObjects=True) or []
            history = [h for h in history if cmds.nodeType(h) != 'mesh']
            if history:
                issues.append(f"{_short_name(mesh)}: {len(history)} history node(s)")
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
            issues.append(t.split('|')[-1])
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
            issues.append(t.split('|')[-1])
    return issues


def check_duplicate_names():
    seen = {}
    for node in (cmds.ls(type='transform') or []):
        short = node.split('|')[-1]
        seen.setdefault(short, 0)
        seen[short] += 1
    return [k for k, v in seen.items() if v > 1]


def check_multiple_shapes():
    issues = []
    for t in (cmds.ls(type='transform', long=True) or []):
        shapes = cmds.listRelatives(t, shapes=True) or []
        if len(shapes) > 1:
            issues.append(f"{t.split('|')[-1]}: {len(shapes)} shapes")
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
                issues.append(f"{_short_name(mesh)} parented under {grandparent[0].split('|')[-1]}")
    return issues


def check_overlapping_verts():
    issues = []
    for mesh in _get_meshes():
        fn = _mesh_fn(mesh)
        points = om.MPointArray()
        fn.getPoints(points, om.MSpace.kObject)
        seen = {}
        for i in range(points.length()):
            p = points[i]
            key = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
            seen[key] = seen.get(key, 0) + 1
        dupes = sum(1 for v in seen.values() if v > 1)
        if dupes:
            issues.append(f"{_short_name(mesh)}: {dupes} overlapping vertex position(s)")
    return issues


def check_vertex_tweaks():
    issues = []
    for mesh in _get_meshes():
        tweak_nodes = cmds.listConnections(mesh, type='tweak') or []
        for tw in tweak_nodes:
            pnts = cmds.getAttr(f"{tw}.vlist[0].vertex") or []
            dirty = [p for p in pnts if any(abs(v) > 0.0001 for v in p)]
            if dirty:
                issues.append(f"{_short_name(mesh)}: {len(dirty)} dirty vertex tweak(s)")
    return issues


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
    dict(id="tweaks",      label="Vertex local transforms clean",  severity="MUST",   fn=check_vertex_tweaks,
         tip="All vertex local transformations must be cleaned, set to 0."),
]

MANUAL_CHECKS = [
    # Pose & Alignment
    ("SHOULD", "Character is in contact with the ground",                     "pose"),
    ("SHOULD", "Feet tips point straight +Z",                                 "feet_z"),
    ("SHOULD", "Knees tips point straight +Z",                                "knees_z"),
    ("SHOULD", "Left/Right legs are parallel (no A-pose)",                    "legs_parallel"),
    # Body Topology
    ("MUST",   "Sole and shoe have matching topology",                        "sole_topo"),
    ("MUST",   "Loops under foot/shoe are parallel & aligned to ground",      "foot_loops"),
    ("MUST",   "Real body and cloth elbows are at the same place",            "elbow_cloth"),
    ("SHOULD", "Clothing appends match the underlying topology",              "cloth_topo"),
    ("MUST",   "Straight loop at folding positions (knuckles, elbows, fingers)", "fold_loops"),
    ("SHOULD", "Knuckles have the same topology style",                       "knuckle_style"),
    ("SHOULD", "Index/Mid/Ring/Pinky have the same topology",                 "finger_topo"),
    ("SHOULD", "Underlying body is symmetrical",                              "symmetry"),
    ("SHOULD", "No poles in heavily deformed areas (elbows, knees, lips…)",   "poles"),
    # Face
    ("MUST",   "Upper/lower lips vertices match (count & placement)",         "lips_match"),
    ("MUST",   "Upper/lower eyelids vertices match (count & placement)",      "eyelids_match"),
    ("SHOULD", "Lips, eyelids and eyebrows are neutralized",                  "neutralized"),
    ("MUST",   "Sealing loop through center of lips at contact point",        "lips_loop"),
    ("MUST",   "Sealing loop through center of eyelids at contact point",     "eyelids_loop"),
    ("SHOULD", "Inner lips topology is similar/parallel to outer",            "inner_lips"),
    ("INFO",   "Lip commissures checked (thickness, intersections)",          "commissures"),
    ("INFO",   "Lip intersections not excessive",                             "lip_intersect"),
    ("INFO",   "No bumps on the lips",                                        "lip_bumps"),
    # Eyes
    ("MUST",   "Cornea eye-bulge NOT modeled (rigging will handle it)",       "cornea_bulge"),
    ("SHOULD", "Cornea and eyeball have matching topology loops",             "cornea_topo"),
    ("SHOULD", "Eyebrow topology matches underlying body topology",           "eyebrow_topo"),
    ("SHOULD", "Eyelashes topology matches underlying topology",              "eyelashes_topo"),
    # Scene
    ("MUST",   "No illegal nodes (deformers, extra cameras, unused shaders)", "illegal_nodes"),
]

MANUAL_CATEGORIES = [
    ("Pose & Alignment",  ["pose", "feet_z", "knees_z", "legs_parallel"]),
    ("Body Topology",     ["sole_topo", "foot_loops", "elbow_cloth", "cloth_topo",
                           "fold_loops", "knuckle_style", "finger_topo", "symmetry", "poles"]),
    ("Face",              ["lips_match", "eyelids_match", "neutralized", "lips_loop",
                           "eyelids_loop", "inner_lips", "commissures", "lip_intersect", "lip_bumps"]),
    ("Eyes",              ["cornea_bulge", "cornea_topo", "eyebrow_topo", "eyelashes_topo"]),
    ("Scene Cleanup",     ["illegal_nodes"]),
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

    @property
    def checked(self):
        return self.cb.isChecked()


# ── Main Window ───────────────────────────────────────────────────────────────

class ModelCheckerWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle("Model Checker  —  Minimo")
        self.setMinimumSize(500, 680)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setStyleSheet(STYLESHEET)
        self._auto_rows = {}
        self._manual_rows = []
        self._build()

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

        # Tabs
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_auto_tab(),   "Tech Checks  (auto)")
        tabs.addTab(self._build_manual_tab(), "Topology Checks  (manual)")
        root.addWidget(tabs, 1)

        # Log
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(110)
        self.log.setPlaceholderText("Run checks to see results…")
        root.addWidget(self.log)

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

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
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
        lay.addWidget(scroll)

        reset_btn = QtWidgets.QPushButton("Reset Checkboxes")
        reset_btn.clicked.connect(lambda: [r.cb.setChecked(False) for _, r in self._manual_rows])
        lay.addWidget(reset_btn)
        return w

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
                self.log.append(f'<span style="color:#666">[ERROR] {ch["label"]}: {e}</span>')
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
                self.log.append(f'<span style="color:{color}"><b>[{ch["severity"]}] {ch["label"]}</b></span>')
                for issue in issues[:8]:
                    self.log.append(f'&nbsp;&nbsp;• {issue}')
                if len(issues) > 8:
                    self.log.append(f'&nbsp;&nbsp;… and {len(issues) - 8} more')
            else:
                row.set_pass()

        self.log.append("")
        if must_fails == 0 and should_fails == 0:
            self.log.append(f'<span style="color:{C["PASS"]}"><b>✓ All checks passed!</b></span>')
        else:
            if must_fails:
                self.log.append(f'<span style="color:{C["MUST"]}"><b>✗ {must_fails} MUST failure(s) — blockers</b></span>')
            if should_fails:
                self.log.append(f'<span style="color:{C["SHOULD"]}"><b>⚠ {should_fails} SHOULD warning(s)</b></span>')

        self.run_btn.setEnabled(True)

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
        self.log.append(f'<span style="color:{C["ACCENT"]}">Report copied to clipboard.</span>')


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
