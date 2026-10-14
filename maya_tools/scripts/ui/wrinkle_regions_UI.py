"""Shared Maya editor for portable wrinkle regions and presets."""
from maya import cmds
import maya.OpenMayaUI as omui
try:
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets
    from shiboken2 import wrapInstance
from maya_tools.scripts.tools import wrinkle_presets as presets,bifrost_wrinkles as wrinkles
from maya_tools.scripts.tools import pose_blendshapes as poses
from maya_tools.scripts.utils import ui_utils

_window=None


class WrinkleRegionsUI(QtWidgets.QDialog):
    def __init__(self,parent=None):
        super(WrinkleRegionsUI,self).__init__(parent)
        self.setWindowTitle("Wrinkle Regions / Presets");self.resize(620,460)
        layout=QtWidgets.QVBoxLayout(self)
        row=QtWidgets.QHBoxLayout();self.mesh=QtWidgets.QLineEdit();self.mesh.setReadOnly(True)
        self.mesh.setPlaceholderText("Source facial mesh");row.addWidget(self.mesh)
        row.addWidget(self.button("Load mesh",self.load_mesh));layout.addLayout(row)
        row=QtWidgets.QHBoxLayout();self.setup=QtWidgets.QComboBox();row.addWidget(self.setup)
        row.addWidget(self.button("Refresh",self.refresh));layout.addLayout(row)
        row=QtWidgets.QHBoxLayout();self.prefix=QtWidgets.QLineEdit();self.prefix.setPlaceholderText("Setup prefix")
        row.addWidget(self.prefix);row.addWidget(self.button("Create empty regions",self.create));layout.addLayout(row)
        form=QtWidgets.QFormLayout();self.region=QtWidgets.QComboBox();self.region.addItems(wrinkles.REGIONS)
        form.addRow("Region",self.region)
        row=QtWidgets.QHBoxLayout();self.angle=QtWidgets.QDoubleSpinBox();self.angle.setRange(-360,360)
        self.wavelength=QtWidgets.QDoubleSpinBox();self.wavelength.setRange(.001,1e6);self.wavelength.setValue(1)
        self.plane=QtWidgets.QComboBox();self.plane.addItems(["XY","XZ","YZ"])
        for w in (self.angle,self.wavelength,self.plane):row.addWidget(w)
        form.addRow("Fold angle / spacing / plane",row)
        self.feather=QtWidgets.QSpinBox();self.feather.setRange(0,30);self.feather.setValue(2)
        form.addRow("Boundary feather rings",self.feather);layout.addLayout(form)
        row=QtWidgets.QHBoxLayout();row.addWidget(self.button("Assign selected vertices",self.assign_region))
        row.addWidget(self.button("Clear region",self.clear_region));layout.addLayout(row)
        layout.addWidget(self.button("Assign selected controllers to region",self.assign_controls))
        self.preview=QtWidgets.QCheckBox("Manual preview (all assigned regions)")
        self.preview.toggled.connect(lambda checked:self.run(lambda:self.set_preview(checked)))
        layout.addWidget(self.preview)
        row=QtWidgets.QHBoxLayout();row.addWidget(self.button("Export preset...",self.export_preset))
        row.addWidget(self.button("Apply preset...",self.apply_preset));layout.addLayout(row)
        self.project=QtWidgets.QCheckBox("Project regions to a different topology (normalized bounds)")
        layout.addWidget(self.project)
        self.replace=QtWidgets.QCheckBox("Replace the loaded setup when applying a preset")
        layout.addWidget(self.replace)
        hint=QtWidgets.QLabel("Assign regions on source vertices. Angle and spacing shape the folds; masks and presets are stored per character. Review projected regions around eyes and lips.")
        hint.setWordWrap(True);layout.addWidget(hint)
        self.status=QtWidgets.QLabel("Load a facial mesh or select an existing setup.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.setup.currentIndexChanged.connect(self.setup_changed)
        ui_utils.apply_maya_style(self);self.refresh()

    def button(self,label,callback):
        b=QtWidgets.QPushButton(label);b.clicked.connect(lambda checked=False:self.run(callback));return b

    def run(self,callback):
        try:callback()
        except Exception as exc:self.status.setText(str(exc));cmds.warning(str(exc))

    def refresh(self,selected=None):
        self.setup.blockSignals(True);self.setup.clear()
        for record in wrinkles.export_setups():
            name=record["prefix"]+"_Settings";self.setup.addItem(name,name)
            if name==selected:self.setup.setCurrentIndex(self.setup.count()-1)
        self.setup.blockSignals(False);self.setup_changed()

    def setup_changed(self,*args):
        settings=self.setup.currentData()
        if settings:
            record=presets.setup_record(settings);self.mesh.setText(poses.mesh_transform(record["source"]))
            self.prefix.setText(record["prefix"])
            self.preview.blockSignals(True);self.preview.setChecked(cmds.getAttr(settings+".ManualActivation")>0)
            self.preview.blockSignals(False)

    def load_mesh(self):
        selected=cmds.ls(selection=True,long=True,objectsOnly=True) or []
        if len(selected)!=1:raise ValueError("Select one facial mesh.")
        mesh=poses.mesh_transform(selected[0]);self.mesh.setText(mesh)
        self.prefix.setText(mesh.rsplit("|",1)[-1].replace(":","_")+"Wrinkles")

    def current_settings(self):
        result=self.setup.currentData()
        if not result:raise ValueError("Create or choose a wrinkle setup.")
        return result

    def create(self):
        setup=presets.create(self.mesh.text(),self.prefix.text().strip())
        self.refresh(setup["settings"]);self.status.setText("Created empty regions. Select source vertices and assign a fold pattern.")

    def assign_region(self):
        settings=self.current_settings();source=presets._source(settings)[0]
        vertices=presets.selected_vertices(source)
        presets.assign_region(settings,self.region.currentText(),vertices,self.angle.value(),self.wavelength.value(),self.feather.value(),self.plane.currentText())
        self.status.setText("Updated %s on %d selected vertices."%(self.region.currentText(),len(vertices)))

    def clear_region(self):
        settings=self.current_settings();count=presets._source(settings)[2].numVertices
        presets.set_patterns(settings,{self.region.currentText():[0.]*count})
        self.status.setText("Region cleared. Maya Undo restores the previous field.")

    def assign_controls(self):
        settings=self.current_settings()
        controls=cmds.ls(selection=True,long=True,objectsOnly=True) or []
        setup=presets.assign_controls(settings,self.region.currentText(),controls)
        self.refresh(setup["settings"]);self.status.setText("Local controller masks updated in neutral space.")

    def set_preview(self,checked):
        cmds.setAttr(self.current_settings()+".ManualActivation",1 if checked else 0)

    def export_preset(self):
        path,_=QtWidgets.QFileDialog.getSaveFileName(self,"New wrinkle preset","","Wrinkle presets (*.wrinkles.json)")
        if path:
            if not path.endswith(".wrinkles.json"):path+=".wrinkles.json"
            presets.export_preset(self.current_settings(),path);self.status.setText("Preset saved: "+path)

    def apply_preset(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,"Apply wrinkle preset","","Wrinkle presets (*.wrinkles.json)")
        if path:
            result=presets.apply_preset(path,self.mesh.text(),prefix=self.prefix.text(),
                replace_existing=self.replace.isChecked(),remap_topology=self.project.isChecked())
            self.refresh(result["settings"])
            self.status.setText("Preset applied%s; %d template controls were not found."%(
                " with projected regions" if result["projected"] else "",len(result["missing_controls"])))


def show():
    global _window
    if _window is not None:
        try:_window.close()
        except RuntimeError:pass
    pointer=omui.MQtUtil.mainWindow()
    parent=wrapInstance(int(pointer),QtWidgets.QWidget) if pointer else None
    _window=WrinkleRegionsUI(parent);_window.show();return _window
