"""Host installed skinning UIs without editing their installation files."""
import json
from pathlib import Path
import re

from maya import cmds, mel, OpenMayaUI as omui
from maya_tools.scripts.utils import ui_utils
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance, isValid
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance, isValid


def native_widget(name, window=False):
    pointer = omui.MQtUtil.findWindow(name) if window else omui.MQtUtil.findLayout(name)
    if not pointer:
        pointer = omui.MQtUtil.findControl(name)
    if not pointer:
        raise RuntimeError("Maya UI could not be found: " + name)
    return wrapInstance(int(pointer), QtWidgets.QWidget)


def module_scripts(module):
    try:
        return Path(cmds.moduleInfo(moduleName=module, path=True)) / 'scripts'
    except RuntimeError:
        raise RuntimeError("Install the {} Maya module before using this tab.".format(module))


def load_plugin(name):
    if not cmds.pluginInfo(name, query=True, loaded=True):
        cmds.loadPlugin(name, quiet=True)


def build_ng(parent):
    return NGPanel(parent)


class NGPanel(QtWidgets.QWidget):
    """Use native NG selection routing to choose a stacked skinCluster."""
    def __init__(self, owner):
        super(NGPanel, self).__init__(owner)
        from ngSkinTools2.ui.mainwindow import build_ui
        from ngSkinTools2.ui.paintContextCallbacks import definePaintContextCallbacks
        from ngSkinTools2.api.session import session
        self.owner = owner
        self.session = session
        self.choices = {}
        self.last_mesh = None
        self.last_skins = []
        self.busy = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel('SkinCluster'))
        self.skin_cluster = QtWidgets.QComboBox()
        self.skin_cluster.setObjectName('ngSkinClusterSelector')
        self.skin_cluster.setMinimumContentsLength(12)
        self.skin_cluster.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.skin_cluster.setToolTip('Choose the skinCluster NG edits on this mesh. Selected vertices are preserved.')
        row.addWidget(self.skin_cluster, 1)
        layout.addLayout(row)
        definePaintContextCallbacks()
        self.native_ui, self._autorig_options = build_ui(self)
        ui_utils.preserve_style(self.native_ui, subtree=True)
        self.install_rigger_actions()
        self.editor_tabs = QtWidgets.QTabWidget()
        self.editor_tabs.setDocumentMode(True)
        self.editor_tabs.addTab(self.native_ui, 'Layers / Paint')
        from maya_tools.scripts.ui.facial_loop_skinning_UI import LoopRiggerPanel
        self.loop_rigger = LoopRiggerPanel(self)
        loop_scroll = QtWidgets.QScrollArea()
        loop_scroll.setWidgetResizable(True)
        loop_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        loop_scroll.setWidget(self.loop_rigger)
        self.editor_tabs.addTab(loop_scroll, 'Loop Rigger (Preview)')
        self.ensure_nurbs_tab()
        self.editor_tabs.currentChanged.connect(self.change_editor_tab)
        layout.addWidget(self.editor_tabs, 1)
        self.skin_cluster.activated.connect(lambda _: owner.run_action(self.choose_cluster))
        ui_utils.apply_maya_style(self)
        self.refresh()

    def ensure_nurbs_tab(self):
        """The same dependency-free package also attaches to standalone NG."""
        if hasattr(self, 'nurbs_skin'):
            return self.nurbs_skin
        from ng_nurbs_bridge.ui import build_panel
        self.nurbs_scroll = build_panel(self.editor_tabs)
        self.nurbs_skin = self.nurbs_scroll.nurbs_panel
        self.editor_tabs.addTab(self.nurbs_scroll, 'NURBS Skin')
        return self.nurbs_skin

    def install_rigger_actions(self):
        """Extend the native layer context menu without patching vendor files."""
        from maya_tools.scripts.tools.facial_loop_riggers import RIGGERS
        action_type = getattr(QtGui, 'QAction', None) or QtWidgets.QAction
        self.rigger_actions = {}
        trees = [tree for tree in self.native_ui.findChildren(QtWidgets.QTreeWidget)
                 if tree.headerItem().text(0) == 'Layers']
        if not trees:
            raise RuntimeError('NG native layer list could not be found.')
        for tree in trees:
            hosts = [tree]
            ancestor = tree.parentWidget()
            while ancestor and ancestor is not self.native_ui:
                if isinstance(ancestor, QtWidgets.QStackedWidget):
                    # The layer list is hidden before the first NG layer exists.
                    # Expose the same actions on the native initialization page.
                    hosts.append(ancestor.widget(0)); break
                ancestor = ancestor.parentWidget()
            for host in hosts:
                for old in list(host.actions()):
                    if old.objectName().startswith('autorigFacialRigger'):
                        host.removeAction(old); old.deleteLater()
                separator = action_type(host)
                separator.setObjectName('autorigFacialRiggerSeparator')
                separator.setSeparator(True); host.addAction(separator)
                host.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
                for kind, label in RIGGERS:
                    action = action_type(label, host)
                    action.setObjectName('autorigFacialRigger_' + kind)
                    action.setToolTip('Use the selected loop and existing influences of the active skinCluster. New masks are black.')
                    action.triggered.connect(lambda checked=False, k=kind: self.owner.run_action(lambda: self.run_rigger(k)))
                    host.addAction(action)
                    self.rigger_actions.setdefault(kind, []).append(action)
        self.refresh_rigger_actions()

    def refresh_rigger_actions(self):
        skin = self.skin_cluster.currentData() or self.session.state.selectedSkinCluster
        available = bool(skin and cmds.objExists(skin))
        if hasattr(self, 'editor_tabs') and self.editor_tabs.currentIndex() == 2:
            available = False
        for actions in getattr(self, 'rigger_actions', {}).values():
            for action in actions:
                action.setEnabled(available)

    def run_rigger(self, kind):
        from maya_tools.scripts.tools import facial_loop_riggers
        skin = self.skin_cluster.currentData() or self.session.state.selectedSkinCluster
        selected = cmds.ls(selection=True, long=True) or []
        result = facial_loop_riggers.apply(kind, skin, selection=selected)
        self.select_cluster(skin)
        self.session.events.targetChanged.emitIfChanged()
        self.session.events.layerListChanged.emitIfChanged()
        self.session.events.currentLayerChanged.emitIfChanged()
        self.owner.status.setText('{}: {} joint loops, {} vertices. New masks are black.{}'.format(
            result['layer'], result['assignments'], result['vertices'],
            ' Mirrored L to R.' if result['mirrored'] else ''))
        return result

    def change_editor_tab(self, index):
        self.deactivate()
        self.skin_cluster.setEnabled(index != 2 and bool(self.last_skins))
        if index == 1:
            self.loop_rigger.refresh_review()
        elif index == 2:
            self.nurbs_skin.run(lambda: self.nurbs_skin.load_selection(required=False))
            self.nurbs_skin.refresh()
        self.refresh_rigger_actions()

    def select_cluster(self, cluster):
        """NG resolves the last selected node, including skinCluster nodes.

        Keep a component mask, and append the explicit deformer target. Use
        native selection instead of overriding the shared NG session state.
        """
        from ngSkinTools2.api import PaintTool
        painting = PaintTool.is_painting()
        if painting:
            cmds.setToolTo('selectSuperContext')
        selected = cmds.ls(selection=True, long=True) or []
        components = [item for item in selected if any(token in item for token in ('.vtx[', '.e[', '.f['))
                      and self.mesh_for(item) == self.owner.current_mesh]
        cmds.select(components + [cluster], replace=True, noExpand=True)
        self.session.events.nodeSelectionChanged.emit()
        if painting:
            self.session.paint_tool.start()

    @staticmethod
    def mesh_for(node):
        node = node.split('.')[0]
        if cmds.nodeType(node) == 'mesh':
            return (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
        return node if cmds.listRelatives(node, shapes=True, type='mesh') else None

    def clusters_for(self, mesh):
        if not mesh or not cmds.objExists(mesh):
            return []
        skins = cmds.ls(cmds.listHistory(mesh, pruneDagObjects=True) or [], type='skinCluster') or []
        # NG's temporary paint display can hide the normal output shape from
        # listHistory(transform). The deformers still own the original shape.
        if not skins:
            from ngSkinTools2.api import PaintTool
            if PaintTool.is_painting():
                candidates = self.last_skins if mesh == self.last_mesh else cmds.ls(type='skinCluster') or []
                for skin in candidates:
                    if cmds.objExists(skin) and any(self.mesh_for(shape) == mesh for shape in
                            cmds.ls(cmds.skinCluster(skin, query=True, geometry=True) or [], long=True) or []):
                        skins.append(skin)
        self.last_mesh = mesh
        self.last_skins = list(dict.fromkeys(skins))
        return self.last_skins

    def choose_cluster(self):
        cluster = self.skin_cluster.currentData()
        if not cluster or not cmds.objExists(cluster):
            self.refresh()
            return
        self.busy = True
        try:
            self.choices[self.owner.current_mesh] = cluster
            self.select_cluster(cluster)
        finally:
            self.busy = False
        from maya_tools.scripts.framework import context as framework_context
        if framework_context.service().snapshot().root:
            framework_context.service().set_skin(cluster)
        self.refresh()

    def deactivate(self):
        if hasattr(self, 'nurbs_skin'):
            self.nurbs_skin.deactivate()
        from ngSkinTools2.api import PaintTool
        if PaintTool.is_painting():
            cmds.setToolTo('selectSuperContext')

    def refresh(self):
        if self.busy:
            return
        if hasattr(self, 'nurbs_skin') and self.editor_tabs.currentIndex() == 2:
            self.nurbs_skin.refresh()
            self.refresh_rigger_actions()
            return
        self.busy = True
        try:
            mesh = self.owner.current_mesh
            skins = self.clusters_for(mesh)
            selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
            explicit = next((node for node in reversed(selected) if node in skins), None)
            choice = explicit or self.choices.get(mesh)
            from maya_tools.scripts.framework import context as framework_context
            shared = framework_context.service().snapshot()
            if shared.root:
                choice = shared.skin
            if explicit and not shared.root:
                self.choices[mesh] = explicit
            # Keep an explicit choice when the user returns to mesh/vertex
            # selection; NG otherwise resolves the first skin in its history.
            if choice in skins and not explicit and any(self.mesh_for(node) == mesh for node in selected):
                self.select_cluster(choice)
            self.session.events.nodeSelectionChanged.emit()
            active = self.session.state.selectedSkinCluster
            if shared.root:
                related = any(node == shared.skin or self.mesh_for(node) == shared.mesh for node in selected)
                editable = bool(shared.skin) and related and active == shared.skin
                self.native_ui.setEnabled(editable)
                if not editable:
                    self.deactivate()
                if shared.skin in skins:
                    active = shared.skin
            else:
                self.native_ui.setEnabled(True)
            previous = self.skin_cluster.blockSignals(True)
            try:
                self.skin_cluster.clear()
                self.skin_cluster.addItem('Choose skinCluster' if skins else 'No skinCluster on this mesh', None)
                for skin in skins:
                    self.skin_cluster.addItem(skin, skin)
                self.skin_cluster.setCurrentIndex(max(0, self.skin_cluster.findData(active)))
                self.skin_cluster.setEnabled(bool(skins))
            finally:
                self.skin_cluster.blockSignals(previous)
            if active in skins:
                count = len(cmds.skinCluster(active, query=True, influence=True) or [])
                self.owner.skin_info.setText('{}  |  {} influences'.format(active, count))
            self.refresh_rigger_actions()
        finally:
            self.busy = False


def br_namespace(name):
    return 'arSkin_' + name


def adapt_br_source(source, filename):
    """Give MEL controls/callbacks private names; keep the plug-in commands.

    The shipped property builder always targets Maya's global Tool Settings.
    Its scoped copy accepts our host layout instead. Resources, icons and the
    installed scripts remain untouched; original Tool Settings still work.
    """
    source = re.sub(r'^\s*source\s+br(?:Smooth|Transfer)Weights\w*[^;]*;', '', source, flags=re.M)
    private_procs = re.findall(r'(?:global\s+)?proc\s+(?:(?:string|int|float|vector|matrix)(?:\[\])?\s+)?(\w+)\s*\(', source)
    local_names = {name: 'arSkin_{}_{}'.format(Path(filename).stem, name)
                   for name in private_procs if not name.startswith(('brSmoothWeights', 'brTransferWeights'))}
    for name, replacement in local_names.items():
        source = re.sub(r'\b' + re.escape(name) + r'\b', replacement, source)

    def replace_token(match):
        token = match.group(0)
        if token in ('brSmoothWeightsContext', 'brTransferWeightsContext', 'brSmoothWeightsCmd', 'brTransferWeightsCmd'):
            return token
        # Icon filenames and resource keys belong to the installed plug-in.
        if re.match(r'\.(?:svg|png|mel)\b', source[match.end():]):
            return token
        return br_namespace(token)

    source = re.sub(r'(?<![\w])br(?:Smooth|Transfer)Weights\w*', replace_token, source)
    source = re.sub(r'\bg(?:Smooth|Transfer)Weights\w*', lambda m: 'arSkin_' + m.group(0), source)
    if filename.endswith('Properties.mel'):
        pattern = r'(global proc arSkin_br(?:Smooth|Transfer)WeightsProperties)\(\)'
        source, count = re.subn(pattern, r'\1(string $parent)', source)
        if count != 1:
            raise RuntimeError("Unsupported brush property builder: " + filename)
        source, count = re.subn(r'string \$parent = `toolPropertyWindow -query -location`;', '', source)
        if count != 1:
            raise RuntimeError("Unsupported Tool Settings parent: " + filename)
        source = re.sub(r'columnLayout (arSkin_br(?:Smooth|Transfer)Weights);',
                        r'columnLayout -adjustableColumn true \1;', source)
    return source


class BrushPanel(QtWidgets.QWidget):
    def __init__(self, transfer, owner):
        super(BrushPanel, self).__init__(owner)
        self.owner = owner
        self.prefix = 'brTransferWeights' if transfer else 'brSmoothWeights'
        self.context = self.prefix + 'Context1'
        self.native_host = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        self.activate_button = QtWidgets.QPushButton('PAINT TRANSFER' if transfer else 'PAINT SMOOTH')
        self.activate_button.setMinimumHeight(32)
        self.activate_button.clicked.connect(lambda: owner.run_action(self.activate))
        layout.addWidget(self.activate_button)
        self.hint = QtWidgets.QLabel('Activate the brush to edit its settings.')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        try:
            self.build_native(layout)
        except Exception:
            self.dispose()
            self.deleteLater()
            raise

    def build_native(self, layout):
        load_plugin('brSmoothWeights')
        scripts = module_scripts('brSmoothWeights')
        for suffix in ('ShowInViewMessage', 'InfluenceList', 'Properties', 'Values'):
            path = scripts / (self.prefix + suffix + '.mel')
            if not path.is_file():
                raise RuntimeError("Missing installed brush script: " + str(path))
            mel.eval('source ' + json.dumps(path.as_posix()) + ';')
            mel.eval(adapt_br_source(path.read_text(encoding='utf-8-sig'), path.name))
        self.native_host = cmds.window('arSkin_{}Host'.format(self.prefix), title='Skinning brush host')
        host_layout = cmds.columnLayout(adjustableColumn=True, parent=self.native_host)
        mel.eval('{}({});'.format(br_namespace(self.prefix + 'Properties'), json.dumps(host_layout)))
        self.controls = native_widget(host_layout)
        ui_utils.preserve_style(self.controls, subtree=True)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(self.controls)
        layout.addWidget(scroll, 1)
        # MEL globals outlive the Qt panel. A new tree must not inherit the
        # old panel's "same mesh / same joint count" shortcut.
        mel.eval(br_namespace(self.prefix + 'Clear') + ';')
        ui_utils.apply_maya_style(self)
        self.refresh()

    def activate(self):
        self.owner.select_mesh()
        mel.eval('source {0}ToolCtx; {0}ToolCtx;'.format(self.prefix))
        self.context = cmds.currentCtx()
        self.owner.activated_contexts.add(self.context)
        # Keep brush help in this panel instead of a persistent viewport banner.
        mel.eval('{}Context -edit -message false {};'.format(self.prefix, json.dumps(self.context)))
        cmds.inViewMessage(clear='topCenter')
        self.refresh()

    def deactivate(self):
        """A brush activated here must not keep painting from another tab."""
        if cmds.currentCtx() == self.context and self.context in self.owner.activated_contexts:
            cmds.setToolTo('selectSuperContext')
            cmds.inViewMessage(clear='topCenter')

    def refresh(self):
        if not isValid(self.controls):
            return
        active = cmds.currentCtx().startswith(self.prefix + 'Context')
        self.controls.setEnabled(active)
        self.hint.setText('LMB: paint. MMB: adjust. Shift/Ctrl: select/deselect.'
                          if active else 'Activate the brush to edit its settings.')
        if active:
            mel.eval('{}({});'.format(br_namespace(self.prefix + 'OptionValues'), json.dumps(cmds.currentCtx())))
            if self.prefix == 'brTransferWeights':
                mel.eval(br_namespace(self.prefix + 'SetFieldLabels') + ';')
            mel.eval(br_namespace(self.prefix + 'GetSelection') + ';')

    def dispose(self):
        self.deactivate()
        if self.native_host and cmds.window(self.native_host, exists=True):
            cmds.deleteUI(self.native_host, window=True)
        self.native_host = None


class RampPanel(QtWidgets.QWidget):
    def __init__(self, owner):
        super(RampPanel, self).__init__(owner)
        self.owner = owner
        self.editors = {}
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        self.kind = QtWidgets.QComboBox()
        self.kind.addItem('Ramp Weights', 'rampWeights')
        self.kind.addItem('Weights Server', 'weightsServer')
        layout.addWidget(self.kind)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.kind.currentIndexChanged.connect(lambda _: owner.run_action(self.ensure_editor))
        try:
            self.ensure_editor()
        except Exception:
            self.dispose()
            self.deleteLater()
            raise

    def ensure_editor(self):
        kind = self.kind.currentData()
        record = self.editors.get(kind)
        if record and isValid(record['widget']):
            self.stack.setCurrentWidget(record['widget'])
            return
        load_plugin(kind)
        scripts = module_scripts('rampWeights')
        cmds.optionVar(stringValue=('brWeightsControllerContentPath', str(scripts.parent).replace('\\', '/')))
        for stem in ('brWeightsControllerCreateMenuItems', 'brWeightsControllerCommon', 'brEditRampWeights', 'brEditWeightsServer'):
            mel.eval('source ' + json.dumps((scripts / (stem + '.mel')).as_posix()) + ';')
        prefix = mel.eval('brWeightsControllerGetPrefixByName({});'.format(json.dumps(kind)))
        name = prefix + 'EditWin'
        existing = cmds.window(name, exists=True)
        if not existing:
            mel.eval('brEditWeightsController {};'.format(kind))
        widget = native_widget(name, window=True)
        ui_utils.preserve_style(widget, subtree=True)
        record = {'name': name, 'widget': widget, 'created': not existing,
                  'parent': widget.parentWidget(), 'flags': widget.windowFlags(), 'visible': widget.isVisible(),
                  'geometry': widget.saveGeometry(), 'minimum': widget.minimumSize(),
                  'policy': widget.sizePolicy()}
        # Redirect the editor's built-in type switch back into this same panel.
        for control in cmds.lsUI(controls=True, long=True) or []:
            if not control.startswith(name + '|'):
                continue
            try:
                command = cmds.iconTextButton(control, query=True, command=True)
                if 'brWeightsControllerCloseUI' in command and 'brEditWeightsController' in command:
                    record.setdefault('callbacks', []).append((control, command, cmds.iconTextButton(control, query=True, doubleClickCommand=True)))
                    switch = lambda *args: self.kind.setCurrentIndex(1 - self.kind.currentIndex())
                    cmds.iconTextButton(control, edit=True, command=switch, doubleClickCommand=switch)
            except RuntimeError:
                pass
            try:
                if cmds.button(control, query=True, label=True) == 'Close':
                    record.setdefault('close_buttons', []).append(control)
                    cmds.button(control, edit=True, manage=False)
            except RuntimeError:
                pass
        widget.setParent(self.stack)
        widget.setWindowFlags(QtCore.Qt.Widget)
        widget.setMinimumSize(0, 0)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        widget.show()
        self.editors[kind] = record

    def refresh(self):
        record = self.editors.get(self.kind.currentData())
        if record and isValid(record['widget']):
            return
        self.ensure_editor()

    def dispose(self):
        for record in self.editors.values():
            if not isValid(record['widget']):
                continue
            if record['created']:
                if cmds.window(record['name'], exists=True):
                    cmds.deleteUI(record['name'], window=True)
            else:
                record['widget'].setParent(record['parent'])
                record['widget'].setWindowFlags(record['flags'])
                record['widget'].setMinimumSize(record['minimum'])
                record['widget'].setSizePolicy(record['policy'])
                record['widget'].restoreGeometry(record['geometry'])
                for control in record.get('close_buttons', []):
                    cmds.button(control, edit=True, manage=True)
                for control, command, double_click in record.get('callbacks', []):
                    try:
                        cmds.iconTextButton(control, edit=True, command=command, doubleClickCommand=double_click)
                    except RuntimeError:
                        pass
                record['widget'].setVisible(record['visible'])
        self.editors.clear()
