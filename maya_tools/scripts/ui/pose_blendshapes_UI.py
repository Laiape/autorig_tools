"""Small mesh/blendshape/target editor for controller-captured poses."""
from maya import cmds
import maya.OpenMayaUI as omui
try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance

from maya_tools.scripts.tools import pose_blendshapes as tool
from maya_tools.scripts.tools import orientation_correctives as orientation
from maya_tools.scripts.utils import ui_utils

_window = None


class TransferDialog(QtWidgets.QDialog):
    def __init__(self, editor):
        super(TransferDialog, self).__init__(editor)
        self.editor = editor
        self.bs = editor.current_blendshape()
        self.index = editor.current_target()
        self.source_mesh = tool.mesh_transform(editor.mesh.text())
        self.landmarks = {"source": [], "target": []}
        self.setWindowTitle("Transfer Corrective Sculpt")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Source: " + dict(tool.targets(self.bs))[self.index]))
        self.mesh = QtWidgets.QLineEdit(); self.mesh.setReadOnly(True)
        self.mesh.setPlaceholderText("Destination mesh / LOD")
        layout.addWidget(self.mesh)
        load = QtWidgets.QPushButton("Load selected destination mesh")
        load.clicked.connect(self.load_mesh); layout.addWidget(load)
        self.destination_bs = QtWidgets.QComboBox(); layout.addWidget(self.destination_bs)
        self.distance = QtWidgets.QDoubleSpinBox(); self.distance.setRange(0, 1e6)
        self.distance.setDecimals(4)
        row = QtWidgets.QHBoxLayout(); row.addWidget(QtWidgets.QLabel("Maximum match distance (0 = unlimited)"))
        row.addWidget(self.distance); layout.addLayout(row)
        self.mask = QtWidgets.QCheckBox("Only selected destination vertices")
        layout.addWidget(self.mask)
        self.landmark_label = QtWidgets.QLabel("Optional: align variants with at least four landmark pairs.")
        self.landmark_label.setWordWrap(True); layout.addWidget(self.landmark_label)
        row = QtWidgets.QHBoxLayout()
        pair = QtWidgets.QPushButton("Add selected source/target vertex pair")
        pair.clicked.connect(self.add_pair); row.addWidget(pair)
        clear = QtWidgets.QPushButton("Clear pairs")
        clear.clicked.connect(self.clear_pairs); row.addWidget(clear); layout.addLayout(row)
        hint = QtWidgets.QLabel("Use aligned neutral object-space meshes. The matching destination controller must exist. Inspect the transferred sculpt in its captured pose.")
        hint.setWordWrap(True); layout.addWidget(hint)
        transfer = QtWidgets.QPushButton("Transfer saved sculpt")
        transfer.clicked.connect(self.transfer); layout.addWidget(transfer)
        self.status = QtWidgets.QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        ui_utils.apply_maya_style(self)

    def load_mesh(self):
        try:
            selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
            if len(selected) != 1:
                raise ValueError("Select one destination polygon mesh.")
            mesh = tool.mesh_transform(selected[0])
            if mesh == self.source_mesh:
                raise ValueError("Choose another mesh.")
            self.mesh.setText(mesh)
            self.destination_bs.clear(); self.destination_bs.addItem("New post/tangent blendshape", None)
            for bs in tool.blendshapes(mesh):
                self.destination_bs.addItem(bs, bs)
            self.clear_pairs()
        except Exception as exc:
            self.status.setText(str(exc))

    def add_pair(self):
        try:
            selected = cmds.filterExpand(cmds.ls(selection=True, flatten=True, long=True), selectionMask=31) or []
            pair = {}
            for vertex in selected:
                mesh = tool.mesh_transform(vertex.split(".vtx[")[0])
                if mesh == self.source_mesh:
                    pair["source"] = cmds.xform(vertex, query=True, objectSpace=True, translation=True)
                elif mesh == self.mesh.text():
                    pair["target"] = cmds.xform(vertex, query=True, objectSpace=True, translation=True)
            if len(selected) != 2 or len(pair) != 2:
                raise ValueError("Select one source vertex and one destination vertex in neutral.")
            for side, position in pair.items():
                self.landmarks[side].append(position)
            self.landmark_label.setText("Landmark pairs: %d" % len(self.landmarks["source"]))
        except Exception as exc:
            self.status.setText(str(exc))

    def clear_pairs(self):
        self.landmarks = {"source": [], "target": []}
        self.landmark_label.setText("Optional: align variants with at least four landmark pairs.")

    def transfer(self):
        try:
            from maya_tools.scripts.tools import corrective_transfer
            vertices = None
            if self.mask.isChecked():
                selected = cmds.filterExpand(cmds.ls(selection=True, flatten=True, long=True), selectionMask=31) or []
                vertices = [int(v.split(".vtx[")[1].rstrip("]")) for v in selected
                            if tool.mesh_transform(v.split(".vtx[")[0]) == self.mesh.text()]
            result = corrective_transfer.transfer_target(self.source_mesh, self.bs, self.index, self.mesh.text(),
                destination_bs=self.destination_bs.currentData(), landmarks=self.landmarks if self.landmarks["source"] else None,
                max_distance=self.distance.value() or None, vertices=vertices)
            self.status.setText("Created %s: %d affected vertices, %d unmatched. Load the destination mesh to review it." % (
                result["name"], result["transfer"]["affected_vertices"], result["transfer"]["unmatched"]))
        except Exception as exc:
            self.status.setText(str(exc)); cmds.warning(str(exc))


