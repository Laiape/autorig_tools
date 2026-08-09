"""
RigProgressDialog — progress window shown during AutoRig build.
Light theme. Auto-closes 2 s after finish, or via the close button.
"""
import os

import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

from maya.scripts.utils import ui_utils

# ── Maya-grey palette ─────────────────────────────────────────────────────────
C_WHITE  = "#b0b0b0"   # medium-dark grey — main bg
C_PANEL  = "#a2a2a2"   # body panel bg
C_HOVER  = "#949494"   # hover
C_BORDER = "#808080"   # borders
C_TEXT   = "#1a1a1a"   # main text
C_DIM    = "#555555"   # dim / secondary text
C_ACCENT = "#2667a6"   # dark blue — text / borders
C_LIME   = "#5b9bd5"   # medium blue — bar fill / highlights


def _root_path():
    here = os.path.realpath(__file__)
    sep = os.sep + "scripts"
    return here.split(sep)[0] if sep in here else os.path.dirname(os.path.dirname(os.path.dirname(here)))


def _find_thumbnail(asset_name):
    d = os.path.join(_root_path(), "assets", asset_name)
    for name in ("thumbnail.jpg", "thumbnail.png",
                 f"{asset_name}.jpg", f"{asset_name}.png"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def _find_icon(icon_name):
    icons_dir = os.path.join(_root_path(), "icons")
    for ext in (".png", ".jpg", ".svg"):
        p = os.path.join(icons_dir, icon_name + ext)
        if os.path.exists(p):
            return p
    return None


def _main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class RigProgressDialog(QtWidgets.QDialog):
    """
    Non-blocking progress dialog for the AutoRig build pipeline.
    Auto-closes 2 s after finish(); a close button also appears.
    """

    def __init__(self, asset_name, mgear=False, parent=None):
        super().__init__(parent or _main_window())
        self.setWindowTitle(f"Building  {asset_name}…")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.CustomizeWindowHint
            | QtCore.Qt.WindowTitleHint
        )
        self.setFixedWidth(440)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self._build_ui(asset_name, mgear)
        self.adjustSize()
        ui_utils.apply_maya_style(self)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self, asset_name, mgear):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        hdr = QtWidgets.QWidget()
        hdr.setStyleSheet(f"background:{C_WHITE}; border-bottom:1px solid {C_BORDER};")
        hdr.setFixedHeight(76)
        h = QtWidgets.QHBoxLayout(hdr)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(14)

        # thumbnail
        thumb = QtWidgets.QLabel()
        thumb.setFixedSize(52, 52)
        thumb.setAlignment(QtCore.Qt.AlignCenter)
        thumb.setStyleSheet(f"""
            background:{C_PANEL}; border:1px solid {C_BORDER}; border-radius:4px;
            color:{C_DIM}; font-size:8px; letter-spacing:1px;
        """)
        tp = _find_thumbnail(asset_name)
        if tp:
            pix = QtGui.QPixmap(tp).scaled(
                52, 52, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            thumb.setPixmap(pix)
        else:
            thumb.setText("NO\nIMG")
        h.addWidget(thumb)

        # asset name + status
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(4)
        lbl_name = QtWidgets.QLabel(asset_name.upper())
        lbl_name.setStyleSheet(
            f"color:{C_ACCENT}; font-size:12px; font-weight:bold; letter-spacing:3px;")
        lbl_sub = QtWidgets.QLabel("BUILDING RIG…")
        lbl_sub.setStyleSheet(
            f"color:{C_DIM}; font-size:8px; font-weight:bold; letter-spacing:4px;")
        col.addWidget(lbl_name)
        col.addWidget(lbl_sub)
        h.addLayout(col, 1)

        # mGear icon (only when integration is active)
        if mgear:
            ip = _find_icon("mgear")
            if ip:
                ml = QtWidgets.QLabel()
                ml.setFixedSize(46, 46)
                ml.setAlignment(QtCore.Qt.AlignCenter)
                ml.setToolTip("mGear integration enabled")
                mp = QtGui.QPixmap(ip).scaled(
                    46, 46, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                ml.setPixmap(mp)
                h.addWidget(ml)

        root.addWidget(hdr)

        # body
        body = QtWidgets.QWidget()
        body.setStyleSheet(f"background:{C_PANEL};")
        b = QtWidgets.QVBoxLayout(body)
        b.setContentsMargins(16, 14, 16, 14)
        b.setSpacing(8)

        step_row = QtWidgets.QHBoxLayout()
        step_row.setSpacing(8)
        self._step_lbl = QtWidgets.QLabel("INITIALIZING…")
        self._step_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:10px; font-weight:bold; letter-spacing:1px;")
        self._pct_lbl = QtWidgets.QLabel("0%")
        self._pct_lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:10px; font-weight:bold; letter-spacing:1px;")
        self._pct_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        step_row.addWidget(self._step_lbl, 1)
        step_row.addWidget(self._pct_lbl)
        b.addLayout(step_row)

        self._bar = QtWidgets.QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        b.addWidget(self._bar)

        # bottom row: time label + close button
        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(8)

        self._time_lbl = QtWidgets.QLabel("")
        self._time_lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:18px; font-weight:bold; letter-spacing:2px;")
        bottom.addWidget(self._time_lbl, 1)

        self._close_btn = QtWidgets.QPushButton("CLOSE")
        self._close_btn.setObjectName("close_btn")
        self._close_btn.setVisible(False)
        self._close_btn.setFixedHeight(26)
        self._close_btn.clicked.connect(self.hide)
        bottom.addWidget(self._close_btn)

        b.addLayout(bottom)
        root.addWidget(body)

    # ── public API ────────────────────────────────────────────────────────────

    def _set_pct(self, label, pct):
        """Update label, percentage, and bar (0-100), then flush Qt events."""
        self._step_lbl.setText(label.upper())
        self._pct_lbl.setText(f"{int(pct)}%")
        self._bar.setValue(int(pct))
        QtWidgets.QApplication.processEvents()

    def set_step(self, label, current, total):
        pct = int(current / max(total, 1) * 100)
        self._set_pct(label, pct)

    def finish(self, elapsed_seconds):
        """Mark complete, show elapsed time, reveal close button, schedule auto-close."""
        self._step_lbl.setText("BUILD COMPLETE.")
        self._pct_lbl.setText("100%")
        self._bar.setValue(100)
        m = int(elapsed_seconds // 60)
        s = elapsed_seconds % 60
        t = f"{m}M {s:.1f}S" if m else f"{s:.1f}S"
        self._time_lbl.setText(t)
        self._close_btn.setVisible(True)
        QtWidgets.QApplication.processEvents()
        QtCore.QTimer.singleShot(3000, self.hide)
