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
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None


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
        content = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        root.addWidget(scroll)
        root = QtWidgets.QVBoxLayout(content)
        self.resize(640, 820)

        info = QtWidgets.QLabel(
            "Range of Motion test: keys every N frames, one axis at a time,\n"
            "always returning to neutral between extremes.")
        info.setAlignment(Qt.AlignCenter)
        root.addWidget(info)

        root.addWidget(self._build_options_group())
        root.addWidget(self._build_zones_group())
        report_group = QtWidgets.QGroupBox("Build comparison")
        report_layout = QtWidgets.QVBoxLayout(report_group)
        self._report_meshes = []
        self._report_mesh_label = QtWidgets.QLabel("Select meshes from one character, then load them.")
        self._report_mesh_label.setWordWrap(True)
        report_layout.addWidget(self._report_mesh_label)
        buttons = QtWidgets.QHBoxLayout()
        load_meshes = QtWidgets.QPushButton("Load selected meshes")
        load_meshes.clicked.connect(self._load_report_meshes)
        buttons.addWidget(load_meshes)
        report_button = QtWidgets.QPushButton("Combination poses + report")
        report_button.clicked.connect(self._run_report)
        buttons.addWidget(report_button)
        report_layout.addLayout(buttons)
        contact_button = QtWidgets.QPushButton("Continuous facial contact report")
        contact_button.clicked.connect(self._run_contact_report)
        report_layout.addWidget(contact_button)
        dq_button = QtWidgets.QPushButton("Compare local DQ using selected joints")
        dq_button.clicked.connect(self._compare_skinning)
        report_layout.addWidget(dq_button)
        apply_dq = QtWidgets.QPushButton("Apply last tested local DQ mask")
        apply_dq.clicked.connect(self._apply_skinning)
        report_layout.addWidget(apply_dq)
        detail_button = QtWidgets.QPushButton("Create detail modes: select high mesh, then low mesh")
        detail_button.clicked.connect(self._create_detail_modes)
        report_layout.addWidget(detail_button)
        mode_row = QtWidgets.QHBoxLayout()
        self._detail_combo = QtWidgets.QComboBox()
        self._detail_combo.addItems(['Animation', 'Review', 'Export'])
        self._detail_combo.setCurrentIndex(1)
        mode_row.addWidget(self._detail_combo)
        switch_detail = QtWidgets.QPushButton('Apply detail mode')
        switch_detail.clicked.connect(self._switch_detail)
        ui_utils.action(switch_detail, 'success')
        mode_row.addWidget(switch_detail)
        bypass = QtWidgets.QPushButton('Install wrinkle compute bypass')
        bypass.clicked.connect(self._install_detail_bypass)
        mode_row.addWidget(bypass)
        report_layout.addLayout(mode_row)
        timing_row = QtWidgets.QHBoxLayout()
        self._timing_state = QtWidgets.QComboBox()
        self._timing_state.addItems(['A: DG / CPU', 'B: Parallel / CPU', 'C: Parallel / GPU', 'D: GPU / Cached'])
        self._timing_state.setCurrentIndex(2)
        timing_row.addWidget(self._timing_state)
        playback = QtWidgets.QPushButton('Measure animated playback')
        playback.clicked.connect(self._measure_playback)
        ui_utils.action(playback, 'warning')
        timing_row.addWidget(playback)
        report_layout.addLayout(timing_row)
        viewport_button = QtWidgets.QPushButton("Profile viewport interaction and detail modes")
        viewport_button.clicked.connect(self._profile_viewport)
        report_layout.addWidget(viewport_button)
        self._baseline = QtWidgets.QLineEdit()
        self._baseline.setPlaceholderText("Optional previous .rigqa.json report")
        baseline_row = QtWidgets.QHBoxLayout()
        baseline_row.addWidget(self._baseline)
        choose = QtWidgets.QPushButton("Baseline...")
        choose.clicked.connect(self._choose_baseline)
        baseline_row.addWidget(choose)
        report_layout.addLayout(baseline_row)
        root.addWidget(report_group)
        from maya_tools.scripts.ui.rig_tools_panel import GeneralRigPanel
        self.general_rig = GeneralRigPanel(self)
        general_group = QtWidgets.QGroupBox('General rig tools')
        general_layout = QtWidgets.QVBoxLayout(general_group)
        general_layout.addWidget(self.general_rig)
        root.addWidget(general_group)

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

    def _load_report_meshes(self):
        from maya_tools.scripts.tools import pose_blendshapes
        try:
            self._report_meshes = [pose_blendshapes.mesh_transform(n) for n in cmds.ls(selection=True, long=True) or []]
            if not self._report_meshes:
                raise ValueError("Select at least one polygon mesh.")
            self._report_mesh_label.setText(", ".join(m.rsplit("|", 1)[-1] for m in self._report_meshes))
        except Exception as exc:
            self._status.setText(str(exc))

    def _choose_baseline(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Previous build report", "", "Rig QA (*.rigqa.json)")
        if path:
            self._baseline.setText(path)

    def _run_report(self):
        from maya_tools.scripts.tools import rig_validation
        try:
            if not self._report_meshes:
                raise ValueError("Load the character meshes first.")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "New build report", "", "Rig QA (*.rigqa.json)")
            if not path:
                return
            if not path.endswith(".rigqa.json"):
                path += ".rigqa.json"
            root = "|" + self._report_meshes[0].split("|")[1]
            report = rig_validation.run_report(root, self._report_meshes, path, self._baseline.text().strip() or None,
                                               sides=self._sides())
            self._status.setText("Saved %d combination poses. Parallel mean: %.2f ms. Missing channels: %d." % (
                len(report["poses"]), report["timings"]["parallel"]["mean_ms"], len(report["missing_channels"])))
        except Exception as exc:
            self._status.setText(str(exc))
            cmds.warning(str(exc))

    def _run_contact_report(self):
        from maya_tools.scripts.tools import facial_contact_validation
        try:
            if not self._report_meshes:
                raise ValueError("Load the facial meshes first.")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "New facial contact report", "", "Facial contact (*.contact.json)")
            if not path:
                return
            if not path.endswith(".contact.json"):
                path += ".contact.json"
            root = "|" + self._report_meshes[0].split("|")[1]
            report = facial_contact_validation.run(root, self._report_meshes, path)
            failed = sum(not s['closed_contact_pass'] for s in report['sequences'])
            self._status.setText("Saved %d continuous sequences. Closed landmark contact failures: %d." % (len(report['sequences']), failed))
        except Exception as exc:
            self._status.setText(str(exc))
            cmds.warning(str(exc))

    def _compare_skinning(self):
        from maya_tools.scripts.tools import skinning_volume, rig_validation
        try:
            if not self._report_meshes:
                raise ValueError("Load the body mesh, then select its arm or forearm skin joints.")
            mesh = self._report_meshes[0]
            joints = cmds.ls(selection=True, type="joint", long=True) or []
            candidates = cmds.ls(cmds.listHistory(mesh), type="skinCluster") or []
            skin = next((s for s in candidates if set(cmds.ls(cmds.skinCluster(s, q=True, influence=True), long=True) or []).intersection(joints)), None)
            if not skin:
                raise ValueError("Select joints influencing the loaded mesh.")
            regional, mask = skinning_volume.local_mask(mesh, skin, joints)
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "New skinning comparison", "", "Skinning comparison (*.skincompare.json)")
            if not path:
                return
            if not path.endswith(".skincompare.json"):
                path += ".skincompare.json"
            root = "|" + mesh.split("|")[1]
            self._skin_candidate = skinning_volume.compare(root, mesh, skin, path, rig_validation.COMBINATION_POSES, mask, [i for i,w in enumerate(regional) if w > .5])
            self._status.setText("Compared native skinning methods. Review shapes before applying the tested mask.")
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

    def _apply_skinning(self):
        from maya_tools.scripts.tools import skinning_volume, rig_validation
        try:
            candidate = getattr(self, "_skin_candidate", None)
            if not candidate or not cmds.objExists(candidate['skin']) or rig_validation.mesh_data(candidate['mesh'])['topology'] != candidate['topology']:
                raise ValueError("Run a comparison on this mesh before applying its mask.")
            skinning_volume.apply_mask(candidate['mesh'], candidate['skin'], candidate['mask'])
            self._status.setText("Applied tested local DQ mask. Maya Undo restores the previous settings.")
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

    def _create_detail_modes(self):
        from maya_tools.scripts.tools import rig_performance, bifrost_wrinkles
        try:
            meshes = cmds.ls(selection=True, long=True, objectsOnly=True) or []
            if len(meshes) != 2:
                raise ValueError("Select the rendered high mesh followed by the low mesh.")
            root = "|" + meshes[0].split("|")[1]
            settings = [r['prefix']+'_Settings' for r in bifrost_wrinkles.export_setups()
                        if (r['source'] if r.get('in_place') else r['prefix']+'_Face').rsplit('|',1)[-1] == meshes[0].rsplit('|',1)[-1]]
            rig_performance.create_detail_modes(root, [meshes[0]], [meshes[1]], settings)
            self._status.setText("Created Animation / Review / Export on the character root. Review is active.")
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

    def _performance_root(self):
        if not self._report_meshes:
            raise ValueError('Load meshes belonging to one character first.')
        return '|' + self._report_meshes[0].split('|')[1]

    def _switch_detail(self):
        from maya_tools.scripts.tools import rig_performance
        try:
            rig_performance.set_detail_mode(self._performance_root(), self._detail_combo.currentIndex())
            self._status.setText('Applied ' + self._detail_combo.currentText() + ' detail mode.')
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

    def _install_detail_bypass(self):
        from maya_tools.scripts.tools import rig_performance
        try:
            rig_performance.install_compute_bypass(self._performance_root())
            self._status.setText('Installed workflow detail routing. Switch modes here; measure skipped work before acceptance.')
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

    def _measure_playback(self):
        from maya_tools.scripts.tools import rig_benchmark
        try:
            root = self._performance_root()
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'New animated benchmark', '', 'Performance (*.performance.json)')
            if not path:
                return
            if not path.endswith('.performance.json'):
                path += '.performance.json'
            state = 'ABCD'[self._timing_state.currentIndex()]
            report = rig_benchmark.run_state(root, path, state=state, detail=self._detail_combo.currentIndex())
            timing = report['timing']
            self._status.setText('%s: median %.2f ms; p95 %.2f ms; variation %.1f%%. Report saved.' %
                                 (state, timing['median_ms'], timing['p95_ms'], timing['cv_percent']))
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

    def _profile_viewport(self):
        from maya_tools.scripts.tools import rig_performance
        try:
            if not self._report_meshes:
                raise ValueError("Load meshes belonging to the character first.")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "New viewport benchmark", "", "Viewport benchmark (*.viewport.json)")
            if not path:
                return
            if not path.endswith(".viewport.json"):
                path += ".viewport.json"
            root = "|" + self._report_meshes[0].split("|")[1]
            report = rig_performance.benchmark(root, path)
            self._status.setText("Viewport mean: Animation %.2f ms; Review %.2f ms. Profiler capture saved." % (report['variants']['animation']['mean_ms'], report['variants']['review']['mean_ms']))
        except Exception as exc:
            self._status.setText(str(exc)); cmds.warning(str(exc))

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
