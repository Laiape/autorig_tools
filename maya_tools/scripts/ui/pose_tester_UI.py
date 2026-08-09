"""
pose_tester_UI.py
=================
PySide6/2 UI for the Rig Pose Tester (ROM) integrated with AutoRig Tools.

Una fila por zona del cuerpo (Spine, Neck/Head, Clavicle, Shoulder, Elbow,
Wrist, Fingers, Hip, Knee, Ankle/Foot) con un desplegable de poses ROM:
al elegir una pose en el desplegable (o pulsar su botón de play) se anima
esa pose en los controladores del rig, con keys aisladas por eje que
vuelven a neutral entre extremos (flujo ROM estándar de producción).

Launch from Maya Script Editor:
    from ui import pose_tester_UI
    from importlib import reload
    reload(pose_tester_UI)
    pose_tester_UI.show()
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

from maya_tools.scripts.utils import ui_utils
from maya_tools.scripts.tools import pose_tester


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


_SIDES = {
    "Both": ("L", "R"),
    "Left (L)": ("L",),
    "Right (R)": ("R",),
}


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

_window_instance = None


class PoseTesterUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle("Rig Pose Tester — ROM")
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self._zone_combos = {}
        self._build_ui()
        ui_utils.apply_maya_style(self)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        info = QtWidgets.QLabel(
            "Range of Motion test: keys every N frames, one axis at a time,\n"
            "always returning to neutral between extremes.")
        info.setAlignment(Qt.AlignCenter)
        root.addWidget(info)

        root.addWidget(self._build_options_group())
        root.addWidget(self._build_zones_group())

        # ── acciones globales ────────────────────────────────────────────────
        actions = QtWidgets.QHBoxLayout()
        self._full_btn = QtWidgets.QPushButton("Full Body ROM")
        self._full_btn.setObjectName("primary")
        self._full_btn.clicked.connect(self._on_full_body)
        actions.addWidget(self._full_btn, 2)

        self._clear_btn = QtWidgets.QPushButton("Clear Test Anim")
        self._clear_btn.clicked.connect(self._on_clear)
        actions.addWidget(self._clear_btn, 1)
        root.addLayout(actions)

        self._status = QtWidgets.QLabel("")
        self._status.setObjectName("status")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        root.addWidget(self._status)

    def _build_options_group(self):
        group = QtWidgets.QGroupBox("Options")
        lay = QtWidgets.QHBoxLayout(group)
        lay.setSpacing(8)

        lay.addWidget(QtWidgets.QLabel("Side:"))
        self._side_combo = QtWidgets.QComboBox()
        self._side_combo.addItems(list(_SIDES.keys()))
        lay.addWidget(self._side_combo)

        lay.addWidget(QtWidgets.QLabel("Spacing:"))
        self._spacing_spin = QtWidgets.QSpinBox()
        self._spacing_spin.setRange(2, 50)
        self._spacing_spin.setValue(pose_tester.DEFAULT_SPACING)
        self._spacing_spin.setSuffix(" f")
        lay.addWidget(self._spacing_spin)

        lay.addWidget(QtWidgets.QLabel("Start:"))
        self._start_spin = QtWidgets.QSpinBox()
        self._start_spin.setRange(0, 100000)
        self._start_spin.setValue(pose_tester.DEFAULT_START)
        lay.addWidget(self._start_spin)

        self._fk_check = QtWidgets.QCheckBox("Auto FK")
        self._fk_check.setChecked(True)
        self._fk_check.setToolTip(
            "Switch Ik_Fk to FK on the tested limbs before keying.")
        lay.addWidget(self._fk_check)

        self._play_check = QtWidgets.QCheckBox("Play")
        self._play_check.setChecked(True)
        self._play_check.setToolTip("Play the timeline after keying.")
        lay.addWidget(self._play_check)

        lay.addStretch()
        return group

    def _build_zones_group(self):
        group = QtWidgets.QGroupBox("Body Zones — pick a pose to animate it")
        grid = QtWidgets.QGridLayout(group)
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        for row, zone in enumerate(pose_tester.ZONES):
            label = QtWidgets.QLabel(zone)
            label.setMinimumWidth(90)
            grid.addWidget(label, row, 0)

            combo = QtWidgets.QComboBox()
            combo.addItems(pose_tester.pose_labels(zone))
            combo.setCurrentIndex(combo.count() - 1)  # Full ROM por defecto
            # `activated` solo salta con interacción del usuario: elegir una
            # pose en el desplegable la anima directamente.
            combo.activated.connect(
                lambda index, z=zone: self._on_animate(z, index))
            self._zone_combos[zone] = combo
            grid.addWidget(combo, row, 1)

            play_btn = QtWidgets.QPushButton("▶")
            play_btn.setFixedWidth(30)
            play_btn.setToolTip(f"Animate the selected {zone} pose")
            play_btn.clicked.connect(
                lambda checked=False, z=zone: self._on_animate(
                    z, self._zone_combos[z].currentIndex()))
            grid.addWidget(play_btn, row, 2)

        return group

    # ── SLOTS ────────────────────────────────────────────────────────────────

    def _sides(self):
        return _SIDES[self._side_combo.currentText()]

    def _on_animate(self, zone, pose_index):
        label = pose_tester.pose_labels(zone)[pose_index]
        try:
            end = pose_tester.animate_pose(
                zone, pose_index,
                sides=self._sides(),
                spacing=self._spacing_spin.value(),
                start_frame=self._start_spin.value(),
                set_fk=self._fk_check.isChecked(),
                play=self._play_check.isChecked())
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise

        if end is None:
            self._status.setText(
                f"{zone}: no controls found in scene — build the rig first.")
            return
        self._status.setText(f"{zone} — {label}   ·   keys up to frame {int(end)}")

    def _on_full_body(self):
        try:
            end = pose_tester.animate_full_body(
                sides=self._sides(),
                spacing=self._spacing_spin.value(),
                start_frame=self._start_spin.value(),
                set_fk=self._fk_check.isChecked(),
                play=self._play_check.isChecked())
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise

        if end is None:
            self._status.setText(
                "No controls found in scene — build the rig first.")
            return
        self._status.setText(
            f"Full Body ROM   ·   keys up to frame {int(end)}")
        cmds.inViewMessage(amg="Full Body ROM animado.",
                           pos="midCenter", fade=True)

    def _on_clear(self):
        try:
            cleared = pose_tester.clear_test()
        except Exception as e:
            self._status.setText(f"Error: {e}")
            raise
        self._status.setText(
            f"Test animation cleared ({cleared} channels reset).")
        cmds.inViewMessage(amg="Animación de test borrada.",
                           pos="midCenter", fade=True)


def show():
    global _window_instance
    if _window_instance is not None:
        try:
            _window_instance.close()
            _window_instance.deleteLater()
        except Exception:
            pass
    _window_instance = PoseTesterUI()
    _window_instance.show()
