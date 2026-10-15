"""Native context, guided workflow and operation history panels."""
import json
from pathlib import Path
try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets
from maya import cmds
from maya_tools.scripts.framework import context, execution, registry, state


class ContextPanel(QtWidgets.QGroupBox):
    def __init__(self, owner):
        super().__init__('Character context', owner)
        self.owner = owner
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(8, 6, 8, 6)
        row = QtWidgets.QHBoxLayout()
        self.root = QtWidgets.QLabel('No active character')
        self.root.setWordWrap(True)
        row.addWidget(self.root, 1)
        load = QtWidgets.QPushButton('Use selection')
        load.clicked.connect(lambda: owner.context_action(context.service().capture_selection))
        row.addWidget(load)
        clear = QtWidgets.QToolButton(); clear.setText('Clear')
        clear.clicked.connect(lambda: owner.context_action(context.service().clear))
        row.addWidget(clear)
        form.addRow(row)
        self.asset = QtWidgets.QComboBox()
        self.asset.addItem('Choose asset...', '')
        for name in context.assets():
            self.asset.addItem(name, name)
        self.asset.activated.connect(lambda _: owner.context_action(lambda: context.service().set_asset(self.asset.currentData())))
        form.addRow('Asset', self.asset)
        self.mesh = QtWidgets.QComboBox()
        self.mesh.setMinimumContentsLength(8)
        self.mesh.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mesh.activated.connect(lambda _: owner.context_action(lambda: context.service().set_mesh(self.mesh.currentData())))
        form.addRow('Mesh', self.mesh)
        self.skin = QtWidgets.QComboBox()
        self.skin.setMinimumContentsLength(8)
        self.skin.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.skin.activated.connect(lambda _: owner.context_action(lambda: context.service().set_skin(self.skin.currentData())))
        form.addRow('SkinCluster', self.skin)
        self.select = QtWidgets.QPushButton('Select active mesh')
        self.select.clicked.connect(self.select_mesh)
        form.addRow(self.select)
        self.refresh()

    def select_mesh(self):
        active = context.service().snapshot()
        if active.mesh:
            cmds.select(active.mesh, replace=True)

    def refresh(self):
        active = context.service().snapshot()
        label = active.root.rsplit('|', 1)[-1] if active.root else 'No active character'
        self.root.setText(label)
        self.root.setToolTip(active.root + ('\nNamespace: ' + active.namespace if active.namespace else ''))
        for combo in (self.asset, self.mesh, self.skin):
            combo.blockSignals(True)
        self.asset.setCurrentIndex(max(0, self.asset.findData(active.asset)))
        self.mesh.clear(); self.mesh.addItem('Choose active mesh...', '')
        for mesh in context.meshes(active.root):
            self.mesh.addItem(mesh.rsplit('|', 1)[-1], mesh)
            self.mesh.setItemData(self.mesh.count() - 1, mesh, QtCore.Qt.ToolTipRole)
        self.mesh.setCurrentIndex(max(0, self.mesh.findData(active.mesh)))
        self.skin.clear(); self.skin.addItem('Choose skinCluster...', '')
        for skin in context.skins(active.mesh):
            self.skin.addItem(skin, skin)
        self.skin.setCurrentIndex(max(0, self.skin.findData(active.skin)))
        for combo in (self.asset, self.mesh, self.skin):
            combo.blockSignals(False)
        self.select.setEnabled(bool(active.mesh))


