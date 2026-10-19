"""Dockable skinning workspace with embedded native plug-in interfaces."""
import traceback

from maya import cmds, OpenMayaUI as omui
try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance, isValid
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance, isValid

from maya_tools.scripts.ui import skinning_tool_adapters as adapters
from maya_tools.scripts.utils import ui_utils
from maya_tools.scripts.framework import context as framework_context

WORKSPACE = 'AutoRigSkinningWorkspaceControl'
_panel = None


def mesh_transform(node):
    node = node.split('.')[0]
    if cmds.nodeType(node) == 'mesh':
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    if not cmds.listRelatives(node, shapes=True, noIntermediate=True, type='mesh'):
        raise ValueError('Select a polygon mesh.')
    return cmds.ls(node, long=True)[0]


def skin_cluster(mesh):
    skins = cmds.ls(cmds.listHistory(mesh, pruneDagObjects=True) or [], type='skinCluster') or []
    if not skins:
        raise ValueError('The mesh has no skinCluster: ' + mesh)
    return skins[0]


class LazyPage(QtWidgets.QWidget):
    """Load native editors on demand and expose a retry for missing plug-ins."""
    def __init__(self, factory, owner):
        super(LazyPage, self).__init__(owner)
        self.factory, self.owner, self.content = factory, owner, None
        self.box = QtWidgets.QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.message = QtWidgets.QLabel('Select this tab to load its tools.')
        self.message.setWordWrap(True)
        self.box.addWidget(self.message)
        self.retry = QtWidgets.QPushButton('Load / retry')
        self.retry.clicked.connect(self.ensure)
        self.box.addWidget(self.retry)

    def ensure(self):
        if self.content is not None:
            self.refresh()
            return
        previous = set(self.owner.children())
        try:
            self.content = self.factory()
            self.box.addWidget(self.content, 1)
            ui_utils.apply_maya_style(self.owner)
            self.message.hide()
            self.retry.hide()
            self.refresh()
        except Exception as exc:
            for child in set(self.owner.children()) - previous:
                if isinstance(child, QtWidgets.QWidget):
                    child.deleteLater()
            self.message.setText(str(exc))
            self.owner.status.setText(str(exc))
            cmds.warning('Skinning Manager: ' + str(exc))
            traceback.print_exc()

    def refresh(self):
        if self.content is not None and hasattr(self.content, 'refresh'):
            self.owner.run_action(self.content.refresh, quiet=True)


class SkinningManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SkinningManager, self).__init__(parent)
        self.setObjectName('AutoRigSkinningManager')
        self.original_context = cmds.currentCtx()
        self.activated_contexts = set()
        self.jobs = []
        self.disposed = False
        self.correctives = None
        self.current_mesh = ''
        self._shared_applied = False
        self._shared_skin = ''
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        heading = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('SKINNING MANAGER')
        font = title.font(); font.setBold(True); title.setFont(font)
        heading.addWidget(title, 1)
        button = QtWidgets.QPushButton('Float / dock')
        button.clicked.connect(lambda: self.run_action(self.toggle_dock))
        heading.addWidget(button)
        root.addLayout(heading)
        row = QtWidgets.QHBoxLayout()
        self.mesh = QtWidgets.QLineEdit()
        self.mesh.setReadOnly(True)
        self.mesh.setPlaceholderText('Select a mesh in Maya')
        row.addWidget(self.mesh, 1)
        load = QtWidgets.QPushButton('From selection')
        load.clicked.connect(lambda: self.run_action(self.load_selection))
        row.addWidget(load)
        root.addLayout(row)
        self.skin_info = QtWidgets.QLabel('No mesh selected')
        self.skin_info.setWordWrap(True)
        root.addWidget(self.skin_info)
        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self.skin_tabs = QtWidgets.QTabWidget()
        self.skin_tabs.setDocumentMode(True)
        self.tabs.addTab(self.skin_tabs, 'Skinning')
        self.status = QtWidgets.QLabel('Select a mesh. Each tab contains its original tool interface.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        # Style the shell before embedding editors so their styles stay intact.
        ui_utils.apply_maya_style(self)
        self.pages = []
        factories = (
            ('NG', lambda: adapters.build_ng(self)),
            ('Smooth', lambda: adapters.BrushPanel(False, self)),
            ('Transfer', lambda: adapters.BrushPanel(True, self)),
            ('Ramp', lambda: adapters.RampPanel(self)),
            ('Utilities', self.build_utilities),
        )
        for label, factory in factories:
            page = LazyPage(factory, self)
            self.pages.append(page)
            self.skin_tabs.addTab(page, label)
        self.correctives_page = LazyPage(self.build_correctives, self)
        self.tabs.addTab(self.correctives_page, 'Corrective Blendshapes')
        self.skin_tabs.currentChanged.connect(lambda _: self.activate_page())
        self.tabs.currentChanged.connect(lambda _: self.activate_page())
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh_scene)
        self.destroyed.connect(lambda: self.dispose())
        for event in ('SelectionChanged', 'ToolChanged'):
            self.jobs.append(cmds.scriptJob(event=[event, self.scene_changed], parent=WORKSPACE))
        for event in ('SceneOpened', 'NewSceneOpened', 'Undo', 'Redo'):
            self.jobs.append(cmds.scriptJob(event=[event, self.queue_refresh], parent=WORKSPACE))
        service = framework_context.service()
        self._context_token = service.subscribe(self.apply_framework_context)
        token = self._context_token
        self.destroyed.connect(lambda *args: service.unsubscribe(token))
        self.load_selection(required=False)
        self.activate_page()

    def run_action(self, callback, quiet=False):
        if self.disposed:
            return
        try:
            return callback()
        except Exception as exc:
            self.status.setText(str(exc))
            if not quiet:
                cmds.warning('Skinning Manager: ' + str(exc))

    def queue_refresh(self, *args):
        if not self.disposed:
            self._refresh_timer.start(50)

    def scene_changed(self, *args):
        if self.disposed or not self.isVisible():
            return
        self.run_action(lambda: self.load_selection(required=False), quiet=True)
        if self.current_mesh and not cmds.objExists(self.current_mesh):
            self.current_mesh = ''
            self.mesh.clear()
            self.skin_info.setText('No mesh selected')
            self.status.setText('Select a mesh. Each tab contains its original tool interface.')
            if self.correctives:
                self.correctives.mesh.clear()
                self.correctives.blendshapes.clear()
                self.correctives.targets.clear()
        if self.tabs.currentIndex() == 0:
            self.active_page().refresh()

    def refresh_scene(self):
        if self.disposed or not self.isVisible():
            return
        self.scene_changed()
        self.correctives_page.refresh()

    def active_page(self):
        return self.skin_tabs.currentWidget() if self.tabs.currentIndex() == 0 else self.correctives_page

    def activate_page(self):
        active = self.active_page()
        self.release_brushes(except_page=active)
        active.ensure()

    def release_brushes(self, except_page=None):
        for page in getattr(self, 'pages', ()):
            if page is not except_page and page.content is not None and hasattr(page.content, 'deactivate'):
                page.content.deactivate()

    def hideEvent(self, event):
        self.release_brushes()
        super(SkinningManager, self).hideEvent(event)

    def showEvent(self, event):
        super(SkinningManager, self).showEvent(event)
        if hasattr(self, '_refresh_timer'):
            self.queue_refresh()

    def load_selection(self, required=True):
        shared = framework_context.service().snapshot()
        if shared.root and not required:
            self.apply_framework_context(shared)
            return
        selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        meshes = []
        for node in selected:
            try:
                if cmds.nodeType(node) == 'skinCluster':
                    geometry = cmds.skinCluster(node, query=True, geometry=True) or []
                    if len(geometry) != 1:
                        continue
                    mesh = mesh_transform(geometry[0])
                else:
                    mesh = mesh_transform(node)
                if mesh not in meshes:
                    meshes.append(mesh)
            except (RuntimeError, ValueError):
                pass
        if len(meshes) != 1:
            if required:
                raise ValueError('Select one polygon mesh, or vertices on one mesh.')
            return
        mesh = meshes[0]
        if mesh != self.current_mesh:
            if self.correctives:
                self.correctives.set_mesh(mesh)
            self.current_mesh = mesh
            self.mesh.setText(mesh.rsplit('|', 1)[-1])
            self.mesh.setToolTip(mesh)
        skins = cmds.ls(cmds.listHistory(mesh, pruneDagObjects=True) or [], type='skinCluster') or []
        if skins:
            count = len(cmds.skinCluster(skins[0], query=True, influence=True) or [])
            self.skin_info.setText('{}  |  {} influences'.format(skins[0], count))
        else:
            self.skin_info.setText('No skinCluster on this mesh')
        if required:
            framework_context.service().capture_selection()

    def apply_framework_context(self, active):
        if self.disposed:
            return
        if not active.root and not self._shared_applied:
            return
        if active.mesh != self.current_mesh:
            self.release_brushes()
        elif active.skin != self._shared_skin:
            # NG's explicit cluster switch already restarts its native brush
            # on the new target. Keep that session; other brushes must stop.
            self.release_brushes(except_page=self.pages[0])
        self._shared_skin = active.skin
        if active.mesh != self.current_mesh:
            if self.correctives and active.mesh:
                self.correctives.set_mesh(active.mesh)
            self.current_mesh = active.mesh
        self._shared_applied = bool(active.root)
        self.mesh.setText(active.mesh.rsplit('|', 1)[-1] if active.mesh else '')
        self.mesh.setToolTip(active.mesh)
        if not active.mesh:
            self.skin_info.setText('Choose the active mesh in Tool Framework.')
            if self.correctives:
                self.correctives.mesh.clear(); self.correctives.blendshapes.clear(); self.correctives.targets.clear()
            return
        if active.skin:
            count = len(cmds.skinCluster(active.skin, query=True, influence=True) or [])
            self.skin_info.setText('{}  |  {} influences'.format(active.skin, count))
            ng = self.pages[0].content
            if ng is not None:
                ng.choices[active.mesh] = active.skin
        else:
            self.skin_info.setText('Choose an active skinCluster in Tool Framework.' if framework_context.skins(active.mesh)
                                   else 'No skinCluster on this mesh')

    def select_mesh(self):
        if not self.current_mesh or not cmds.objExists(self.current_mesh):
            raise ValueError('Select a polygon mesh first.')
        # Keep component selections so native tools can use their vertex mask.
        selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        if not any(node == self.current_mesh or node.startswith(self.current_mesh + '|') for node in selected):
            cmds.select(self.current_mesh, replace=True)
        return self.current_mesh

    def build_correctives(self):
        from maya_tools.scripts.ui.pose_blendshapes_UI import PoseBlendshapesUI
        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        editor = PoseBlendshapesUI(scroll, embedded=True)
        # Mesh context belongs to the manager; keep sculpt controls visible
        # while the longer target/driver editor scrolls above them.
        editor.mesh.hide()
        editor.load_mesh_button.hide()
        editor.layout().removeItem(editor.editing_layout)
        editor.editing_layout.setParent(None)
        editor.layout().removeWidget(editor.status)
        scroll.setWidget(editor)
        layout.addWidget(scroll, 1)
        layout.addLayout(editor.editing_layout)
        layout.addWidget(editor.status)
        from maya_tools.scripts.tools import pose_blendshapes
        if pose_blendshapes.edit_session():
            self.current_mesh = editor.mesh.text()
            self.mesh.setText(self.current_mesh.rsplit('|', 1)[-1])
            self.mesh.setToolTip(self.current_mesh)
        elif self.current_mesh:
            editor.set_mesh(self.current_mesh)
        self.correctives = editor

        def refresh_editor():
            mesh = editor.mesh.text()
            if mesh and cmds.objExists(mesh) and not pose_blendshapes.edit_session():
                region = editor.driver_region.currentData()
                target = editor.current_target() if editor.targets.currentItem() else None
                selected = {item.data(QtCore.Qt.UserRole) for item in editor.targets.selectedItems()}
                editor.refresh()
                editor.refresh_targets(target)
                for index in range(editor.targets.count()):
                    item = editor.targets.item(index)
                    item.setSelected(item.data(QtCore.Qt.UserRole) in selected)
                editor.refresh_regions(region)
        container.refresh = refresh_editor
        io = QtWidgets.QHBoxLayout()
        for label, method in (('Export correctives', 'export_corrective_blendshapes'), ('Import correctives', 'import_corrective_blendshapes')):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, m=method: self.run_action(lambda: self.menu_action(m)))
            io.addWidget(button)
        layout.addLayout(io)
        return container

    def menu_action(self, name):
        from maya_tools.scripts.ui import auto_rig_UI
        return getattr(auto_rig_UI, name)()

    def build_utilities(self):
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        groups = (
            ('Skin weights', (
                ('Bind selected joints + mesh', self.bind),
                ('Copy skin: source then destinations', self.copy_weights),
                ('Mirror weights +X to -X', lambda: self.mirror_weights(False)),
                ('Mirror weights -X to +X', lambda: self.mirror_weights(True)),
                ('Normalize weights', self.normalize),
                ('Prune weights below 0.001', self.prune),
                ('Remove unused influences', self.remove_unused),
            )),
            ('Import / export', (
                ('Export skin (.skc)', lambda: self.menu_action('export_skin_cluster')),
                ('Import skin (.skc)', lambda: self.menu_action('import_skin_cluster')),
                ('Proxy skinning', lambda: self.menu_action('proxy_skinning')),
            )),
            ('Transfer / deformation', (
                ('Auto Skin Transfer (Clothes)', lambda: self.menu_action('open_skin_transfer_ui')),
                ('Proximity Wrap (Multiple Drivers)', lambda: self.menu_action('open_proximity_wrap_ui')),
                ('Bake Deformation to Skin', lambda: self.menu_action('open_proximity_bake_ui')),
            )),
        )
        for title, actions in groups:
            group = QtWidgets.QGroupBox(title)
            box = QtWidgets.QVBoxLayout(group)
            for label, callback in actions:
                button = QtWidgets.QPushButton(label)
                button.clicked.connect(lambda checked=False, c=callback: self.run_action(c))
                box.addWidget(button)
            layout.addWidget(group)
        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def edit_weights(self, action):
        mesh = self.select_mesh()
        skin = skin_cluster(mesh)
        cmds.undoInfo(openChunk=True, chunkName='Skinning Manager')
        try:
            action(skin, mesh)
        finally:
            cmds.undoInfo(closeChunk=True)
        self.status.setText('Weights updated: ' + mesh.rsplit('|', 1)[-1])
        self.queue_refresh()

    def normalize(self):
        self.edit_weights(lambda skin, mesh: cmds.skinCluster(skin, edit=True, forceNormalizeWeights=True))

    def prune(self):
        def prune_mesh(skin, mesh):
            vertices = cmds.filterExpand(cmds.ls(selection=True, flatten=True, long=True), selectionMask=31) or []
            vertices = [vertex for vertex in vertices if mesh_transform(vertex) == mesh]
            cmds.skinPercent(skin, vertices or [mesh], pruneWeights=0.001)
        self.edit_weights(prune_mesh)

    def remove_unused(self):
        self.edit_weights(lambda skin, mesh: cmds.skinCluster(skin, edit=True, removeUnusedInfluence=True))

    def mirror_weights(self, inverse):
        self.edit_weights(lambda skin, mesh: cmds.copySkinWeights(sourceSkin=skin, destinationSkin=skin,
            mirrorMode='YZ', mirrorInverse=inverse, surfaceAssociation='closestPoint',
            influenceAssociation=['label', 'name', 'closestJoint'], normalize=True))

    def bind(self):
        selected = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        joints = cmds.ls(selected, type='joint') or []
        meshes = []
        for node in selected:
            try:
                meshes.append(mesh_transform(node))
            except ValueError:
                pass
        if not joints or len(set(meshes)) != 1:
            raise ValueError('Select joints and one unbound mesh.')
        mesh = meshes[0]
        if cmds.ls(cmds.listHistory(mesh) or [], type='skinCluster'):
            raise ValueError('The selected mesh already has a skinCluster.')
        cmds.skinCluster(joints, mesh, toSelectedBones=True, bindMethod=0, skinMethod=0,
                         normalizeWeights=1, maximumInfluences=4, obeyMaxInfluences=True)
        self.load_selection()
        self.status.setText('Bound mesh to selected joints.')

    def copy_weights(self):
        selected = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        meshes = list(dict.fromkeys(mesh_transform(node) for node in selected))
        if len(meshes) < 2:
            raise ValueError('Select the source mesh first, then destination meshes.')
        source = skin_cluster(meshes[0])
        influences = cmds.skinCluster(source, query=True, influence=True)
        cmds.undoInfo(openChunk=True, chunkName='Copy skin weights')
        try:
            for mesh in meshes[1:]:
                try:
                    destination = skin_cluster(mesh)
                except ValueError:
                    destination = cmds.skinCluster(influences, mesh, toSelectedBones=True, normalizeWeights=1)[0]
                cmds.copySkinWeights(sourceSkin=source, destinationSkin=destination, noMirror=True,
                    surfaceAssociation='closestPoint', influenceAssociation=['name', 'closestJoint'], normalize=True)
        finally:
            cmds.undoInfo(closeChunk=True)
        self.status.setText('Skin weights copied to {} mesh(es).'.format(len(meshes) - 1))

    def toggle_dock(self):
        if cmds.workspaceControl(WORKSPACE, query=True, floating=True):
            if cmds.workspaceControl('Outliner', exists=True):
                cmds.workspaceControl(WORKSPACE, edit=True, dockToControl=('Outliner', 'right'))
            else:
                cmds.workspaceControl(WORKSPACE, edit=True, dockToMainWindow=('left', False))
        else:
            cmds.workspaceControl(WORKSPACE, edit=True, floating=True)

    def dispose(self):
        if self.disposed:
            return
        # Release the brush before deleting its callback controls.
        current = cmds.currentCtx()
        ng_paint = self.pages[0].content is not None and cmds.contextInfo(current, c=True) == 'ngst2PaintContext'
        if current in self.activated_contexts or (ng_paint and current != self.original_context):
            try:
                cmds.setToolTo(self.original_context)
            except RuntimeError:
                cmds.setToolTo('selectSuperContext')
        for job in self.jobs:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        self.jobs = []
        self._refresh_timer.stop()
        self.disposed = True
        framework_context.service().unsubscribe(self._context_token)
        for page in self.pages:
            if page.content is not None and hasattr(page.content, 'dispose'):
                page.content.dispose()


