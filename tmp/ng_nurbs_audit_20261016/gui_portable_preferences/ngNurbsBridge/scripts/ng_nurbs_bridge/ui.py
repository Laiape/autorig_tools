"""Shared native Qt panel. Its layer session is independent of NG's mesh UI."""
import weakref

from maya import cmds
from maya.api import OpenMaya as om

from . import brush, core, topology
from .qt import QtCore, QtWidgets, isValid


class NurbsPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(NurbsPanel, self).__init__(parent)
        self.setObjectName('ngNurbsSkinPanel')
        self.shape_uuid = None
        self.bridge = None
        self.busy = False
        self.callbacks = []
        self._pending = False
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(6, 6, 6, 6)
        selection = QtWidgets.QHBoxLayout()
        self.surface = QtWidgets.QLineEdit()
        self.surface.setReadOnly(True)
        self.surface.setPlaceholderText('Select a skinned NURBS surface')
        selection.addWidget(self.surface, 1)
        use = QtWidgets.QPushButton('Use selection')
        use.clicked.connect(lambda: self.run(self.load_selection))
        selection.addWidget(use)
        box.addLayout(selection)
        self.skin_label = QtWidgets.QLabel('No NURBS surface loaded')
        self.skin_label.setWordWrap(True)
        box.addWidget(self.skin_label)
        self.initialize = QtWidgets.QPushButton('Initialize NURBS Skin Layers')
        self.initialize.clicked.connect(lambda: self.run(self.create_bridge))
        box.addWidget(self.initialize)
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.layer_tree = QtWidgets.QTreeWidget()
        self.layer_tree.setHeaderLabels(['Layers', 'Opacity %'])
        self.layer_tree.setRootIsDecorated(True)
        self.layer_tree.setColumnWidth(0, 155)
        self.layer_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.layer_tree.itemSelectionChanged.connect(self.change_layer)
        self.layer_tree.itemChanged.connect(lambda item, column: self.run(lambda: self.edit_layer(item, column)))
        split.addWidget(self.layer_tree)
        self.influences = QtWidgets.QTreeWidget()
        self.influences.setHeaderLabels(['Influence / channel', 'Lock'])
        self.influences.setRootIsDecorated(False)
        self.influences.setColumnWidth(0, 155)
        self.influences.itemSelectionChanged.connect(self.change_target)
        self.influences.itemChanged.connect(lambda item, col: self.run(lambda: self.lock_influence(item, col)))
        split.addWidget(self.influences)
        box.addWidget(split, 1)
        actions = QtWidgets.QHBoxLayout()
        for label, callback in [('Add layer', self.add_layer), ('Remove layer', self.remove_layer),
                                ('Up', lambda: self.move_layer(-1)), ('Down', lambda: self.move_layer(1))]:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, action=callback: self.run(action))
            actions.addWidget(button)
        box.addLayout(actions)
        form = QtWidgets.QFormLayout()
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(['Replace', 'Add', 'Scale', 'Smooth', 'Sharpen'])
        self.radius = QtWidgets.QDoubleSpinBox()
        self.radius.setRange(0.0001, 1000000)
        self.radius.setDecimals(4)
        self.radius.setValue(1.0)
        self.radius.setSuffix(' units')
        self.intensity = QtWidgets.QDoubleSpinBox()
        self.intensity.setRange(0, 1)
        self.intensity.setSingleStep(0.05)
        self.intensity.setValue(0.25)
        self.value = QtWidgets.QDoubleSpinBox()
        self.value.setRange(0, 1)
        self.value.setSingleStep(0.05)
        self.value.setValue(1.0)
        for label, widget in [('Mode', self.mode), ('Radius', self.radius), ('Intensity', self.intensity), ('Value', self.value)]:
            form.addRow(label, widget)
        box.addLayout(form)
        for widget in (self.mode, self.radius, self.intensity, self.value):
            signal = widget.currentIndexChanged if widget is self.mode else widget.valueChanged
            signal.connect(self.settings_changed)
        row = QtWidgets.QHBoxLayout()
        self.paint = QtWidgets.QPushButton('Paint NURBS')
        self.paint.setCheckable(True)
        self.paint.clicked.connect(lambda checked: self.run(self.start_paint) if checked else self.deactivate())
        row.addWidget(self.paint)
        flood = QtWidgets.QPushButton('Flood')
        flood.clicked.connect(lambda: self.run(self.flood))
        row.addWidget(flood)
        box.addLayout(row)
        instructions = QtWidgets.QLabel('LMB: paint   |   Shift: smooth   |   Ctrl: invert\n'
            'Preview shows the selected layer channel on the surface.')
        instructions.setWordWrap(True)
        box.addWidget(instructions)
        finish = QtWidgets.QHBoxLayout()
        for label, callback in [('Bake + detach', lambda: self.detach(False)),
                                ('Restore original', lambda: self.detach(True)),
                                ('Export layers', self.export_layers)]:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, action=callback: self.run(action))
            finish.addWidget(button)
        box.addLayout(finish)
        self.status = QtWidgets.QLabel('Use selection to load an untrimmed NURBS with one skinCluster.')
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        self._connect_events()
        self.run(lambda: self.load_selection(required=False))
        self.refresh()

    def _connect_events(self):
        reference = weakref.ref(self)
        def queue(*args):
            panel = reference()
            if panel and isValid(panel) and not panel._pending:
                panel._pending = True
                QtCore.QTimer.singleShot(0, panel._event_refresh)
        for event in ('SelectionChanged', 'Undo', 'Redo', 'ToolChanged'):
            self.callbacks.append(om.MEventMessage.addEventCallback(event, queue))
        for event in (om.MSceneMessage.kBeforeNew, om.MSceneMessage.kBeforeOpen):
            def before_scene(*args):
                panel = reference()
                if panel and isValid(panel):
                    panel.deactivate()
                    panel.bridge = None
                    panel.shape_uuid = None
            self.callbacks.append(om.MSceneMessage.addCallback(event, before_scene))
        ids = self.callbacks
        def cleanup(*args):
            for callback in list(ids):
                om.MMessage.removeCallback(callback)
            ids[:] = []
        self.destroyed.connect(cleanup)

    def _event_refresh(self):
        self._pending = False
        if not isValid(self):
            return
        self.run(lambda: self.load_selection(required=False) if not self.shape_uuid else None)
        self.refresh()

    def run(self, action):
        try:
            return action()
        except Exception as error:
            self.deactivate()
            self.status.setText(str(error))
            cmds.warning('NURBS Skin: '+str(error))

    def load_selection(self, required=True):
        selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        shapes = set()
        for node in selected:
            try:
                if cmds.nodeType(node) == 'skinCluster':
                    for geometry in cmds.skinCluster(node, query=True, geometry=True) or []:
                        shapes.add(topology.surface_shape(geometry))
                else:
                    shapes.add(topology.surface_shape(node))
            except (ValueError, RuntimeError):
                continue
        if len(shapes) != 1:
            if required:
                raise ValueError('Select one skinned NURBS surface or its CVs.')
            return
        shape = shapes.pop()
        if self.shape_uuid != core.uuid(shape):
            self.deactivate()
        self.shape_uuid = core.uuid(shape)
        self.refresh()

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        try:
            old_layer = self.layer_id()
            old_target = self.target()
            shape = core.node_for(self.shape_uuid) if self.shape_uuid and cmds.ls(self.shape_uuid) else None
            self.bridge = core.find(shape) if shape else None
            self.surface.setText(shape.rsplit('|', 1)[-1] if shape else '')
            self.surface.setToolTip(shape or '')
            self.initialize.setVisible(self.bridge is None)
            self.initialize.setEnabled(bool(shape))
            self.layer_tree.clear()
            self.influences.clear()
            if not self.bridge:
                self.skin_label.setText('No layer bridge' if shape else 'No NURBS surface loaded')
                self.paint.setEnabled(False)
                return
            data = self.bridge.validate()
            self.skin_label.setText('%s  |  %s x %s CVs  |  %s editable' % (
                self.bridge.skin, data['topology']['nu'], data['topology']['nv'], len(data['active'])))
            layers = self.bridge.layers().list()
            items = {}
            for layer in layers:
                item = QtWidgets.QTreeWidgetItem([layer.name, str(round(layer.opacity*100, 3))])
                item.setData(0, QtCore.Qt.UserRole, layer.id)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if layer.enabled else QtCore.Qt.Unchecked)
                items[layer.id] = item
            for layer in sorted(layers, key=lambda l: l.index):
                parent = items.get(layer.parent_id)
                (parent.addChild if parent else self.layer_tree.addTopLevelItem)(items[layer.id])
            self.layer_tree.expandAll()
            chosen = items.get(old_layer) or (items[layers[0].id] if layers else None)
            if chosen:
                self.layer_tree.setCurrentItem(chosen)
            self._fill_influences(old_target)
            self.paint.setEnabled(bool(chosen))
            self.paint.setChecked(bool(brush.active() and brush.active().bridge.identity == self.bridge.identity))
            self.status.setText('Changes update the NURBS skin. Select a layer and an influence or channel.')
        except Exception as error:
            self.deactivate()
            self.paint.setEnabled(False)
            self.status.setText(str(error))
        finally:
            self.busy = False

    def layer_id(self):
        item = self.layer_tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None

    def layer(self):
        from ngSkinTools2 import api
        if not self.bridge or self.layer_id() is None:
            raise ValueError('Select a NURBS layer first.')
        return api.Layer.load(self.bridge.proxy_skin, self.layer_id())

    def target(self):
        item = self.influences.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None

    def _fill_influences(self, previous=None):
        self.influences.clear()
        if self.layer_id() is None:
            return
        locked = set(self.layer().locked_influences)
        data = self.bridge.data
        rows = [('Layer mask', 'mask')]
        if data['skin_method'] == 2:
            rows.append(('DQ blend', 'dq'))
        rows.extend((core.node_for(i['uuid']).rsplit('|', 1)[-1], i['logical']) for i in data['proxy_influences'])
        for text, target in rows:
            item = QtWidgets.QTreeWidgetItem([text, ''])
            item.setData(0, QtCore.Qt.UserRole, target)
            if isinstance(target, int):
                item.setCheckState(1, QtCore.Qt.Checked if target in locked else QtCore.Qt.Unchecked)
                item.setToolTip(1, 'Lock this influence in the current layer. Maya joint locks are also respected.')
            self.influences.addTopLevelItem(item)
            if target == previous:
                self.influences.setCurrentItem(item)
        if self.influences.currentItem() is None and rows:
            self.influences.setCurrentItem(self.influences.topLevelItem(1 if len(rows)>1 else 0))

    def change_layer(self):
        if self.busy:
            return
        self.deactivate()
        self.busy = True
        try:
            self._fill_influences(self.target())
        finally:
            self.busy = False

    def change_target(self):
        if not self.busy:
            self.deactivate()

    def create_bridge(self):
        if not self.shape_uuid:
            self.load_selection()
        self.bridge = core.create(core.node_for(self.shape_uuid))
        self.refresh()

    def add_layer(self):
        self.deactivate()
        if not self.bridge:
            raise ValueError('Initialize NURBS Skin Layers first.')
        self.bridge.validate()
        layer = self.bridge.layers().add('Layer %s' % (len(self.bridge.layers().list())+1), force_empty=True)
        self.refresh()
        for item in self.layer_tree.findItems(layer.name, QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive, 0):
            self.layer_tree.setCurrentItem(item)

    def remove_layer(self):
        self.deactivate()
        layer = self.layer()
        if len(self.bridge.layers().list()) <= 1:
            raise ValueError('Keep one layer, or use Bake + detach / Restore original.')
        self.bridge.layers().delete(layer)
        self.refresh()

    def move_layer(self, direction):
        self.deactivate()
        layer = self.layer()
        layer.index = max(0, layer.index+direction)
        self.refresh()

    def edit_layer(self, item, column):
        if self.busy:
            return
        self.deactivate()
        from ngSkinTools2 import api
        self.bridge.validate()
        layer = api.Layer.load(self.bridge.proxy_skin, item.data(0, QtCore.Qt.UserRole))
        with core.transaction('Edit NURBS layer'):
            if column == 0:
                layer.name = item.text(0)
                layer.enabled = item.checkState(0) == QtCore.Qt.Checked
            else:
                layer.opacity = max(0, min(100, float(item.text(1))))/100
        self.refresh()

    def lock_influence(self, item, column):
        if self.busy or column != 1:
            return
        self.deactivate()
        target = item.data(0, QtCore.Qt.UserRole)
        if isinstance(target, int):
            layer = self.layer()
            locked = set(layer.locked_influences)
            locked.add(target) if item.checkState(1) == QtCore.Qt.Checked else locked.discard(target)
            layer.locked_influences = sorted(locked)

    def controller(self):
        if self.target() is None:
            raise ValueError('Select an influence, mask or DQ channel.')
        return brush.Controller(self.bridge, self.layer().id, self.target(), self.mode.currentText(),
                                self.radius.value(), self.intensity.value(), self.value.value())

    def start_paint(self):
        self.deactivate()
        brush.start(self.controller())
        self.paint.setChecked(True)
        self.status.setText('Paint on the NURBS surface. Shift smooths; Ctrl inverts. Esc cancels the stroke.')

    def settings_changed(self, *args):
        if self.busy:
            return
        self.value.setEnabled(self.mode.currentText() not in ('Smooth', 'Sharpen'))
        controller = brush.active()
        if controller and self.bridge and controller.bridge.identity == self.bridge.identity:
            controller.cancel()
            controller.mode = self.mode.currentText()
            controller.radius = self.radius.value()
            controller.intensity = self.intensity.value()
            controller.value = self.value.value()

    def flood(self):
        self.deactivate()
        self.controller().flood()
        self.refresh()

    def detach(self, restore):
        self.deactivate()
        if not self.bridge:
            raise ValueError('No NURBS bridge is loaded.')
        self.bridge.detach(restore=restore)
        self.bridge = None
        self.refresh()
        self.status.setText('Original skin restored.' if restore else 'Composed weights baked to the native NURBS skin.')

    def export_layers(self):
        from ngSkinTools2 import api
        if not self.bridge:
            raise ValueError('Initialize NURBS Skin Layers first.')
        paths = cmds.fileDialog2(fileMode=0, caption='Export NURBS NG layers', fileFilter='NG layers (*.json)')
        if paths:
            self.bridge.validate()
            api.export_json(self.bridge.proxy_skin, paths[0])

    def deactivate(self):
        controller = brush.active()
        if controller and self.bridge and controller.bridge.identity == self.bridge.identity:
            brush.stop()
        self.paint.setChecked(False)

    def hideEvent(self, event):
        self.deactivate()
        super(NurbsPanel, self).hideEvent(event)


def build_panel(parent=None):
    """Scroll in compact docks without changing the native palette."""
    scroll = QtWidgets.QScrollArea(parent)
    scroll.setObjectName('ngNurbsSkinScroll')
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    panel = NurbsPanel(scroll)
    scroll.setWidget(panel)
    scroll.nurbs_panel = panel
    return scroll
