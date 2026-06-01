"""
deboor_tools_UI.py
==================
PySide6/2 UI for De Boor Algorithm tools integrated with AutoRig Tools.

Tabs:
  - De Boor Ribbon        — procedural spline ribbon rig
  - Split Blendshape      — split blendshape targets along a curve
  - Skin — Curve          — redistribute skin weights along a curve
  - Skin — Surface        — redistribute skin weights across a NURBS surface

Launch from Maya Script Editor:
    from ui import deboor_tools_UI
    from importlib import reload
    reload(deboor_tools_UI)
    deboor_tools_UI.show()
"""

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Qt
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Qt
    from shiboken2 import wrapInstance

from utils import ui_utils


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _pick_row(line_edit, callback, btn_label="Pick", btn_width=50):
    row = QtWidgets.QWidget()
    lay = QtWidgets.QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(line_edit)
    btn = QtWidgets.QPushButton(btn_label)
    btn.setFixedWidth(btn_width)
    btn.clicked.connect(callback)
    lay.addWidget(btn)
    return row


def _status_label():
    lbl = QtWidgets.QLabel("")
    lbl.setObjectName("status")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
#  STYLE
# ─────────────────────────────────────────────────────────────────────────────

_STYLE = """
QDialog, QWidget {
    background-color: #2b2b2b;
    color: #cccccc;
    font-size: 12px;
}
QTabWidget::pane { border: 1px solid #444; }
QTabBar::tab {
    background: #222;
    color: #aaa;
    padding: 6px 14px;
    border: 1px solid #444;
    border-bottom: none;
}
QTabBar::tab:selected { background: #2b2b2b; color: #fff; }
QTabBar::tab:hover    { background: #333;    color: #ddd; }
QGroupBox {
    border: 1px solid #444;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
    font-weight: bold;
    color: #aaaaaa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QLineEdit {
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px 6px;
    color: #dddddd;
}
QLineEdit:focus { border: 1px solid #4a9eff; }
QPushButton {
    background: #3a3a3a;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 4px 10px;
    color: #cccccc;
}
QPushButton:hover  { background: #484848; border-color: #4a9eff; }
QPushButton:pressed{ background: #2d2d2d; }
QPushButton#primary {
    background: #1a5fa8;
    border: 1px solid #3278c0;
    color: #ffffff;
    font-weight: bold;
    font-size: 13px;
    padding: 8px;
}
QPushButton#primary:hover  { background: #2070c0; }
QPushButton#primary:pressed{ background: #104080; }
QPushButton#primary:disabled{ background: #2a2a2a; color: #555; border-color: #444; }
QPushButton#danger {
    background: #8b1a1a;
    border: 1px solid #b02020;
    color: #ffffff;
    padding: 3px 8px;
}
QPushButton#danger:hover { background: #a52020; }
QComboBox {
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px 6px;
    color: #dddddd;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: #2b2b2b; selection-background-color: #1a5fa8; }
QSpinBox, QDoubleSpinBox {
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 2px 4px;
    color: #dddddd;
}
QCheckBox { color: #cccccc; }
QCheckBox::indicator { width: 14px; height: 14px; }
QListWidget {
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 3px;
    color: #dddddd;
}
QListWidget::item:selected { background: #1a5fa8; }
QTextEdit {
    background: #1a1a1a;
    border: 1px solid #444;
    border-radius: 3px;
    color: #aaaaaa;
    font-family: Consolas, monospace;
    font-size: 11px;
}
QLabel#status { color: #888888; font-style: italic; }
QScrollArea { border: none; background: transparent; }
"""


# ─────────────────────────────────────────────────────────────────────────────
#  DEGREE ROW WIDGET  (shared pattern)
# ─────────────────────────────────────────────────────────────────────────────