def restore():
    """Workspace uiScript entry, including a saved Maya workspace restore."""
    global _panel
    if _panel is not None and isValid(_panel) and not _panel.disposed:
        return _panel
    pointer = omui.MQtUtil.findControl(WORKSPACE)
    if not pointer:
        return None
    host = wrapInstance(int(pointer), QtWidgets.QWidget)
    layout = host.layout() or QtWidgets.QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    _panel = SkinningManager(host)
    layout.addWidget(_panel)
    return _panel


def close():
    if _panel is not None and isValid(_panel):
        _panel.dispose()


def show():
    """Open once, dock next to the Outliner, and let Maya save its layout."""
    if cmds.about(batch=True):
        raise RuntimeError('Open Skinning Manager in interactive Maya.')
    if cmds.workspaceControl(WORKSPACE, exists=True):
        cmds.workspaceControl(WORKSPACE, edit=True, restore=True)
        cmds.workspaceControl(WORKSPACE, edit=True, **{'raise': True})
        return restore()
    kwargs = dict(label='Skinning Manager', retain=False, initialWidth=480, minimumWidth=440,
                  uiScript='from maya_tools.scripts.ui import skinning_manager_UI; skinning_manager_UI.restore()',
                  closeCommand='from maya_tools.scripts.ui import skinning_manager_UI; skinning_manager_UI.close()',
                  loadImmediately=True)
    if cmds.workspaceControl('Outliner', exists=True):
        kwargs['dockToControl'] = ('Outliner', 'right')
    else:
        kwargs['dockToMainWindow'] = ('left', False)
    cmds.workspaceControl(WORKSPACE, **kwargs)
    return restore()
