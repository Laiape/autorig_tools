"""Bake supported deformation stacks with independent validation poses."""
from importlib import reload
import os
import re
from maya import cmds
import maya.OpenMayaUI as omui
try:
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets
    from shiboken2 import wrapInstance
from maya_tools.scripts.tools import proximity_bake
from maya_tools.scripts.utils import ui_utils

_window = None


class DeformationBakeUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(DeformationBakeUI, self).__init__(parent)
        self.setWindowTitle("Bake Deformation to Skin")
        self.resize(560, 440)
        layout = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel("Select meshes with skin, Proximity Wrap, corrective blendshapes or Delta Mush. Animate a varied range of motion first.")
        hint.setWordWrap(True); layout.addWidget(hint)
        form = QtWidgets.QFormLayout()
        frame_row = QtWidgets.QHBoxLayout()
        self.start, self.end, self.step = [QtWidgets.QDoubleSpinBox() for _ in range(3)]
        for field in (self.start, self.end): field.setRange(-1e6, 1e6)
        self.step.setRange(.01, 1e6); self.step.setValue(1)
        self.start.setValue(cmds.playbackOptions(query=True, minTime=True))
        self.end.setValue(cmds.playbackOptions(query=True, maxTime=True))
        for field in (self.start, self.end, self.step): frame_row.addWidget(field)
        form.addRow("Fit start / end / step", frame_row)
        self.bind = QtWidgets.QDoubleSpinBox(); self.bind.setRange(-1e6, 1e6)
        self.bind.setValue(cmds.currentTime(query=True)); form.addRow("Bind frame", self.bind)
        self.influences = QtWidgets.QSpinBox(); self.influences.setRange(1, 64)
        self.influences.setValue(8); form.addRow("Maximum influences", self.influences)
        self.limit = QtWidgets.QDoubleSpinBox(); self.limit.setRange(0, 1e6); self.limit.setDecimals(5)
        form.addRow("Max accepted error (0 = report only)", self.limit)
        layout.addLayout(form)
        self.hybrid = QtWidgets.QCheckBox("Fit native orientation residual correctives (one source mesh)")
        layout.addWidget(self.hybrid)
        hybrid_form = QtWidgets.QFormLayout()
        self.hybrid_fields = []
        for label in ("Pose controller", "Orientation joint", "Reference joint"):
            row = QtWidgets.QHBoxLayout(); field = QtWidgets.QLineEdit(); field.setPlaceholderText(label)
            row.addWidget(field); load = QtWidgets.QPushButton("Load selected")
            load.clicked.connect(lambda checked=False, f=field: f.setText((cmds.ls(selection=True,long=True,objectsOnly=True) or [''])[0]))
            row.addWidget(load); hybrid_form.addRow(label,row); self.hybrid_fields.append(field)
        self.hybrid_axis = QtWidgets.QComboBox(); self.hybrid_axis.addItems(["X","Y","Z"])
        hybrid_form.addRow("Twist axis",self.hybrid_axis); layout.addLayout(hybrid_form)
        self.held_out = QtWidgets.QCheckBox("Validate at midpoints excluded from the fit")
        self.held_out.setChecked(True); layout.addWidget(self.held_out)
        self.heatmap = QtWidgets.QCheckBox("Show worst per-vertex error on the baked copy")
        self.heatmap.setChecked(True); layout.addWidget(self.heatmap)
        self.save = QtWidgets.QCheckBox("Export a new SKC version for rebuild")
        layout.addWidget(self.save)
        row = QtWidgets.QHBoxLayout()
        self.path = QtWidgets.QLineEdit(); self.path.setPlaceholderText("Optional new .skc file")
        row.addWidget(self.path)
        choose = QtWidgets.QPushButton("Choose..."); choose.clicked.connect(self.choose)
        row.addWidget(choose); layout.addLayout(row)
        note = QtWidgets.QLabel("Originals are preserved. A limit failure rolls back the copies and prevents export. Review held-out errors before replacing a production stack.")
        note.setWordWrap(True); layout.addWidget(note)
        button = QtWidgets.QPushButton("Bake selection to Skin"); button.clicked.connect(self.bake)
        layout.addWidget(button)
        self.status = QtWidgets.QLabel("Ready."); self.status.setWordWrap(True); layout.addWidget(self.status)
        ui_utils.apply_maya_style(self)

    def choose(self):
        from maya_tools.scripts.tools.skin_manager_api import SkinManager
        manager = SkinManager(); latest = manager.get_latest_version_path()
        match = re.search(r"_v(\d+)\.skc$", latest)
        version = int(match.group(1)) + 1 if match and os.path.isfile(latest) else 1
        suggested = os.path.join(manager.folder_path, "{}_v{:03d}.skc".format(manager.asset_name, version))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "New baked SKC", suggested, "Skin Cluster (*.skc)")
        if path: self.path.setText(path); self.save.setChecked(True)

    def bake(self):
        try:
            if self.hybrid.isChecked():
                from maya_tools.scripts.tools import hybrid_bake
                if self.save.isChecked():
                    raise ValueError("Review the hybrid candidate and performance before exporting it with Skin Cluster Manager.")
                controller,joint,reference = [f.text().strip() for f in self.hybrid_fields]
                result = hybrid_bake.bake_with_residuals(self.start.value(),self.end.value(),self.step.value(),controller,joint,reference,
                    self.hybrid_axis.currentText(),self.influences.value(),self.limit.value() or .1,color_error=self.heatmap.isChecked())
                self.result = result
                self.status.setText("Hybrid quality passed: %.6g %s; %d residual targets. Compare viewport cost before replacing the source." % (result['worst_max'],result['units'],len(result['targets'])))
                return
            output = self.path.text().strip() if self.save.isChecked() else None
            if self.save.isChecked() and not output:
                raise ValueError("Choose a new SKC file.")
            if output and not output.lower().endswith(".skc"): output += ".skc"
            result = proximity_bake.bake_selected(self.start.value(), self.end.value(), self.step.value(),
                self.bind.value(), self.influences.value(), export_path=output,
                validation_frames=None if self.held_out.isChecked() else [],
                error_limit=self.limit.value() or None, color_error=self.heatmap.isChecked())
            worst = max(r["worst_max"] for r in result["records"])
            self.status.setText("Baked %d meshes. Worst error: %.6g %s. Held-out frames: %d.%s" % (
                len(result["records"]), worst, cmds.currentUnit(query=True, linear=True),
                len(result["validation_frames"]), " SKC: " + output if output else ""))
            self.result = result
        except Exception as exc:
            self.status.setText(str(exc)); cmds.warning(str(exc))


def show():
    global _window
    reload(proximity_bake)
    if _window is not None:
        try: _window.close()
        except RuntimeError: pass
    pointer = omui.MQtUtil.mainWindow()
    parent = wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None
    _window = DeformationBakeUI(parent); _window.show()
    return _window