class WorkflowPanel(QtWidgets.QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        layout = QtWidgets.QVBoxLayout(self)
        self._shown_step = None
        self.character = QtWidgets.QLabel()
        self.character.setWordWrap(True)
        layout.addWidget(self.character)
        self.steps = QtWidgets.QTreeWidget()
        self.steps.setHeaderLabels(['Step', 'Review'])
        self.steps.setRootIsDecorated(False)
        for step_id, label, tool_id, description in state.STEPS:
            item = QtWidgets.QTreeWidgetItem(self.steps, [label, 'Pending'])
            item.setData(0, QtCore.Qt.UserRole, step_id)
            item.setToolTip(0, description)
        self.steps.setCurrentItem(self.steps.topLevelItem(0))
        layout.addWidget(self.steps, 1)
        self.description = QtWidgets.QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.note = QtWidgets.QLineEdit()
        self.note.setPlaceholderText('Review note; required when skipping a step')
        layout.addWidget(self.note)
        self.open = QtWidgets.QPushButton('Open step tool')
        self.open.clicked.connect(self.open_step)
        layout.addWidget(self.open)
        row = QtWidgets.QHBoxLayout()
        self.mark = QtWidgets.QPushButton('Mark reviewed')
        self.mark.clicked.connect(lambda: self.record('reviewed'))
        row.addWidget(self.mark)
        self.skip = QtWidgets.QPushButton('Skip step')
        self.skip.clicked.connect(lambda: self.record('skipped'))
        row.addWidget(self.skip)
        self.next = QtWidgets.QPushButton('Next')
        self.next.clicked.connect(self.next_step)
        row.addWidget(self.next)
        layout.addLayout(row)
        note = QtWidgets.QLabel('Review marks are your checklist. Actual quality results remain in Model Checker, Test Rig and package validation.')
        note.setWordWrap(True); layout.addWidget(note)
        self.steps.currentItemChanged.connect(self.describe)
        self.refresh()

    def step(self):
        item = self.steps.currentItem()
        step_id = item.data(0, QtCore.Qt.UserRole) if item else state.STEPS[0][0]
        return next(step for step in state.STEPS if step[0] == step_id)

    def describe(self, *args):
        step = self.step()
        active = context.service().snapshot()
        check = execution.preflight(step[2], active)
        self.description.setText(step[3] + ('\n' + ' '.join(check.errors) if check.errors else ''))
        self.open.setEnabled(bool(active.key) and check.ready and not self.owner._busy)
        saved = state.workflow(active.key).get(step[0], {})
        if self._shown_step != (active.key, step[0]):
            self.note.setText(saved.get('note', '') if isinstance(saved, dict) else '')
            self._shown_step = (active.key, step[0])

    def refresh(self):
        active = context.service().snapshot()
        self.character.setText('Workflow: ' + (active.root.rsplit('|', 1)[-1] or active.asset or 'load a character or asset'))
        saved = state.workflow(active.key)
        for index in range(self.steps.topLevelItemCount()):
            item = self.steps.topLevelItem(index)
            entry = saved.get(item.data(0, QtCore.Qt.UserRole), {})
            item.setText(1, entry.get('status', 'pending').replace('_', ' ').title() if isinstance(entry, dict) else 'Pending')
        self.mark.setEnabled(bool(active.key) and not self.owner._busy)
        self.skip.setEnabled(bool(active.key) and not self.owner._busy)
        self.describe()

    def open_step(self):
        step = self.step()
        key = context.service().snapshot().key
        result = self.owner.launch_tool(step[2])
        if result and result['status'] in ('opened', 'returned', 'completed'):
            state.set_step(key, step[0], 'in_progress', self.note.text())
            self.refresh()

    def record(self, status):
        try:
            state.set_step(context.service().snapshot().key, self.step()[0], status, self.note.text())
            self.refresh()
        except ValueError as exc:
            self.owner.status.setText(str(exc))

    def next_step(self):
        index = next(i for i, step in enumerate(state.STEPS) if step[0] == self.step()[0])
        self.steps.setCurrentItem(self.steps.topLevelItem(min(index + 1, len(state.STEPS) - 1)))


class ActivityPanel(QtWidgets.QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        layout = QtWidgets.QVBoxLayout(self)
        self.rows = QtWidgets.QTreeWidget()
        self.rows.setHeaderLabels(['Tool', 'Result', 'ms'])
        self.rows.setRootIsDecorated(False)
        layout.addWidget(self.rows, 1)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(170)
        layout.addWidget(self.details)
        export = QtWidgets.QPushButton('Export operation history...')
        export.clicked.connect(self.export)
        layout.addWidget(export)
        self.rows.currentItemChanged.connect(self.describe)
        log = execution.journal()
        self.token = log.subscribe(self.refresh)
        token = self.token
        self.destroyed.connect(lambda *args: log.unsubscribe(token))
        self.refresh()

    def refresh(self):
        self.rows.clear()
        for entry in reversed(execution.journal().rows):
            item = QtWidgets.QTreeWidgetItem(self.rows, [entry.get('tool', ''), entry['status'], str(entry.get('duration_ms', ''))])
            item.setData(0, QtCore.Qt.UserRole, entry)
        self.rows.resizeColumnToContents(1)
        self.rows.setColumnWidth(0, max(100, self.width() - 180))
        self.details.setPlainText('Local log: ' + str(execution.journal().path) +
            ('\nLog write failed: ' + execution.journal().io_error if execution.journal().io_error else ''))

    def describe(self, item, *args):
        if item:
            entry = item.data(0, QtCore.Qt.UserRole)
            self.details.setPlainText(json.dumps(entry, indent=2))

    def export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export operation history', '', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(execution.journal().rows, indent=2), encoding='utf-8')
            except OSError as exc:
                self.details.setPlainText(str(exc))
