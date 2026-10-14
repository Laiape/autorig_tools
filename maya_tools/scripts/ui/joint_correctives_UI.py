"""Joint target editor; inherits the shared Maya native Qt style."""
import maya.cmds as cmds
import maya.OpenMayaUI as omui
try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance

from maya_tools.scripts.tools import joint_correctives as jc
from maya_tools.scripts.utils import ui_utils

_window = None


class JointCorrectivesUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(JointCorrectivesUI, self).__init__(parent)
        self.setWindowTitle("Joint Corrective Targets")
        self.resize(650, 720)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self._loading = False
        layout = QtWidgets.QVBoxLayout(self)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        help_label = QtWidgets.QLabel("Create a region, add joints from selected mesh vertices, then edit a target.\n"
                                    "Move, rotate or scale the edit handles to change volume and shape.")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        region_box = QtWidgets.QGroupBox("Region")
        form = QtWidgets.QFormLayout(region_box)
        self.regions = QtWidgets.QComboBox()
        self.regions.currentIndexChanged.connect(self._refresh_region)
        form.addRow("System", self._row(self.regions, "Refresh", self.refresh))
        self.mesh = QtWidgets.QLineEdit()
        form.addRow("Mesh", self._row(self.mesh, "Load selected", lambda: self._load(self.mesh)))
        self.region_name = QtWidgets.QLineEdit("shoulder")
        form.addRow("Name", self._row(self.region_name, "Create region", self._create))
        self.parent_joint = QtWidgets.QLineEdit()
        form.addRow("Follow rig joint", self._row(self.parent_joint, "Load selected", lambda: self._load(self.parent_joint)))
        self.patch_name = QtWidgets.QLineEdit("deltoid")
        form.addRow("Patch name", self.patch_name)
        self.falloff = QtWidgets.QCheckBox("Smooth initial vertex mask")
        self.falloff.setChecked(True)
        form.addRow(self.falloff)
        form.addRow(self._button("Add joint at selected vertices", self._add_joint))
        self.joints = QtWidgets.QComboBox()
        form.addRow("Corrective joint", self.joints)
        tools = QtWidgets.QHBoxLayout()
        tools.addWidget(self._button("Replace selected mask weights", self._mask))
        tools.addWidget(self._button("Select skin layer", self._select_skin))
        form.addRow(tools)
        layout.addWidget(region_box)
        target_box = QtWidgets.QGroupBox("Targets")
        target_layout = QtWidgets.QVBoxLayout(target_box)
        self.poses = QtWidgets.QListWidget()
        self.poses.currentItemChanged.connect(self._refresh_pose)
        target_layout.addWidget(self.poses)
        self.pose_name = QtWidgets.QLineEdit("shoulder_volume")
        target_layout.addWidget(self._row(self.pose_name, "Add target", self._add_pose))
        edit_buttons = QtWidgets.QHBoxLayout()
        for label, callback in (("Edit", self._edit), ("Save edit", lambda: self._finish(True)),
                                ("Cancel edit", lambda: self._finish(False)), ("Delete target", self._delete)):
            edit_buttons.addWidget(self._button(label, callback))
        target_layout.addLayout(edit_buttons)
        settings = QtWidgets.QFormLayout()
        self.weight = QtWidgets.QDoubleSpinBox()
        self.weight.setRange(0, 1)
        self.weight.setSingleStep(.05)
        self.weight.setDecimals(3)
        self.weight.valueChanged.connect(lambda value: self._set_pose("weight", value))
        self.enabled = QtWidgets.QCheckBox("Enabled")
        self.enabled.toggled.connect(lambda value: self._set_pose("enabled", value))
        settings.addRow("Manual weight", self._row(self.weight, "Enabled", None, self.enabled))
        solo = QtWidgets.QHBoxLayout()
        solo.addWidget(self._button("Solo target at 1", lambda: self._preview(self._pose())))
        solo.addWidget(self._button("Resume all drivers", lambda: self._preview(None)))
        settings.addRow(solo)
        self.automatic = QtWidgets.QCheckBox("Automatic driver")
        self.automatic.toggled.connect(lambda value: self._set_pose("auto", value))
        settings.addRow(self.automatic)
        self.driver = QtWidgets.QLineEdit()
        settings.addRow("Driver attribute", self._row(self.driver, "Load channel", self._load_channel))
        ranges = QtWidgets.QHBoxLayout()
        self.start, self.end = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for label, widget, value in (("Start (weight 0)", self.start, 30), ("End (weight 1)", self.end, 90)):
            widget.setRange(-100000, 100000)
            widget.setValue(value)
            ranges.addWidget(QtWidgets.QLabel(label))
            ranges.addWidget(widget)
        self.smooth = QtWidgets.QCheckBox("Smooth")
        self.smooth.setChecked(True)
        ranges.addWidget(self.smooth)
        settings.addRow(ranges)
        settings.addRow(self._button("Apply driver and range", self._configure))
        self.reference = QtWidgets.QLineEdit()
        settings.addRow("Shoulder reference", self._row(self.reference, "Load selected", lambda: self._load(self.reference)))
        swing = QtWidgets.QHBoxLayout()
        self.axis = QtWidgets.QComboBox()
        self.axis.addItems(["X", "Y", "Z"])
        swing.addWidget(QtWidgets.QLabel("Arm length axis"))
        swing.addWidget(self.axis)
        swing.addWidget(self._button("Capture neutral shoulder angle", self._swing))
        settings.addRow(swing)
        hint = QtWidgets.QLabel("Shoulder angle: Follow rig joint = upper arm; reference = clavicle/torso.\n"
                               "Capture with the arm in its zero pose. This driver ignores axial twist.")
        hint.setWordWrap(True)
        settings.addRow(hint)
        target_layout.addLayout(settings)
        layout.addWidget(target_box)
        layout.addWidget(self.status)
        ui_utils.apply_maya_style(self)
        self.refresh()

    def _button(self, label, callback):
        button = QtWidgets.QPushButton(label)
        button.clicked.connect(lambda checked=False: self._run(callback))
        return button

    def _row(self, widget, label, callback, extra=None):
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        layout.addWidget(extra if extra is not None else self._button(label, callback))
        return row

    def _run(self, callback):
        try:
            callback()
        except Exception as exc:
            self.status.setText(str(exc))
            cmds.warning(str(exc))

    def _system(self):
        result = self.regions.currentData()
        if not result or not cmds.objExists(result):
            raise ValueError("Create or select a region first.")
        return result

    def _pose(self):
        item = self.poses.currentItem()
        if item is None:
            raise ValueError("Select a target first.")
        return item.data(QtCore.Qt.UserRole)

    def _load(self, widget):
        selection = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        if not selection:
            raise ValueError("Select a mesh or rig joint first.")
        widget.setText(selection[0])

    def refresh(self, selected=None):
        previous = selected or self.regions.currentData()
        self.regions.blockSignals(True)
        self.regions.clear()
        for system in jc.systems():
            self.regions.addItem(system, system)
        if previous:
            self.regions.setCurrentIndex(max(0, self.regions.findData(previous)))
        self.regions.blockSignals(False)
        self._refresh_region()

    def _refresh_region(self, *args):
        current = self.poses.currentItem()
        previous = current.data(QtCore.Qt.UserRole) if current else None
        self.poses.clear()
        self.joints.clear()
        if not self.regions.currentData():
            return
        system = self._system()
        self.mesh.setText(jc.linked(system, "mesh") or "")
        for _, joint in jc.indexed(system, "joints"):
            self.joints.addItem(joint, joint)
        for _, pose in jc.indexed(system, "poses"):
            item = QtWidgets.QListWidgetItem(cmds.getAttr(pose + ".label"))
            item.setData(QtCore.Qt.UserRole, pose)
            self.poses.addItem(item)
            if pose == previous:
                self.poses.setCurrentItem(item)
        if not self.poses.currentItem() and self.poses.count():
            self.poses.setCurrentRow(0)
        if cmds.getAttr(system + ".editing"):
            edit_pose = jc.linked(system, "poses", cmds.getAttr(system + ".editIndex"))
            for i in range(self.poses.count()):
                if self.poses.item(i).data(QtCore.Qt.UserRole) == edit_pose:
                    self.poses.setCurrentRow(i)
            self.status.setText("A target edit is active in this scene. Save or cancel to resume playback.")
        self._sync_edit_state()

    def _sync_edit_state(self):
        system = self.regions.currentData()
        editing = bool(system and cmds.objExists(system) and cmds.getAttr(system + ".editing"))
        self.regions.setEnabled(not editing)
        self.poses.setEnabled(not editing)
        if self.poses.currentItem():
            self.weight.setEnabled(not editing and not cmds.getAttr(self._pose() + ".auto"))
        self.automatic.setEnabled(not editing)
        self.enabled.setEnabled(not editing)

    def _refresh_pose(self, *args):
        if not self.poses.currentItem():
            return
        pose = self._pose()
        self._loading = True
        try:
            for widget, attr in ((self.weight, "weight"), (self.start, "start"), (self.end, "end")):
                widget.setValue(cmds.getAttr(pose + "." + attr))
            for widget, attr in ((self.enabled, "enabled"), (self.automatic, "auto"), (self.smooth, "smooth")):
                widget.setChecked(cmds.getAttr(pose + "." + attr))
            self.driver.setText(cmds.getAttr(pose + ".driverPlug") or "")
        finally:
            self._loading = False
        self._sync_edit_state()

    def _set_pose(self, attr, value):
        if not self._loading and self.poses.currentItem():
            self._run(lambda: self._change_pose(attr, value))

    def _change_pose(self, attr, value):
        jc._idle(self._system())
        cmds.setAttr(self._pose() + "." + attr, value)
        self._sync_edit_state()

    def _create(self):
        system = jc.create_system(self.mesh.text(), self.region_name.text())
        self.refresh(system)
        self.status.setText("Region created. Load a follow joint, then select mesh vertices for each patch.")

    def _add_joint(self):
        jc.add_joint(self._system(), self.parent_joint.text(), cmds.ls(selection=True, flatten=True),
                     self.patch_name.text(), self.falloff.isChecked())
        self._refresh_region()
        self.status.setText("Joint and mask added. Create or edit a target to deform the patch.")

    def _mask(self):
        jc.set_mask(self._system(), self.joints.currentData(), cmds.ls(selection=True, flatten=True), self.falloff.isChecked())
        self.status.setText("Selected vertex weights updated. Unselected vertices keep their weights.")

    def _select_skin(self):
        cmds.select(jc.linked(self._system(), "skin"), replace=True)
        self.status.setText("Corrective skin selected. Its neutral influence carries the remaining weight.")

    def _add_pose(self):
        pose = jc.add_pose(self._system(), self.pose_name.text())
        self._refresh_region()
        for i in range(self.poses.count()):
            if self.poses.item(i).data(QtCore.Qt.UserRole) == pose:
                self.poses.setCurrentRow(i)
        jc.begin_edit(self._system(), pose)
        self._sync_edit_state()
        self.status.setText("Editing new target. Move/rotate/scale the selected handles, then Save edit.")

    def _edit(self):
        jc.begin_edit(self._system(), self._pose())
        self._sync_edit_state()
        self.status.setText("Editing at full weight. Save or cancel before changing targets.")

    def _finish(self, save):
        jc.finish_edit(self._system(), save)
        self._sync_edit_state()
        self.status.setText("Target saved. Use weight or a driver to activate it." if save else "Edit cancelled.")

    def _delete(self):
        jc.remove_pose(self._system(), self._pose())
        self._refresh_region()
        self.status.setText("Target removed. Maya Undo restores it.")

    def _preview(self, pose):
        jc.preview(self._system(), pose)
        self.status.setText("Target isolated at weight 1." if pose else "All target drivers resumed.")

    def _load_channel(self):
        selection = cmds.ls(selection=True) or []
        attributes = cmds.channelBox("mainChannelBox", query=True, selectedMainAttributes=True) or []
        if not selection or not attributes:
            raise ValueError("Select a rig object and a numeric channel in the Channel Box.")
        self.driver.setText(selection[0] + "." + attributes[0])

    def _configure(self):
        jc.configure_driver(self._pose(), self.driver.text(), self.start.value(), self.end.value(), self.smooth.isChecked())
        self._refresh_pose()
        self.status.setText("Driver applied: weight 0 at start, weight 1 at end.")

    def _swing(self):
        plug = jc.direction_driver(self._system(), self.parent_joint.text(), self.reference.text(), self.axis.currentText())
        self.driver.setText(plug)
        self.status.setText("Neutral shoulder angle captured. Apply the driver and activation range to a target.")


def show():
    global _window
    if _window is not None:
        try:
            _window.close()
        except RuntimeError:
            pass
    pointer = omui.MQtUtil.mainWindow()
    parent = wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None
    _window = JointCorrectivesUI(parent)
    _window.show()
    return _window
