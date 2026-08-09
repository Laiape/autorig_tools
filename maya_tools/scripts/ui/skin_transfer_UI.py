"""
skin_transfer_UI.py
===================
PySide6/2 UI for the Auto Skin Transfer system.

Launch from Maya Script Editor:
    from ui import skin_transfer_UI
    from importlib import reload
    reload(skin_transfer_UI)
    skin_transfer_UI.show()

Or from the AutoRig Tools menu → Skin Cluster Manager → Auto Skin Transfer.
"""

import os
from importlib import reload

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Qt, Signal
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Qt, Signal
    from shiboken2 import wrapInstance

from maya_tools.scripts.utils import ui_utils


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


# ─────────────────────────────────────────────────────────────────────────────
#  STYLE
# ─────────────────────────────────────────────────────────────────────────────

_STYLE = """
QDialog, QWidget {
    background-color: #2b2b2b;
    color: #cccccc;
    font-size: 12px;
}
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
QComboBox {
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px 6px;
    color: #dddddd;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: #2b2b2b; selection-background-color: #1a5fa8; }
QSpinBox {
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 2px 4px;
    color: #dddddd;
}
QCheckBox { color: #cccccc; }
QCheckBox::indicator { width: 14px; height: 14px; }
QProgressBar {
    background: #1e1e1e;
    border: 1px solid #444;
    border-radius: 3px;
    text-align: center;
    color: #cccccc;
}
QProgressBar::chunk { background: #1a5fa8; border-radius: 2px; }
QLabel#status { color: #888888; font-style: italic; }
QLabel#sectionLabel { color: #4a9eff; font-weight: bold; }
QTextEdit {
    background: #1a1a1a;
    border: 1px solid #444;
    border-radius: 3px;
    color: #aaaaaa;
    font-family: Consolas, monospace;
    font-size: 11px;
}
QScrollArea { border: none; background: transparent; }
"""


# ─────────────────────────────────────────────────────────────────────────────
#  COLLAPSIBLE SECTION WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class CollapsibleSection(QtWidgets.QWidget):
    def __init__(self, title, parent=None, start_open=True):
        super().__init__(parent)
        self._open = start_open

        self._btn = QtWidgets.QPushButton(("▼ " if start_open else "▶ ") + title)
        self._btn.setCheckable(True)
        self._btn.setChecked(start_open)
        self._btn.setStyleSheet(
            "QPushButton { text-align:left; background:#333; border:none; "
            "color:#aaa; font-weight:bold; padding:4px 6px; border-radius:3px;}"
            "QPushButton:hover { background:#3c3c3c; color:#ddd; }"
        )
        self._btn.toggled.connect(self._toggle)

        self._content = QtWidgets.QWidget()
        self._content.setVisible(start_open)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._btn)
        layout.addWidget(self._content)

    def set_content_layout(self, layout):
        self._content.setLayout(layout)

    def _toggle(self, checked):
        self._content.setVisible(checked)
        self._btn.setText(("▼ " if checked else "▶ ") + self._btn.text()[2:])