class DegreeRow(QtWidgets.QWidget):
    def __init__(self, auto_label="Auto (n-1)", default=3, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.spin = QtWidgets.QSpinBox()
        self.spin.setRange(1, 7)
        self.spin.setValue(default)
        self.spin.setEnabled(False)

        self.auto_cb = QtWidgets.QCheckBox(auto_label)
        self.auto_cb.setChecked(True)
        self.auto_cb.toggled.connect(lambda c: self.spin.setEnabled(not c))

        lay.addWidget(self.spin)
        lay.addWidget(self.auto_cb)
        lay.addStretch()

    def value(self):
        return None if self.auto_cb.isChecked() else self.spin.value()


# ─────────────────────────────────────────────────────────────────────────────
#  LIST WIDGET WITH ADD / REMOVE BUTTONS
# ─────────────────────────────────────────────────────────────────────────────

class PickListWidget(QtWidgets.QWidget):
    """List of Maya node names with Add-from-selection and Clear buttons."""

    def __init__(self, height=90, node_type=None, parent=None):
        super().__init__(parent)
        self._node_type = node_type  # None = any; "joint" = joints only

        self._list = QtWidgets.QListWidget()
        self._list.setFixedHeight(height)

        self._btn_add   = QtWidgets.QPushButton("+ Add Selection")
        self._btn_rem   = QtWidgets.QPushButton("Remove")
        self._btn_rem.setObjectName("danger")
        self._btn_rem.setFixedWidth(62)
        self._btn_clear = QtWidgets.QPushButton("Clear")
        self._btn_clear.setFixedWidth(48)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_rem)
        btn_row.addWidget(self._btn_clear)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.addWidget(self._list)
        lay.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add)
        self._btn_rem.clicked.connect(self._remove)
        self._btn_clear.clicked.connect(self._list.clear)

    def _add(self):
        if self._node_type:
            sel = cmds.ls(sl=True, type=self._node_type) or []
        else:
            sel = cmds.ls(sl=True, long=False) or []
        for obj in sel:
            if not self._list.findItems(obj, Qt.MatchExactly):
                self._list.addItem(obj)

    def _remove(self):
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    def items(self):
        return [self._list.item(i).text() for i in range(self._list.count())]

    def clear(self):
        self._list.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 1 — DE BOOR RIBBON
# ─────────────────────────────────────────────────────────────────────────────