class CaptureDialog(QtWidgets.QDialog):
    def __init__(self, editor):
        super(CaptureDialog, self).__init__(editor)
        self.editor = editor
        self.controller = None
        self.setWindowTitle("Add Pose Target")
        self.resize(450, 280)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Select a posed controller in Maya, then load it."))
        self.control_label = QtWidgets.QLabel("No controller loaded")
        layout.addWidget(self.control_label)
        load = QtWidgets.QPushButton("Load selected controller")
        load.clicked.connect(self.load_selection)
        layout.addWidget(load)
        self.channels = QtWidgets.QTableWidget(0, 3)
        self.channels.setHorizontalHeaderLabels(["Channel", "Default", "Pose = weight 1"])
        self.channels.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.channels.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.channels)
        self.name = QtWidgets.QLabel()
        self.name.setWordWrap(True)
        layout.addWidget(self.name)
        self.error = QtWidgets.QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QtWidgets.QHBoxLayout()
        self.add = QtWidgets.QPushButton("Add and sculpt")
        self.add.setEnabled(False)
        self.add.clicked.connect(self.create)
        buttons.addWidget(self.add)
        cancel = QtWidgets.QPushButton("Close")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        ui_utils.apply_maya_style(self)
        self.load_selection()

    def load_selection(self):
        try:
            selection = cmds.ls(selection=True, objectsOnly=True, long=True) or []
            if len(selection) != 1:
                raise ValueError("Select one posed controller.")
            controller, values = tool.capture_control(selection[0])
            if controller == tool.mesh_transform(self.editor.mesh.text()):
                raise ValueError("Select the rig controller, not the mesh.")
            self.controller = controller
            self.control_label.setText(controller.rsplit("|", 1)[-1])
            self.channels.setRowCount(len(values))
            for row, value in enumerate(values):
                for column, key in enumerate(("channel", "default", "pose")):
                    self.channels.setItem(row, column, QtWidgets.QTableWidgetItem(str(value[key])))
            self.name.setText(tool.target_name(controller, values))
            self.add.setEnabled(True)
            self.error.setText("")
        except Exception as exc:
            self.controller = None
            self.add.setEnabled(False)
            self.channels.setRowCount(0)
            self.name.setText("")
            self.error.setText(str(exc))

    def create(self):
        try:
            index, name = tool.add_target(self.editor.mesh.text(), self.editor.current_blendshape(), self.controller,
                                          self.editor.driver_region.currentData(), self.editor.pose_type.currentData())
            self.editor.refresh_targets(index)
            self.editor.status.setText("Editing " + name + ": sculpt or move mesh vertices, then Save.")
            self.editor.sync_edit()
            self.accept()
        except Exception as exc:
            self.error.setText(str(exc))


