"""Native dockable catalogue for the existing AutoRig tool editors."""
import json
import traceback

from maya import cmds, OpenMayaUI as omui
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance, isValid
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance, isValid

from maya_tools.scripts.framework import registry, context, execution, state
from maya_tools.scripts.utils import ui_utils
from maya_tools.scripts.ui import framework_panels

WORKSPACE = 'AutoRigToolFrameworkWorkspaceControl'
PREFERENCES = 'AutoRigToolFrameworkPreferencesV1'
_panel = None


def _read_preferences():
    try:
        data = json.loads(cmds.optionVar(query=PREFERENCES)) if cmds.optionVar(exists=PREFERENCES) else {}
        if not isinstance(data, dict):
            return set(), []
        favorites = data.get('favorites', [])
        recent = data.get('recent', [])
        favorites = favorites if isinstance(favorites, list) else []
        recent = recent if isinstance(recent, list) else []
        valid = lambda items: list(dict.fromkeys(item for item in items if isinstance(item, str) and item in registry.BY_ID))
        return set(valid(favorites)), valid(recent)[:12]
    except (ValueError, TypeError, RuntimeError):
        return set(), []


class ToolFramework(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('AutoRigToolFramework')
        self.setMinimumWidth(300)
        self.favorites, self.recent = _read_preferences()
        self._busy = False
        self.disposed = False
        self.jobs = []
        self._profile_name = 'All tools'
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        heading = QtWidgets.QHBoxLayout()
        mark = QtWidgets.QLabel()
        mark.setPixmap(QtGui.QPixmap(registry.icon_path('framework')).scaled(
            32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        heading.addWidget(mark)
        title = QtWidgets.QLabel('AUTORIG TOOLS')
        font = title.font(); font.setBold(True); title.setFont(font)
        heading.addWidget(title, 1)
        self.dock_button = QtWidgets.QToolButton()
        self.dock_button.setText('Float / dock')
        self.dock_button.setToolTip('Detach this panel or dock it on the right of Maya')
        self.dock_button.clicked.connect(self.toggle_dock)
        heading.addWidget(self.dock_button)
        layout.addLayout(heading)
        profile_row = QtWidgets.QHBoxLayout()
        self.profile_choice = QtWidgets.QComboBox()
        self.profile_choice.setAccessibleName('Work profile')
        self.profile_choice.addItems(list(state.PROFILES))
        self.profile_choice.currentTextChanged.connect(self.change_profile)
        profile_row.addWidget(self.profile_choice, 1)
        save = QtWidgets.QPushButton('Save layout')
        save.clicked.connect(self.save_layout)
        profile_row.addWidget(save)
        layout.addLayout(profile_row)
        self.context_panel = framework_panels.ContextPanel(self)
        layout.addWidget(self.context_panel)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, 1)
        tools_page = QtWidgets.QWidget()
        self.tabs.addTab(tools_page, 'Tools')
        outer_layout = layout
        layout = QtWidgets.QVBoxLayout(tools_page)
        layout.setContentsMargins(0, 6, 0, 0)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText('Search tools, workflows or keywords...')
        self.query.setClearButtonEnabled(True)
        self.query.addAction(QtGui.QIcon(registry.icon_path('search')), QtWidgets.QLineEdit.LeadingPosition)
        self.query.setAccessibleName('Search AutoRig tools')
        layout.addWidget(self.query)
        self.scope = QtWidgets.QComboBox()
        self.scope.setAccessibleName('Tool category')
        self.scope.addItem('All tools', 'all')
        self.scope.addItem(QtGui.QIcon(registry.icon_path('favorite')), 'Favorites', 'favorites')
        self.scope.addItem('Recently used', 'recent')
        for group in registry.GROUPS:
            self.scope.addItem(group.title(), group)
            for section in registry.SECTIONS.get(group, ()):
                self.scope.addItem('{} / {}'.format(group.title(), section), group + ':' + section)
        layout.addWidget(self.scope)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setIconSize(QtCore.QSize(20, 20))
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(False)
        self.tree.setMinimumHeight(180)
        self.tree.setAccessibleName('AutoRig tool catalogue')
        layout.addWidget(self.tree, 1)
        self.count = QtWidgets.QLabel()
        layout.addWidget(self.count)
        self.tool_title = QtWidgets.QLabel('Select a tool')
        self.tool_title.setWordWrap(True)
        font = self.tool_title.font(); font.setBold(True); self.tool_title.setFont(font)
        layout.addWidget(self.tool_title)
        self.description = QtWidgets.QLabel('Choose a tool to see its workflow. Double-click or press Open to launch it.')
        self.description.setWordWrap(True)
        self.description.setMinimumHeight(58)
        layout.addWidget(self.description)
        self.requirements_label = QtWidgets.QLabel()
        self.requirements_label.setWordWrap(True)
        layout.addWidget(self.requirements_label)
        actions = QtWidgets.QHBoxLayout()
        self.favorite_button = QtWidgets.QPushButton('Favorite')
        self.favorite_button.setIcon(QtGui.QIcon(registry.icon_path('favorite')))
        self.favorite_button.setCheckable(True)
        self.favorite_button.clicked.connect(self.toggle_favorite)
        actions.addWidget(self.favorite_button)
        self.open_button = QtWidgets.QPushButton('Open tool')
        self.open_button.clicked.connect(lambda: self.launch_selected())
        actions.addWidget(self.open_button, 1)
        layout.addLayout(actions)
        self.status = QtWidgets.QLabel('Ready. Existing editors open in their own tool windows.')
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        outer_layout.addWidget(self.status)
        self.workflow = framework_panels.WorkflowPanel(self)
        self.tabs.addTab(self.workflow, 'Workflow')
        self.activity = framework_panels.ActivityPanel(self)
        self.tabs.addTab(self.activity, 'Activity')
        self.query.textChanged.connect(self.refresh)
        self.scope.currentIndexChanged.connect(self.refresh)
        self.tree.currentItemChanged.connect(self.describe)
        self.tree.itemDoubleClicked.connect(lambda item, column: self.launch_selected())
        self.query.returnPressed.connect(self.launch_selected)
        ui_utils.apply_maya_style(self)
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.scene_changed)
        service = context.service()
        self.context_token = service.subscribe(self.context_changed)
        token = self.context_token
        self.destroyed.connect(lambda *args: service.unsubscribe(token))
        self.refresh()
        name = state.read().get('active_profile', 'All tools')
        if not isinstance(name, str) or name not in state.PROFILES:
            name = 'All tools'
        self.profile_choice.blockSignals(True)
        self.profile_choice.setCurrentText(name)
        self.profile_choice.blockSignals(False)
        self._profile_name = name
        self.apply_profile(name)

    def persist(self):
        cmds.optionVar(stringValue=(PREFERENCES, json.dumps({
            'favorites': sorted(self.favorites), 'recent': self.recent})))

    def selected_id(self):
        item = self.tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None

    def refresh(self, *args):
        previous = self.selected_id()
        scope = self.scope.currentData()
        ids = self.favorites if scope == 'favorites' else self.recent if scope == 'recent' else None
        group_filter, _, section_filter = scope.partition(':')
        tools = registry.search(self.query.text(), group_filter if group_filter in registry.GROUPS else None,
                                ids, section_filter or None)
        if scope == 'recent':
            tools.sort(key=lambda tool: self.recent.index(tool.id))
        self.tree.blockSignals(True)
        self.tree.clear()
        groups, sections, items = {}, {}, {}
        if scope != 'recent':
            tools.sort(key=lambda tool: (registry.GROUPS.index(tool.group),
                registry.SECTIONS[tool.group].index(tool.section) if tool.section else -1))
        for tool in tools:
            if scope == 'recent':
                parent = self.tree
            else:
                if tool.group not in groups:
                    group = QtWidgets.QTreeWidgetItem(self.tree, [tool.group])
                    group.setFlags(group.flags() & ~QtCore.Qt.ItemIsSelectable)
                    group.setData(0, QtCore.Qt.UserRole + 1, tool.group)
                    group.setSizeHint(0, QtCore.QSize(0, 26))
                    font = group.font(0); font.setBold(True); group.setFont(0, font)
                    group.setExpanded(True)
                    groups[tool.group] = group
                parent = groups[tool.group]
                if tool.section:
                    key = (tool.group, tool.section)
                    if key not in sections:
                        section = QtWidgets.QTreeWidgetItem(parent, [tool.section])
                        section.setFlags(section.flags() & ~QtCore.Qt.ItemIsSelectable)
                        section.setData(0, QtCore.Qt.UserRole + 1, tool.group + ':' + tool.section)
                        section.setSizeHint(0, QtCore.QSize(0, 26))
                        section.setExpanded(bool(self.query.text().strip()) or bool(section_filter) or scope == 'favorites')
                        sections[key] = section
                    parent = sections[key]
            item = QtWidgets.QTreeWidgetItem(parent, [tool.label])
            item.setSizeHint(0, QtCore.QSize(0, 28))
            item.setIcon(0, QtGui.QIcon(registry.icon_path(tool.icon)))
            item.setData(0, QtCore.Qt.UserRole, tool.id)
            item.setToolTip(0, tool.unavailable or tool.description)
            if tool.unavailable:
                item.setForeground(0, self.palette().brush(QtGui.QPalette.Disabled, QtGui.QPalette.Text))
            items[tool.id] = item
        self.tool_items = items
        selected = items.get(previous) or next(iter(items.values()), None)
        if selected:
            self.tree.setCurrentItem(selected)
            ancestor = selected.parent()
            while ancestor:
                ancestor.setExpanded(True)
                ancestor = ancestor.parent()
        self.tree.blockSignals(False)
        self.count.setText('{} / {} entries'.format(len(tools), len(registry.TOOLS)))
        self.describe()

    def describe(self, *args):
        tool = registry.BY_ID.get(self.selected_id())
        check = execution.preflight(tool.id) if tool else execution.Preflight()
        self.favorite_button.setEnabled(tool is not None and not self._busy)
        self.open_button.setEnabled(tool is not None and check.ready and not self._busy)
        self.favorite_button.setChecked(bool(tool and tool.id in self.favorites))
        self.favorite_button.setText('Favorited' if self.favorite_button.isChecked() else 'Favorite')
        self.tool_title.setText(tool.label if tool else 'No matching tools')
        self.description.setText((tool.unavailable or tool.description) if tool else 'Change the search or category to see more tools.')
        self.open_button.setText('Run action' if tool and tool.replaces_scene else 'Open tool')
        self.open_button.setIcon(QtGui.QIcon(registry.icon_path(tool.icon)) if tool else QtGui.QIcon())
        self.requirements_label.setText(' '.join(check.errors or check.warnings))

    def toggle_favorite(self, *args):
        tool_id = self.selected_id()
        if tool_id:
            if tool_id in self.favorites:
                self.favorites.remove(tool_id)
            else:
                self.favorites.add(tool_id)
            self.persist()
            self.refresh()

    @staticmethod
    def _allow_scene_replacement(tool):
        answer = cmds.confirmDialog(title=tool.label,
            message='This build replaces the current scene. Save your work before continuing.',
            button=['Save and build', 'Build without saving', 'Cancel'],
            defaultButton='Cancel', cancelButton='Cancel', dismissString='Cancel')
        if answer == 'Cancel':
            return False
        if answer == 'Save and build':
            if cmds.file(query=True, sceneName=True):
                cmds.file(save=True)
            else:
                from maya import mel
                mel.eval('SaveSceneAs;')
            return bool(cmds.file(query=True, sceneName=True)) and not cmds.file(query=True, modified=True)
        return answer == 'Build without saving'

    def launch_selected(self, *args):
        tool_id = self.selected_id()
        return self.launch_tool(tool_id)

    def launch_tool(self, tool_id):
        if not tool_id or self._busy:
            return
        tool = registry.BY_ID[tool_id]
        self._busy = True
        self.context_panel.setEnabled(False)
        self.profile_choice.setEnabled(False)
        self.describe()
        try:
            result = execution.run(tool_id, confirm=self._allow_scene_replacement)
            if result['status'] in ('opened', 'returned', 'completed'):
                self.recent = ([tool_id] + [item for item in self.recent if item != tool_id])[:12]
                self.persist()
                self.refresh()
            self.status.setText('Launched: ' + tool.label if result['status'] == 'opened' else result['message'])
            if result['status'] == 'failed':
                cmds.warning('AutoRig Tools: ' + result['message'])
                print(result['traceback'])
            return result
        except Exception as exc:
            self.status.setText('Unable to launch {}: {}'.format(tool.label, exc))
            cmds.warning('AutoRig Tools: ' + str(exc))
            traceback.print_exc()
        finally:
            self._busy = False
            self.context_panel.setEnabled(True)
            self.profile_choice.setEnabled(True)
            self.describe()
            self.workflow.refresh()

    def context_action(self, callback):
        try:
            callback()
        except (ValueError, RuntimeError) as exc:
            self.status.setText(str(exc))
            self.context_panel.refresh()

    def context_changed(self, active):
        if not self.disposed:
            self.context_panel.refresh()
            self.describe()
            self.workflow.refresh()

    def scene_changed(self):
        if not self.disposed:
            context.service().refresh()
            self.context_panel.refresh()
            self.describe()
            self.workflow.refresh()

    def scene_reset(self, *args):
        context.service().reset()

    def view(self):
        from maya_tools.scripts.framework import adapters
        expanded = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded() and item.data(0, QtCore.Qt.UserRole + 1):
                expanded.append(item.data(0, QtCore.Qt.UserRole + 1))
            iterator += 1
        return dict(scope=self.scope.currentData(), query=self.query.text(), tab=self.tabs.currentIndex(),
                    selected=self.selected_id(), expanded=expanded, editors=adapters.editor_layout())

    def save_layout(self, *args):
        state.save_profile(self._profile_name, self.view())
        self.status.setText('Saved work profile: ' + self._profile_name)

    def change_profile(self, name):
        if name not in state.PROFILES:
            return
        state.save_profile(self._profile_name, self.view())
        self._profile_name = name
        self.apply_profile(name)
        state.save_profile(name, self.view())

    def apply_profile(self, name):
        from maya_tools.scripts.framework import adapters
        saved = state.profile(name)
        self.query.setText(saved['query'] if isinstance(saved['query'], str) else '')
        self.scope.setCurrentIndex(max(0, self.scope.findData(saved['scope'])))
        tab = saved['tab']
        self.tabs.setCurrentIndex(tab if type(tab) is int and 0 <= tab < self.tabs.count() else 0)
        self.refresh()
        selected = self.tool_items.get(saved['selected']) if isinstance(saved['selected'], str) else None
        if selected:
            self.tree.setCurrentItem(selected)
        if isinstance(saved['expanded'], list):
            iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
            while iterator.value():
                item = iterator.value()
                key = item.data(0, QtCore.Qt.UserRole + 1)
                if key:
                    item.setExpanded(key in saved['expanded'])
                iterator += 1
        adapters.restore_editor_layout(saved['editors'])

    def showEvent(self, event):
        super().showEvent(event)
        if not cmds.about(batch=True) and cmds.workspaceControl(WORKSPACE, exists=True) and not self.jobs:
            for name in ('SelectionChanged', 'Undo', 'Redo'):
                self.jobs.append(cmds.scriptJob(event=[name, lambda *args: self._refresh_timer.start(100)], parent=WORKSPACE))
            for name in ('SceneOpened', 'NewSceneOpened'):
                self.jobs.append(cmds.scriptJob(event=[name, self.scene_reset], parent=WORKSPACE))
        self.scene_changed()

    def hideEvent(self, event):
        if not self.disposed:
            state.save_profile(self._profile_name, self.view())
            self.stop_callbacks()
        super().hideEvent(event)

    def stop_callbacks(self):
        self._refresh_timer.stop()
        for job in self.jobs:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        self.jobs = []

    def dispose(self):
        if not self.disposed:
            state.save_profile(self._profile_name, self.view())
            self.stop_callbacks()
            self.disposed = True
            context.service().unsubscribe(self.context_token)

    def toggle_dock(self):
        if cmds.workspaceControl(WORKSPACE, exists=True):
            if cmds.workspaceControl(WORKSPACE, query=True, floating=True):
                cmds.workspaceControl(WORKSPACE, edit=True, dockToMainWindow=('right', False))
            else:
                cmds.workspaceControl(WORKSPACE, edit=True, floating=True)


def restore():
    """Rebuild the native panel when Maya restores a saved workspace."""
    global _panel
    if _panel is not None and isValid(_panel):
        return _panel
    pointer = omui.MQtUtil.findControl(WORKSPACE)
    if not pointer:
        return None
    host = wrapInstance(int(pointer), QtWidgets.QWidget)
    # Reuse an existing panel if only this Python module was reloaded.
    _panel = host.findChild(QtWidgets.QWidget, 'AutoRigToolFramework')
    if _panel is None:
        layout = host.layout() or QtWidgets.QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        _panel = ToolFramework(host)
        layout.addWidget(_panel)
    return _panel


def show():
    """Open once and dock on the right; Maya owns workspace persistence."""
    if cmds.about(batch=True):
        raise RuntimeError('Open the Tool Framework in interactive Maya.')
    if cmds.workspaceControl(WORKSPACE, exists=True):
        cmds.workspaceControl(WORKSPACE, edit=True, restore=True)
        cmds.workspaceControl(WORKSPACE, edit=True, **{'raise': True})
        return restore()
    cmds.workspaceControl(WORKSPACE, label='AutoRig Tool Framework', retain=True,
        initialWidth=360, minimumWidth=300, dockToMainWindow=('right', False),
        uiScript='from maya_tools.scripts.ui import tool_framework_UI; tool_framework_UI.restore()',
        loadImmediately=True)
    return restore()