class RibbonTab(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Control Objects ───────────────────────────────────────────────────
        cvs_grp = QtWidgets.QGroupBox("Control Objects (CVs — order matters)")
        cvs_lay = QtWidgets.QVBoxLayout(cvs_grp)
        self._cvs = PickListWidget(height=100)
        cvs_lay.addWidget(self._cvs)
        root.addWidget(cvs_grp)

        # ── Parameters ────────────────────────────────────────────────────────
        p_grp = QtWidgets.QGroupBox("Parameters")
        form  = QtWidgets.QFormLayout(p_grp)
        form.setSpacing(6)

        self._name_edit = QtWidgets.QLineEdit("ribbon")
        form.addRow("Name:", self._name_edit)

        self._num_joints = QtWidgets.QSpinBox()
        self._num_joints.setRange(2, 500)
        self._num_joints.setValue(10)
        form.addRow("Num Joints:", self._num_joints)

        self._degree = DegreeRow()
        form.addRow("Degree:", self._degree)

        self._kv_type = QtWidgets.QComboBox()
        self._kv_type.addItems(["open", "periodic"])
        self._kv_type.setToolTip("open = open spline  |  periodic = closed loop")
        form.addRow("Curve Type:", self._kv_type)

        self._aim_axis = QtWidgets.QComboBox()
        self._aim_axis.addItems(["x", "y", "z", "-x", "-y", "-z"])
        form.addRow("Aim Axis:", self._aim_axis)

        self._up_axis = QtWidgets.QComboBox()
        self._up_axis.addItems(["y", "x", "z", "-y", "-x", "-z"])
        form.addRow("Up Axis:", self._up_axis)

        self._by_length = QtWidgets.QCheckBox("Distribute joints by curve length")
        self._by_length.setChecked(True)
        form.addRow("", self._by_length)

        # use_* checkboxes
        use_widget = QtWidgets.QWidget()
        use_lay    = QtWidgets.QHBoxLayout(use_widget)
        use_lay.setContentsMargins(0, 0, 0, 0)
        self._use_pos   = QtWidgets.QCheckBox("Position")
        self._use_tan   = QtWidgets.QCheckBox("Tangent")
        self._use_up    = QtWidgets.QCheckBox("Up")
        self._use_scale = QtWidgets.QCheckBox("Scale")
        self._use_pos.setChecked(True)
        self._use_tan.setChecked(True)
        self._use_up.setChecked(True)
        for cb in (self._use_pos, self._use_tan, self._use_up, self._use_scale):
            use_lay.addWidget(cb)
        use_lay.addStretch()
        form.addRow("Use:", use_widget)

        root.addWidget(p_grp)

        # ── Execute ───────────────────────────────────────────────────────────
        self._run_btn = QtWidgets.QPushButton("Create De Boor Ribbon")
        self._run_btn.setObjectName("primary")
        self._run_btn.setMinimumHeight(34)
        root.addWidget(self._run_btn)

        self._status = _status_label()
        root.addWidget(self._status)
        root.addStretch()

        self._run_btn.clicked.connect(self._run)

    def _run(self):
        cvs = self._cvs.items()
        if len(cvs) < 2:
            self._status.setText("Add at least 2 control objects.")
            return

        from importlib import reload
        from utils import ribbon
        reload(ribbon)

        try:
            jnts = ribbon.de_boor_ribbon(
                cvs             = cvs,
                aim_axis        = self._aim_axis.currentText(),
                up_axis         = self._up_axis.currentText(),
                num_joints      = self._num_joints.value(),
                d               = self._degree.value(),
                kv_type         = self._kv_type.currentText(),
                param_from_length = self._by_length.isChecked(),
                name            = self._name_edit.text().strip() or "ribbon",
                use_position    = self._use_pos.isChecked(),
                use_tangent     = self._use_tan.isChecked(),
                use_up          = self._use_up.isChecked(),
                use_scale       = self._use_scale.isChecked(),
            )
            self._status.setText(f"Done — {len(jnts)} joints created.")
            cmds.inViewMessage(
                amg=f"De Boor Ribbon: <hl>{len(jnts)}</hl> joints.",
                pos="midCenter", fade=True)
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 2 — SPLIT BLENDSHAPE
# ─────────────────────────────────────────────────────────────────────────────

class BlendshapeTab(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        in_grp = QtWidgets.QGroupBox("Inputs")
        form   = QtWidgets.QFormLayout(in_grp)
        form.setSpacing(6)

        self._mesh_edit = QtWidgets.QLineEdit()
        self._mesh_edit.setPlaceholderText("Deformed mesh…")
        form.addRow("Mesh:", _pick_row(self._mesh_edit, lambda: self._pick(self._mesh_edit)))

        self._base_edit = QtWidgets.QLineEdit()
        self._base_edit.setPlaceholderText("Base / neutral mesh…")
        form.addRow("Base Mesh:", _pick_row(self._base_edit, lambda: self._pick(self._base_edit)))

        self._crv_edit = QtWidgets.QLineEdit()
        self._crv_edit.setPlaceholderText("NURBS curve…")
        form.addRow("Curve:", _pick_row(self._crv_edit, lambda: self._pick(self._crv_edit)))

        root.addWidget(in_grp)

        names_grp = QtWidgets.QGroupBox("Output Target Names  (one per line, ≥ 2)")
        names_lay = QtWidgets.QVBoxLayout(names_grp)
        self._names_edit = QtWidgets.QTextEdit()
        self._names_edit.setPlaceholderText("left_bs\ncentre_bs\nright_bs")
        self._names_edit.setFixedHeight(80)
        names_lay.addWidget(self._names_edit)
        root.addWidget(names_grp)

        deg_grp = QtWidgets.QGroupBox("Degree")
        deg_lay = QtWidgets.QHBoxLayout(deg_grp)
        self._degree = DegreeRow(auto_label="Auto (num_outputs − 1)", default=2)
        deg_lay.addWidget(self._degree)
        root.addWidget(deg_grp)

        self._run_btn = QtWidgets.QPushButton("Split Blendshape Targets")
        self._run_btn.setObjectName("primary")
        self._run_btn.setMinimumHeight(34)
        root.addWidget(self._run_btn)

        self._status = _status_label()
        root.addWidget(self._status)
        root.addStretch()

        self._run_btn.clicked.connect(self._run)

    def _pick(self, field):
        sel = cmds.ls(sl=True, long=False)
        if sel:
            field.setText(sel[0])

    def _run(self):
        mesh  = self._mesh_edit.text().strip()
        base  = self._base_edit.text().strip()
        crv   = self._crv_edit.text().strip()
        names = [n.strip() for n in self._names_edit.toPlainText().splitlines() if n.strip()]

        if not all([mesh, base, crv]):
            self._status.setText("Fill in Mesh, Base Mesh and Curve.")
            return
        if len(names) < 2:
            self._status.setText("Need at least 2 output names.")
            return

        from importlib import reload
        from utils import blendshape as bs
        reload(bs)

        try:
            meshes = bs.split_with_curve(mesh, base, crv, names, d=self._degree.value())
            self._status.setText(f"Done — {len(meshes)} targets created.")
            cmds.inViewMessage(
                amg=f"Blendshape split: <hl>{len(meshes)}</hl> targets.",
                pos="midCenter", fade=True)
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 3 — SPLIT SKIN (CURVE)
# ─────────────────────────────────────────────────────────────────────────────

class SkinCurveTab(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        in_grp = QtWidgets.QGroupBox("Inputs")
        form   = QtWidgets.QFormLayout(in_grp)
        form.setSpacing(6)

        self._verts_edit = QtWidgets.QLineEdit()
        self._verts_edit.setPlaceholderText("Mesh name or vertex selection…")
        form.addRow("Verts / Mesh:", _pick_row(self._verts_edit, self._pick_verts))

        self._crv_edit = QtWidgets.QLineEdit()
        self._crv_edit.setPlaceholderText("NURBS curve…")
        form.addRow("Curve:", _pick_row(self._crv_edit, lambda: self._pick_single(self._crv_edit)))

        root.addWidget(in_grp)

        jnts_grp = QtWidgets.QGroupBox("Joints  (in curve order)")
        jnts_lay = QtWidgets.QVBoxLayout(jnts_grp)
        hint = QtWidgets.QLabel("Order defines the De Boor basis — match the sequence of joints along the curve.")
        hint.setObjectName("status")
        hint.setWordWrap(True)
        jnts_lay.addWidget(hint)
        self._jnts = PickListWidget(height=90, node_type="joint")
        jnts_lay.addWidget(self._jnts)
        root.addWidget(jnts_grp)

        opt_grp  = QtWidgets.QGroupBox("Options")
        opt_form = QtWidgets.QFormLayout(opt_grp)
        opt_form.setSpacing(6)

        self._degree = DegreeRow()
        opt_form.addRow("Degree:", self._degree)

        self._tol_spin = QtWidgets.QDoubleSpinBox()
        self._tol_spin.setDecimals(7)
        self._tol_spin.setSingleStep(0.000001)
        self._tol_spin.setValue(0.000001)
        self._tol_spin.setRange(0.0, 1.0)
        opt_form.addRow("Tolerance:", self._tol_spin)

        root.addWidget(opt_grp)

        self._run_btn = QtWidgets.QPushButton("Split Skin Weights")
        self._run_btn.setObjectName("primary")
        self._run_btn.setMinimumHeight(34)
        root.addWidget(self._run_btn)

        self._status = _status_label()
        root.addWidget(self._status)
        root.addStretch()

        self._run_btn.clicked.connect(self._run)

    def _pick_verts(self):
        sel = cmds.ls(sl=True, long=False) or []
        if sel:
            self._verts_edit.setText(sel[0] if len(sel) == 1 else ", ".join(sel))

    def _pick_single(self, field):
        sel = cmds.ls(sl=True, long=False)
        if sel:
            field.setText(sel[0])

    def _run(self):
        raw   = self._verts_edit.text().strip()
        crv   = self._crv_edit.text().strip()
        jnts  = self._jnts.items()

        if not all([raw, crv]):
            self._status.setText("Fill in Verts/Mesh and Curve.")
            return
        if len(jnts) < 2:
            self._status.setText("Add at least 2 joints.")
            return

        verts = [v.strip() for v in raw.split(",") if v.strip()]
        verts = verts[0] if len(verts) == 1 else verts

        from importlib import reload
        from utils import skincluster_curve as skc
        reload(skc)

        try:
            skc.split_with_curve(verts, jnts, crv, d=self._degree.value(), tol=self._tol_spin.value())
            self._status.setText("Done — skin weights redistributed.")
            cmds.inViewMessage(amg="Skin weights split with curve.", pos="midCenter", fade=True)
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 4 — SPLIT SKIN (SURFACE)
# ─────────────────────────────────────────────────────────────────────────────

class SkinSurfaceTab(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        in_grp = QtWidgets.QGroupBox("Inputs")
        form   = QtWidgets.QFormLayout(in_grp)
        form.setSpacing(6)

        self._verts_edit = QtWidgets.QLineEdit()
        self._verts_edit.setPlaceholderText("Mesh name or vertex selection…")
        form.addRow("Verts / Mesh:", _pick_row(self._verts_edit, self._pick_verts))

        self._srf_edit = QtWidgets.QLineEdit()
        self._srf_edit.setPlaceholderText("NURBS surface…")
        form.addRow("Surface:", _pick_row(self._srf_edit, lambda: self._pick_single(self._srf_edit)))

        root.addWidget(in_grp)

        jnts_grp = QtWidgets.QGroupBox("Joints Grid")
        jnts_lay = QtWidgets.QVBoxLayout(jnts_grp)
        hint = QtWidgets.QLabel(
            "One U-row per line. Joints within each row are comma-separated in V order.\n"
            "Example (3×3 grid):\n"
            "  j_00, j_01, j_02\n"
            "  j_10, j_11, j_12\n"
            "  j_20, j_21, j_22"
        )
        hint.setObjectName("status")
        hint.setWordWrap(True)
        jnts_lay.addWidget(hint)
        self._jnts_edit = QtWidgets.QTextEdit()
        self._jnts_edit.setPlaceholderText("j_00, j_01\nj_10, j_11")
        self._jnts_edit.setFixedHeight(90)
        jnts_lay.addWidget(self._jnts_edit)
        root.addWidget(jnts_grp)

        opt_grp  = QtWidgets.QGroupBox("Options")
        opt_form = QtWidgets.QFormLayout(opt_grp)
        opt_form.setSpacing(6)

        self._deg_auto = QtWidgets.QCheckBox("Auto")
        self._deg_auto.setChecked(True)
        self._deg_u = QtWidgets.QSpinBox()
        self._deg_u.setRange(1, 7)
        self._deg_u.setValue(2)
        self._deg_u.setEnabled(False)
        self._deg_v = QtWidgets.QSpinBox()
        self._deg_v.setRange(1, 7)
        self._deg_v.setValue(2)
        self._deg_v.setEnabled(False)
        deg_row = QtWidgets.QWidget()
        deg_rlay = QtWidgets.QHBoxLayout(deg_row)
        deg_rlay.setContentsMargins(0, 0, 0, 0)
        deg_rlay.setSpacing(4)
        deg_rlay.addWidget(QtWidgets.QLabel("U:"))
        deg_rlay.addWidget(self._deg_u)
        deg_rlay.addWidget(QtWidgets.QLabel("V:"))
        deg_rlay.addWidget(self._deg_v)
        deg_rlay.addWidget(self._deg_auto)
        deg_rlay.addStretch()
        opt_form.addRow("Degree:", deg_row)

        self._tol_spin = QtWidgets.QDoubleSpinBox()
        self._tol_spin.setDecimals(7)
        self._tol_spin.setSingleStep(0.000001)
        self._tol_spin.setValue(0.000001)
        self._tol_spin.setRange(0.0, 1.0)
        opt_form.addRow("Tolerance:", self._tol_spin)

        root.addWidget(opt_grp)

        self._run_btn = QtWidgets.QPushButton("Split Skin Weights (Surface)")
        self._run_btn.setObjectName("primary")
        self._run_btn.setMinimumHeight(34)
        root.addWidget(self._run_btn)

        self._status = _status_label()
        root.addWidget(self._status)
        root.addStretch()

        self._deg_auto.toggled.connect(self._toggle_deg)
        self._run_btn.clicked.connect(self._run)

    def _toggle_deg(self, checked):
        self._deg_u.setEnabled(not checked)
        self._deg_v.setEnabled(not checked)

    def _pick_verts(self):
        sel = cmds.ls(sl=True, long=False) or []
        if sel:
            self._verts_edit.setText(sel[0] if len(sel) == 1 else ", ".join(sel))

    def _pick_single(self, field):
        sel = cmds.ls(sl=True, long=False)
        if sel:
            field.setText(sel[0])

    def _parse_grid(self):
        lines = [l.strip() for l in self._jnts_edit.toPlainText().splitlines() if l.strip()]
        return [[j.strip() for j in line.split(",") if j.strip()] for line in lines]

    def _run(self):
        raw  = self._verts_edit.text().strip()
        srf  = self._srf_edit.text().strip()
        jnts = self._parse_grid()

        if not all([raw, srf]):
            self._status.setText("Fill in Verts/Mesh and Surface.")
            return
        if len(jnts) < 2:
            self._status.setText("Need at least 2 U-rows of joints.")
            return

        verts = [v.strip() for v in raw.split(",") if v.strip()]
        verts = verts[0] if len(verts) == 1 else verts

        d = None if self._deg_auto.isChecked() else [self._deg_u.value(), self._deg_v.value()]

        from importlib import reload
        from utils import skincluster_surface as sks
        reload(sks)

        try:
            sks.split_with_surface(verts, jnts, srf, d=d, tol=self._tol_spin.value())
            self._status.setText("Done — skin weights redistributed.")
            cmds.inViewMessage(amg="Skin weights split with surface.", pos="midCenter", fade=True)
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

_window_instance = None


class DeBoorToolsUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle("De Boor Tools")
        self.setMinimumWidth(440)
        self.setMinimumHeight(520)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self._build_ui()
        ui_utils.apply_maya_style(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.addTab(RibbonTab(),      "De Boor Ribbon")
        self._tabs.addTab(BlendshapeTab(),  "Split Blendshape")
        self._tabs.addTab(SkinCurveTab(),   "Skin — Curve")
        self._tabs.addTab(SkinSurfaceTab(), "Skin — Surface")

        root.addWidget(self._tabs)

    def set_tab(self, index):
        self._tabs.setCurrentIndex(index)


def show(tab=0):
    global _window_instance
    if _window_instance is not None:
        try:
            _window_instance.close()
            _window_instance.deleteLater()
        except Exception:
            pass
    _window_instance = DeBoorToolsUI()
    _window_instance.set_tab(tab)
    _window_instance.show()