# ─────────────────────────────────────────────────────────────────────────────
#  JOINT MAP DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class JointMapDialog(QtWidgets.QDialog):
    def __init__(self, joint_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Joint Mapping")
        self.setMinimumSize(500, 400)

        table = QtWidgets.QTableWidget(len(joint_map), 2)
        table.setHorizontalHeaderLabels(["Source Joint", "Target Joint"])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("QTableWidget { background:#1e1e1e; alternate-background-color:#252525; }"
                            "QHeaderView::section { background:#333; color:#aaa; padding:4px; }")

        for row, (src, tgt) in enumerate(joint_map.items()):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(src))
            item = QtWidgets.QTableWidgetItem(tgt or "⚠ UNMAPPED")
            if not tgt:
                item.setForeground(QtGui.QColor("#e05555"))
            table.setItem(row, 1, item)

        btn = QtWidgets.QPushButton("Close")
        btn.clicked.connect(self.accept)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(table)
        lay.addWidget(btn)
        ui_utils.apply_maya_style(self)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class SkinTransferUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle("Auto Skin Transfer")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)

        self._joint_map  = {}   # filled after preview
        self._system     = None # lazy import

        self._build_ui()
        self._connect_signals()
        ui_utils.apply_maya_style(self)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        scroll_area   = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(6)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_layout.addWidget(self._section_source())
        scroll_layout.addWidget(self._section_target())
        scroll_layout.addWidget(self._section_uv())
        scroll_layout.addWidget(self._section_joints())
        scroll_layout.addWidget(self._section_refinement())
        scroll_layout.addWidget(self._section_io())
        scroll_layout.addStretch()

        root.addWidget(scroll_area)
        root.addWidget(self._section_transfer())

    # ── sections ─────────────────────────────────────────────────────────────

    def _section_source(self):
        sec = CollapsibleSection("  SOURCE  —  well-skinned mesh")
        lay = QtWidgets.QFormLayout()
        lay.setSpacing(6)

        self._src_field = QtWidgets.QLineEdit()
        self._src_field.setPlaceholderText("Type or pick from viewport…")
        src_row = self._pick_row(self._src_field, self._pick_source)
        lay.addRow("Mesh:", src_row)

        self._src_skin_label = QtWidgets.QLabel("—")
        self._src_skin_label.setStyleSheet("color:#666; font-style:italic;")
        lay.addRow("Skin:", self._src_skin_label)

        # ── .skc file (optional) ──────────────────────────────────────
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("color:#3a3a3a; margin:2px 0;")
        lay.addRow(sep)

        self._skc_field = QtWidgets.QLineEdit()
        self._skc_field.setPlaceholderText("Optional: load weights from .skc export…")
        skc_row = self._pick_row(self._skc_field, self._pick_skc_file,
                                 btn_label="…", btn_width=26)
        lay.addRow(".skc file:", skc_row)

        self._skc_clear_btn = QtWidgets.QPushButton("✕ Clear")
        self._skc_clear_btn.setFixedWidth(62)
        self._skc_clear_btn.setStyleSheet(
            "QPushButton { color:#888; background:transparent; border:none; "
            "font-size:11px;} QPushButton:hover{color:#e05555;}"
        )
        self._skc_status = QtWidgets.QLabel("Skin will be read live from scene.")
        self._skc_status.setObjectName("status")
        skc_info = QtWidgets.QHBoxLayout()
        skc_info.addWidget(self._skc_status)
        skc_info.addStretch()
        skc_info.addWidget(self._skc_clear_btn)
        lay.addRow("", skc_info)

        sec.set_content_layout(lay)
        return sec

    def _section_target(self):
        sec = CollapsibleSection("  TARGET  —  mesh to receive skinning")
        lay = QtWidgets.QFormLayout()
        lay.setSpacing(6)

        self._tgt_field = QtWidgets.QLineEdit()
        self._tgt_field.setPlaceholderText("Type or pick from viewport…")
        tgt_row = self._pick_row(self._tgt_field, self._pick_target)
        lay.addRow("Mesh:", tgt_row)

        self._root_field = QtWidgets.QLineEdit()
        self._root_field.setPlaceholderText("Auto-detected from source skin…")
        root_row = self._pick_row(self._root_field, self._pick_root_joint)
        lay.addRow("Root joint:", root_row)

        sec.set_content_layout(lay)
        return sec

    def _section_uv(self):
        sec = CollapsibleSection("  UV PROJECTION")
        lay = QtWidgets.QFormLayout()
        lay.setSpacing(6)

        self._uv_method = QtWidgets.QComboBox()
        self._uv_method.addItems(["skeleton", "cylindrical", "planar"])
        self._uv_method.setToolTip(
            "skeleton  — bone-relative (recommended, scale/topology independent)\n"
            "cylindrical — Maya built-in cylinder along main skeleton axis\n"
            "planar    — Maya built-in planar along Y"
        )
        lay.addRow("Method:", self._uv_method)

        self._keep_uvs = QtWidgets.QCheckBox("Keep temp UVs for debug")
        lay.addRow("", self._keep_uvs)

        sec.set_content_layout(lay)
        return sec

    def _section_joints(self):
        sec = CollapsibleSection("  JOINT MAPPING")
        lay = QtWidgets.QFormLayout()
        lay.setSpacing(6)

        self._jmap_strategy = QtWidgets.QComboBox()
        self._jmap_strategy.addItems(["auto", "name", "proximity"])
        self._jmap_strategy.setToolTip(
            "auto      — name first, proximity fallback\n"
            "name      — normalised name matching only\n"
            "proximity — closest world-space joint"
        )
        lay.addRow("Strategy:", self._jmap_strategy)

        self._preview_map_btn = QtWidgets.QPushButton("Preview Joint Map…")
        lay.addRow("", self._preview_map_btn)

        sec.set_content_layout(lay)
        return sec

    def _section_refinement(self):
        sec = CollapsibleSection("  REFINEMENT")
        lay = QtWidgets.QFormLayout()
        lay.setSpacing(6)

        # Max influences
        max_row = QtWidgets.QHBoxLayout()
        self._do_max_inf = QtWidgets.QCheckBox("Limit influences")
        self._do_max_inf.setChecked(True)
        self._max_infs = QtWidgets.QSpinBox()
        self._max_infs.setRange(1, 16); self._max_infs.setValue(4)
        self._max_infs.setFixedWidth(55)
        max_row.addWidget(self._do_max_inf)
        max_row.addStretch()
        max_row.addWidget(QtWidgets.QLabel("Max:"))
        max_row.addWidget(self._max_infs)
        lay.addRow("", max_row)

        # Smooth
        smooth_row = QtWidgets.QHBoxLayout()
        self._do_smooth = QtWidgets.QCheckBox("Smooth weights")
        self._do_smooth.setChecked(True)
        self._smooth_iter = QtWidgets.QSpinBox()
        self._smooth_iter.setRange(0, 20); self._smooth_iter.setValue(3)
        self._smooth_iter.setFixedWidth(55)
        smooth_row.addWidget(self._do_smooth)
        smooth_row.addStretch()
        smooth_row.addWidget(QtWidgets.QLabel("Iter:"))
        smooth_row.addWidget(self._smooth_iter)
        lay.addRow("", smooth_row)

        # Critical zones
        self._do_boost = QtWidgets.QCheckBox(
            "Boost critical zones (elbows, knees…)"
        )
        self._do_boost.setChecked(True)
        lay.addRow("", self._do_boost)

        sec.set_content_layout(lay)
        return sec

    def _section_io(self):
        sec = CollapsibleSection("  SAVE / LOAD SKIN MAP", start_open=False)
        lay = QtWidgets.QVBoxLayout()
        lay.setSpacing(4)

        self._map_path_field = QtWidgets.QLineEdit()
        self._map_path_field.setPlaceholderText("Optional: .skinmap file path…")
        lay.addWidget(self._map_path_field)

        btn_row = QtWidgets.QHBoxLayout()
        self._save_map_btn = QtWidgets.QPushButton("Save Map")
        self._load_map_btn = QtWidgets.QPushButton("Load Map")
        self._browse_btn   = QtWidgets.QPushButton("Browse…")
        btn_row.addWidget(self._save_map_btn)
        btn_row.addWidget(self._load_map_btn)
        btn_row.addWidget(self._browse_btn)
        lay.addLayout(btn_row)

        self._map_status = QtWidgets.QLabel("No map loaded")
        self._map_status.setObjectName("status")
        lay.addWidget(self._map_status)

        sec.set_content_layout(lay)
        return sec

    def _section_transfer(self):
        """Bottom transfer bar — always visible."""
        w   = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(4)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("color:#444")
        lay.addWidget(sep)

        self._transfer_btn = QtWidgets.QPushButton("TRANSFER SKINNING")
        self._transfer_btn.setObjectName("primary")
        self._transfer_btn.setMinimumHeight(38)
        lay.addWidget(self._transfer_btn)

        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(14)
        lay.addWidget(self._progress)

        self._status_label = QtWidgets.QLabel("Ready.")
        self._status_label.setObjectName("status")
        self._status_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._status_label)

        return w

    # ── helpers ──────────────────────────────────────────────────────────────

    def _pick_row(self, line_edit, callback, btn_label="Pick", btn_width=44):
        """Returns an HBox with a QLineEdit and an action button."""
        w   = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        btn = QtWidgets.QPushButton(btn_label)
        btn.setFixedWidth(btn_width)
        btn.clicked.connect(callback)
        lay.addWidget(line_edit)
        lay.addWidget(btn)
        return w

    # ── signals ──────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._src_field.editingFinished.connect(self._update_skin_label)
        self._skc_field.editingFinished.connect(self._update_skc_status)
        self._skc_clear_btn.clicked.connect(self._clear_skc)
        self._transfer_btn.clicked.connect(self._on_transfer)
        self._preview_map_btn.clicked.connect(self._on_preview_map)
        self._save_map_btn.clicked.connect(self._on_save_map)
        self._load_map_btn.clicked.connect(self._on_load_map)
        self._browse_btn.clicked.connect(self._on_browse)
        self._do_max_inf.toggled.connect(self._max_infs.setEnabled)
        self._do_smooth.toggled.connect(self._smooth_iter.setEnabled)

    # ── slot implementations ──────────────────────────────────────────────────

    def _pick_skc_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load .skc Export", "", "Skin Cluster Export (*.skc);;All Files (*)"
        )
        if path:
            self._skc_field.setText(path)
            self._update_skc_status()

    def _update_skc_status(self):
        path = self._skc_field.text().strip()
        if not path:
            self._skc_status.setText("Skin will be read live from scene.")
            self._skc_status.setStyleSheet("color:#888; font-style:italic;")
            return
        import os
        if os.path.exists(path):
            import json
            try:
                with open(path) as f:
                    data = json.load(f)
                meshes = list(data.keys())
                first_infs = len(data[meshes[0]][0].get("influences", []))
                self._skc_status.setText(
                    f"✔  {os.path.basename(path)}  "
                    f"({len(meshes)} mesh{'es' if len(meshes)>1 else ''}, "
                    f"{first_infs} influences)"
                )
                self._skc_status.setStyleSheet("color:#5aaa5a; font-style:normal;")
            except Exception:
                self._skc_status.setText(f"✔  {os.path.basename(path)}")
                self._skc_status.setStyleSheet("color:#5aaa5a;")
        else:
            self._skc_status.setText("⚠  File not found")
            self._skc_status.setStyleSheet("color:#e05555;")

    def _clear_skc(self):
        self._skc_field.clear()
        self._update_skc_status()

    def _pick_source(self):
        sel = cmds.ls(sl=True, transforms=True)
        if sel:
            self._src_field.setText(sel[0])
            self._update_skin_label()
        else:
            self._warn("Select a mesh first.")

    def _pick_target(self):
        sel = cmds.ls(sl=True, transforms=True)
        if sel:
            self._tgt_field.setText(sel[0])
        else:
            self._warn("Select a mesh first.")

    def _pick_root_joint(self):
        sel = cmds.ls(sl=True, type="joint")
        if sel:
            self._root_field.setText(sel[0])
        else:
            self._warn("Select a joint first.")

    def _update_skin_label(self):
        mesh = self._src_field.text().strip()
        if not mesh or not cmds.objExists(mesh):
            self._src_skin_label.setText("—")
            return
        shapes = cmds.listRelatives(mesh, shapes=True) or [mesh]
        hist   = cmds.listHistory(shapes[0], pruneDagObjects=True, interestLevel=1) or []
        skins  = [n for n in hist if cmds.nodeType(n) == "skinCluster"]
        if skins:
            self._src_skin_label.setText(skins[-1])
            self._src_skin_label.setStyleSheet("color:#5aaa5a;")
        else:
            self._src_skin_label.setText("No skinCluster found")
            self._src_skin_label.setStyleSheet("color:#e05555;")

    def _on_preview_map(self):
        """Runs joint mapping without transfer and shows the dialog."""
        src  = self._src_field.text().strip()
        tgt  = self._tgt_field.text().strip()
        root = self._root_field.text().strip() or None

        if not src or not tgt:
            self._warn("Fill in source and target meshes first.")
            return

        sys = self._get_system()
        src_skin = sys._find_skin(src)
        if not src_skin:
            self._warn(f"No skinCluster on '{src}'"); return

        if not root:
            root = sys._find_root_joint(src_skin)
        if not root:
            self._warn("Could not detect root joint."); return

        src_joints = cmds.skinCluster(src_skin, q=True, influence=True) or []
        tgt_joints = ([root] +
                      (cmds.listRelatives(root, allDescendents=True, type="joint") or []))
        strategy   = self._jmap_strategy.currentText()

        self._joint_map = sys.joint_mod.map(src_joints, tgt_joints, strategy)
        dlg = JointMapDialog(self._joint_map, self)
        dlg.exec_()

    def _on_transfer(self):
        src  = self._src_field.text().strip()
        tgt  = self._tgt_field.text().strip()
        root = self._root_field.text().strip() or None

        if not src or not tgt:
            self._warn("Source and target meshes are required.")
            return

        self._set_progress(0, "Starting…")
        self._transfer_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        map_path = self._map_path_field.text().strip() or None
        skc_path = self._skc_field.text().strip() or None

        try:
            sys = self._get_system()
            result = sys.transfer(
                source_mesh     = src,
                target_mesh     = tgt,
                root_joint      = root,
                uv_method       = self._uv_method.currentText(),
                joint_strategy  = self._jmap_strategy.currentText(),
                smooth_iter     = self._smooth_iter.value() if self._do_smooth.isChecked() else 0,
                max_infs        = self._max_infs.value()    if self._do_max_inf.isChecked() else 0,
                boost_critical  = self._do_boost.isChecked(),
                cleanup_uvs     = not self._keep_uvs.isChecked(),
                skin_map_path   = map_path,
                source_skc_path = skc_path,
                progress_cb     = self._on_progress,
            )

            if result:
                self._set_progress(100, f"Done — skin: {result}")
                cmds.inViewMessage(
                    amg=f"Skin Transfer complete: <hl>{result}</hl>",
                    pos="midCenter", fade=True
                )
            else:
                self._set_progress(0, "Transfer failed — see Script Editor.")

        except Exception as e:
            self._set_progress(0, f"Error: {e}")
            import traceback; traceback.print_exc()
        finally:
            self._transfer_btn.setEnabled(True)

    def _on_progress(self, pct, msg):
        self._set_progress(pct, msg)
        QtWidgets.QApplication.processEvents()

    def _on_save_map(self):
        path = self._map_path_field.text().strip()
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Skin Map", "", "Skin Map (*.skinmap);;JSON (*.json)"
            )
        if not path:
            return
        if not path.endswith((".skinmap", ".json")):
            path += ".skinmap"

        src = self._src_field.text().strip()
        if not src:
            self._warn("Set source mesh first."); return

        sys_     = self._get_system()
        src_skin = sys_._find_skin(src)
        root     = self._root_field.text().strip() or sys_._find_root_joint(src_skin)
        if not root:
            self._warn("Cannot detect root joint."); return

        joint_data = sys_.zone_analyzer.analyze(root)
        if not sys_.uv_mod.build(src, src, joint_data, self._uv_method.currentText()):
            return
        try:
            u, v       = sys_.uv_mod.get_uv_coords(src)
            skin_map   = sys_.sample_mod.build_map(src, src_skin, u, v)
            if skin_map:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                skin_map.save(path)
                self._map_path_field.setText(path)
                self._map_status.setText(f"Saved: {os.path.basename(path)}")
        finally:
            sys_.uv_mod.cleanup(src)

    def _on_load_map(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Skin Map", "", "Skin Map (*.skinmap);;JSON (*.json)"
        )
        if path:
            self._map_path_field.setText(path)
            self._map_status.setText(f"Loaded: {os.path.basename(path)}")

    def _on_browse(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Skin Map Path", "", "Skin Map (*.skinmap);;JSON (*.json)"
        )
        if path:
            self._map_path_field.setText(path)

    # ── utils ────────────────────────────────────────────────────────────────

    def _set_progress(self, pct, msg):
        self._progress.setValue(int(pct))
        self._status_label.setText(msg)

    def _warn(self, msg):
        self._status_label.setText(f"⚠  {msg}")
        cmds.warning(msg)

    def _get_system(self):
        from maya_tools.scripts.tools import auto_skin_transfer
        reload(auto_skin_transfer)
        return auto_skin_transfer.AutoSkinTransferSystem()


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

_window_instance = None

def show():
    global _window_instance
    if _window_instance is not None:
        try:
            _window_instance.close()
            _window_instance.deleteLater()
        except Exception:
            pass
    _window_instance = SkinTransferUI()
    _window_instance.show()
    _window_instance.raise_()
    return _window_instance