class PoseBlendshapesUI(QtWidgets.QDialog):
    def __init__(self, parent=None, embedded=False):
        super(PoseBlendshapesUI, self).__init__(parent)
        self.setWindowTitle("Pose Blendshapes")
        self.resize(650, 420)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, not embedded)
        if embedded:
            self.setWindowFlags(QtCore.Qt.Widget)
        layout = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self.mesh = QtWidgets.QLineEdit()
        self.mesh.setReadOnly(True)
        self.mesh.setPlaceholderText("Select the mesh to correct")
        top.addWidget(self.mesh)
        self.load_mesh_button = self.button("Load mesh", self.load_mesh)
        top.addWidget(self.load_mesh_button)
        self.refresh_button = self.button("Refresh", self.refresh)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)
        orientation_box = QtWidgets.QGroupBox("Pose driver")
        if embedded:
            orientation_box.setTitle("Pose driver (optional)")
            orientation_box.setCheckable(True)
            orientation_box.setChecked(False)
            driver_content = QtWidgets.QWidget()
            outer = QtWidgets.QVBoxLayout(orientation_box)
            outer.addWidget(driver_content)
            driver_content.hide()
            orientation_box.toggled.connect(driver_content.setVisible)
            driver_layout = QtWidgets.QVBoxLayout(driver_content)
            driver_layout.setContentsMargins(0, 0, 0, 0)
        else:
            driver_layout = QtWidgets.QVBoxLayout(orientation_box)
        inputs = QtWidgets.QHBoxLayout()
        self.driver_joint = QtWidgets.QLineEdit()
        self.driver_joint.setPlaceholderText("Base joint")
        self.driver_reference = QtWidgets.QLineEdit()
        self.driver_reference.setPlaceholderText("Torso / parent reference")
        for field, label in ((self.driver_joint, "Load joint"), (self.driver_reference, "Load reference")):
            field.setReadOnly(True)
            row = QtWidgets.QHBoxLayout() if embedded else inputs
            row.addWidget(field)
            row.addWidget(self.button(label, lambda f=field: self.load_driver_node(f)))
            if embedded:
                driver_layout.addLayout(row)
        self.driver_axis = QtWidgets.QComboBox()
        self.driver_axis.addItems(["X", "Y", "Z"])
        inputs.addWidget(self.driver_axis)
        inputs.addWidget(self.button("Create at neutral", self.create_orientation_region))
        driver_layout.addLayout(inputs)
        modes = QtWidgets.QHBoxLayout()
        self.driver_region = QtWidgets.QComboBox()
        self.refresh_regions()
        modes.addWidget(self.driver_region)
        self.pose_type = QtWidgets.QComboBox()
        for label, value in (("Swing and twist", "swing_twist"), ("Swing only", "swing"), ("Twist only", "twist")):
            self.pose_type.addItem(label, value)
        modes.addWidget(self.pose_type)
        convert = self.button("Convert selected target", self.convert_orientation)
        if not embedded:
            modes.addWidget(convert)
        driver_layout.addLayout(modes)
        if embedded:
            driver_layout.addWidget(convert)
        hint = QtWidgets.QLabel("Create the region in neutral. Add captures the posed joint; Convert uses the target's saved controller pose.")
        hint.setWordWrap(True)
        driver_layout.addWidget(hint)
        layout.addWidget(orientation_box)
        self.orientation_box = orientation_box
        self.controls = []
        panels = QtWidgets.QVBoxLayout() if embedded else QtWidgets.QHBoxLayout()
        left = QtWidgets.QVBoxLayout()
        left.addWidget(QtWidgets.QLabel("Blendshapes on this mesh"))
        self.blendshapes = QtWidgets.QListWidget()
        if embedded:
            self.blendshapes.setMinimumHeight(75)
            self.blendshapes.setMaximumHeight(110)
        self.blendshapes.currentItemChanged.connect(self.refresh_targets)
        left.addWidget(self.blendshapes)
        create = QtWidgets.QHBoxLayout()
        self.order = QtWidgets.QComboBox()
        self.order.addItem("Post / tangent (recommended)", "post")
        self.order.addItem("Pre / before skin", "pre")
        create.addWidget(self.order)
        create.addWidget(self.button("New", self.create_blendshape))
        left.addLayout(create)
        panels.addLayout(left, 1)
        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("Targets"))
        self.targets = QtWidgets.QListWidget()
        if embedded:
            self.targets.setMinimumHeight(110)
        self.targets.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.targets.currentItemChanged.connect(self.describe_target)
        self.targets.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.targets.customContextMenuRequested.connect(self.show_target_menu)
        right.addWidget(self.targets)
        actions = QtWidgets.QHBoxLayout()
        for label, callback in (("Add", self.capture_dialog), ("Edit", self.edit_target), ("Delete", self.delete_target)):
            button = self.button(label, callback)
            self.controls.append(button)
            actions.addWidget(button)
        right.addLayout(actions)
        self.mirror = self.button("Mirror counterpart + dependencies", self.mirror_target)
        self.mirror.setToolTip("Save the sculpt first. Create a new right target and its R_ controller driver across mesh X.")
        right.addWidget(self.mirror)
        self.transfer_button = self.button("Transfer sculpt to mesh / LOD...", self.transfer_dialog)
        self.controls.append(self.transfer_button)
        right.addWidget(self.transfer_button)
        self.combination_button = self.button("Create combination from selected targets...", self.create_combination)
        self.controls.append(self.combination_button)
        right.addWidget(self.combination_button)
        poses = QtWidgets.QHBoxLayout()
        for label, neutral in (("Go to pose", False), ("Default", True)):
            button = self.button(label, lambda value=neutral: self.go_pose(value))
            self.controls.append(button)
            poses.addWidget(button)
        right.addLayout(poses)
        self.neutral = self.button("Neutral pose", self.neutral_pose)
        self.neutral.setToolTip("Reset all controls of this rig to their defaults. Maya Undo restores the previous pose.")
        self.controls.append(self.neutral)
        right.addWidget(self.neutral)
        panels.addLayout(right, 2)
        layout.addLayout(panels)
        self.details = QtWidgets.QLabel("Pose the controller, then Add a target.")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        editing = QtWidgets.QHBoxLayout()
        self.editing_layout = editing
        self.live = self.button("LIVE", self.toggle_live)
        self.live.setObjectName("poseBlendshapeLive")
        ui_utils.preserve_style(self.live)
        self.live.setCheckable(True)
        editing.addWidget(self.live)
        self.save = self.button("Save sculpt", lambda: self.finish(True))
        self.cancel = self.button("Cancel sculpt", lambda: self.finish(False))
        editing.addWidget(self.save)
        editing.addWidget(self.cancel)
        layout.addLayout(editing)
        self.status = QtWidgets.QLabel("Load a mesh. Select its blendshape or create a new one.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        ui_utils.apply_maya_style(self)
        session = tool.edit_session()
        if session:
            self.mesh.setText(tool.linked(session, "mesh"))
            self.refresh(tool.linked(session, "blendShape"))
            self.refresh_targets(cmds.getAttr(session + ".targetIndex"))
            self.status.setText("A sculpt edit is active in this scene. Save or cancel to resume its driver.")
        else:
            selection = cmds.ls(selection=True, objectsOnly=True, long=True) or []
            if len(selection) == 1:
                try:
                    self.mesh.setText(tool.mesh_transform(selection[0]))
                    self.refresh()
                except ValueError:
                    pass
        self.sync_edit()
        self._edit_timer = QtCore.QTimer(self)
        self._edit_timer.setInterval(500)
        self._edit_timer.timeout.connect(self.sync_edit)
        self._edit_timer.start()

    def button(self, label, callback):
        button = QtWidgets.QPushButton(label)
        button.clicked.connect(lambda checked=False: self.run(callback))
        return button

    def load_driver_node(self, field):
        selection = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if len(selection) != 1:
            raise ValueError("Select one base-rig joint or reference transform.")
        field.setText(orientation._transform(selection[0]))

    def refresh_regions(self, selected=None):
        self.driver_region.clear()
        self.driver_region.addItem("Controller channels (SDK)", None)
        for system in orientation.systems():
            self.driver_region.addItem(system, system)
            if system == selected:
                self.driver_region.setCurrentIndex(self.driver_region.count() - 1)

    def create_orientation_region(self):
        tool._idle()
        joint = self.driver_joint.text()
        name = joint.rsplit("|", 1)[-1].replace(":", "_") + "_orientation"
        system = orientation.create_system(joint, self.driver_reference.text(), name, self.driver_axis.currentText())
        self.refresh_regions(system)
        self.status.setText("Neutral captured. Pose the rig and Add, or convert a saved target.")

    def convert_orientation(self):
        tool._idle()
        system = self.driver_region.currentData()
        if not system:
            raise ValueError("Choose an orientation region first.")
        bs, index = self.current_blendshape(), self.current_target()
        record = tool.pose_record(bs, index)
        if not record:
            raise ValueError("Select a captured pose target.")
        import json
        control = tool.linked(record, "controller")
        values = json.loads(cmds.getAttr(record + ".channels"))
        with tool._temporary_values({control + "." + v["channel"]: v["pose"] for v in values}):
            orientation.attach_target(system, bs, index, record, self.pose_type.currentData())
        self.describe_target()
        self.status.setText("Orientation driver applied; saved sculpt and current rig pose preserved.")

    def run(self, callback):
        try:
            callback()
        except Exception as exc:
            self.status.setText(str(exc))
            cmds.warning(str(exc))

    def load_mesh(self):
        selection = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        if len(selection) != 1:
            raise ValueError("Select one polygon mesh.")
        self.set_mesh(selection[0])
        if hasattr(self, '_framework_binding'):
            from maya_tools.scripts.framework import context as framework_context
            framework_context.service().capture_selection()

    def set_mesh(self, mesh):
        mesh = tool.mesh_transform(mesh)
        if mesh != self.mesh.text():
            tool._idle()
        self.mesh.setText(mesh)
        self.refresh()

    def current_blendshape(self):
        item = self.blendshapes.currentItem()
        if not item:
            raise ValueError("Select a blendshape or click New.")
        return item.data(QtCore.Qt.UserRole)

    def current_target(self):
        item = self.targets.currentItem()
        if not item:
            raise ValueError("Select a target.")
        return item.data(QtCore.Qt.UserRole)

    def refresh(self, selected=None):
        previous = selected or (self.current_blendshape() if self.blendshapes.currentItem() else None)
        self.blendshapes.clear()
        if not self.mesh.text():
            return
        for bs in tool.blendshapes(self.mesh.text()):
            item = QtWidgets.QListWidgetItem(bs + "  [" + tool.deformation_order(bs, self.mesh.text()) + "]")
            item.setToolTip(bs)
            item.setData(QtCore.Qt.UserRole, bs)
            self.blendshapes.addItem(item)
            if bs == previous:
                self.blendshapes.setCurrentItem(item)
        if not self.blendshapes.currentItem() and self.blendshapes.count():
            self.blendshapes.setCurrentRow(0)
        self.sync_edit()

    def refresh_targets(self, selected=None, *args):
        if not isinstance(selected, int):
            selected = self.current_target() if self.targets.currentItem() else None
        self.targets.clear()
        if not self.blendshapes.currentItem():
            return
        for index, name in tool.targets(self.current_blendshape()):
            item = QtWidgets.QListWidgetItem(name)
            item.setToolTip(name)
            item.setData(QtCore.Qt.UserRole, index)
            self.targets.addItem(item)
            if index == selected:
                self.targets.setCurrentItem(item)
        if not self.targets.currentItem() and self.targets.count():
            self.targets.setCurrentRow(0)

    def describe_target(self, *args):
        self.sync_edit()
        if not self.targets.currentItem():
            self.details.setText("Pose the controller, then Add a target.")
            return
        record = tool.pose_record(self.current_blendshape(), self.current_target())
        if not record:
            self.details.setText("Existing target. Edit supports baked targets; live source meshes are edited in Maya.")
            return
        import json
        values = json.loads(cmds.getAttr(record + ".channels"))
        from maya_tools.scripts.tools import combination_correctives as combinations
        combination = combinations.data(record)
        if combination:
            names = dict(tool.targets(self.current_blendshape()))
            self.details.setText("Combination: " + " * ".join(names.get(i, str(i)) for i in combination['drivers']) + "\nGo to pose restores all captured controllers.")
            return
        controller = tool.linked(record, "controller")
        system = orientation.linked(record, "orientationSystem")
        if system:
            self.details.setText(system + "\nOrientation driver; controller channels are retained for Go to pose. " +
                                 "; ".join(v["channel"] + ": " + str(v["pose"]) for v in values))
            return
        text = "; ".join("%s: %g -> %g" % (v["channel"], v["default"], v["pose"]) for v in values)
        self.details.setText((controller or "Missing controller") + "\nDefault = weight 0; captured pose = weight 1. " + text)

    def create_blendshape(self):
        bs = tool.create_blendshape(self.mesh.text(), self.order.currentData())
        self.refresh(bs)
        self.status.setText("Select the controller in its target pose, then click Add.")

    def capture_dialog(self):
        tool._idle()
        self.current_blendshape()
        dialog = CaptureDialog(self)
        # A modeless capture dialog permits selection in Maya's viewport.
        dialog.setModal(False)
        self._capture = dialog
        dialog.show()

    def create_combination(self):
        from maya_tools.scripts.tools import combination_correctives as combinations
        indices = [item.data(QtCore.Qt.UserRole) for item in self.targets.selectedItems()]
        name, accepted = QtWidgets.QInputDialog.getText(self, "Combination target", "Unique target name", text="Combination_BLS")
        if accepted:
            index, _ = combinations.create(self.mesh.text(), self.current_blendshape(), indices, name)
            self.refresh_targets(index)
            self.status.setText("Combination pose captured. Sculpt only its remaining correction, then Save sculpt.")

    def transfer_dialog(self):
        tool._idle()
        dialog = TransferDialog(self)
        self._transfer = dialog
        dialog.setModal(False)
        dialog.show()

    def edit_target(self):
        bs, index = self.current_blendshape(), self.current_target()
        tool.begin_edit(self.mesh.text(), bs, index, restore_pose=tool.pose_record(bs, index) is not None)
        self.status.setText("Editing at weight 1. Sculpt or move mesh vertices, then Save.")
        self.sync_edit()

    def finish(self, save):
        selected = self.current_target()
        tool.finish_edit(save)
        self.refresh_targets(selected)
        self.status.setText("Sculpt saved; automatic driver resumed." if save else "Previous sculpt restored; driver resumed.")
        self.sync_edit()

    def toggle_live(self):
        if tool.edit_session():
            self.finish(True)
        else:
            self.edit_target()
        self.sync_edit()

    def mirror_target(self):
        index, name = tool.mirror_target(self.mesh.text(), self.current_blendshape(), self.current_target())
        self.refresh_targets(index)
        self.status.setText("Created " + name + "; driven by the matching R_ controller.")
        self.sync_edit()

    def target_menu(self, item):
        menu = QtWidgets.QMenu(self)
        index = item.data(QtCore.Qt.UserRole)
        for label, direction in (("Mirror shape (same target)", "auto"),):
            action = menu.addAction(label)
            action.setToolTip("Copy the sculpted side to its opposite automatically, keeping the original sculpt, target name and driver.")
            action.setEnabled(tool.edit_session() is None)
            action.triggered.connect(lambda checked=False, value=direction: self.run(
                lambda: self.mirror_shape(index, value)))
        return menu

    def show_target_menu(self, position):
        item = self.targets.itemAt(position)
        if item is None:
            return
        self.targets.setCurrentItem(item)
        menu = self.target_menu(item)
        previous = getattr(self, "_target_context_menu", None)
        if previous is not None:
            previous.close()
        self._target_context_menu = menu
        menu.popup(self.targets.viewport().mapToGlobal(position))

    def mirror_shape(self, index, direction):
        index, name = tool.mirror_target_shape(self.mesh.text(), self.current_blendshape(), index, direction)
        self.refresh_targets(index)
        self.status.setText("Mirrored shape in " + name + "; source sculpt, target and driver preserved.")
        self.sync_edit()

    def go_pose(self, neutral):
        tool.go_to_pose(self.current_blendshape(), self.current_target(), neutral)

    def neutral_pose(self):
        result = tool.neutral_pose(self.mesh.text())
        self.status.setText("Neutral pose: %d rig controls, %d channels reset%s." % (
            result["controls"], result["channels"],
            "; %d locked or driven channels kept" % len(result["skipped"]) if result["skipped"] else ""))

    def delete_target(self):
        tool.remove_target(self.mesh.text(), self.current_blendshape(), self.current_target())
        self.refresh_targets()
        self.status.setText("Target removed. Maya Undo restores it.")

    def sync_edit(self):
        editing = tool.edit_session() is not None
        self.orientation_box.setEnabled(not editing)
        self.blendshapes.setEnabled(not editing)
        self.targets.setEnabled(not editing)
        self.order.setEnabled(not editing)
        for button in self.controls:
            button.setEnabled(not editing)
        self.save.setEnabled(editing)
        self.cancel.setEnabled(editing)
        self.live.setChecked(editing)
        self.live.setEnabled(editing or self.targets.currentItem() is not None)
        self.live.setToolTip("Save sculpt and leave LIVE editing." if editing else "Enter LIVE sculpt editing for the selected target.")
        # Explicit user-requested state color; all other controls keep Maya's theme.
        self.live.setStyleSheet(
            "QPushButton#poseBlendshapeLive:checked { background-color: #c83232; color: white; "
            "border: 1px solid #ef6464; border-radius: 2px; padding: 4px; font-weight: bold; }"
            "QPushButton#poseBlendshapeLive:checked:hover { background-color: #db3b3b; }"
            if editing else "")
        item = self.targets.currentItem()
        self.mirror.setEnabled(not editing and item is not None and item.text().startswith("L_"))


def show():
    global _window
    if _window is not None:
        try:
            _window.close()
        except RuntimeError:
            pass
    pointer = omui.MQtUtil.mainWindow()
    parent = wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None
    _window = PoseBlendshapesUI(parent)
    _window.show()
    return _window
