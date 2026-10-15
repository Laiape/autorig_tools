"""Context-aware adapters for existing editors and file-producing actions."""
import sys
from maya import cmds
try:
    from PySide6 import QtCore
    from shiboken6 import isValid
except ImportError:
    from PySide2 import QtCore
    from shiboken2 import isValid
from maya_tools.scripts.framework import context


class EditorBinding(QtCore.QObject):
    def __init__(self, widget, kind):
        super().__init__(widget)
        self.widget = widget
        self.kind = kind
        self.bound_root = ''
        self.active = True
        self.token = context.service().subscribe(self.apply)
        service, token = context.service(), self.token
        widget.destroyed.connect(lambda *args: service.unsubscribe(token))
        widget.installEventFilter(self)
        self.apply(service.snapshot())

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Close, QtCore.QEvent.DeferredDelete):
            context.service().unsubscribe(self.token)
            self.active = False
        elif event.type() == QtCore.QEvent.Show and not self.active:
            self.token = context.service().subscribe(self.apply)
            self.active = True
            self.apply(context.service().snapshot())
        return False

    def apply(self, active):
        widget = self.widget
        if not isValid(widget):
            return
        if self.kind == 'blendshapes':
            if active.mesh:
                widget.set_mesh(active.mesh)
            elif self.bound_root:
                widget.mesh.clear(); widget.blendshapes.clear(); widget.targets.clear()
        elif self.kind == 'qa':
            panel = widget.general_rig
            panel.root = active.root or None
            panel.root_label.setText(active.root or 'Load the active character in Tool Framework.')
            if active.root:
                panel.refresh_bindings()
            else:
                panel.binding_list.clear()
            widget._report_meshes = [active.mesh] if active.mesh else []
            widget._report_mesh_label.setText(active.mesh.rsplit('|', 1)[-1] if active.mesh else 'No meshes loaded')
        elif self.kind == 'picker' and self.bound_root and active.root_uuid != self.bound_root:
            # Never auto-open a different picker on a selection callback.
            widget.close()
        self.bound_root = active.root_uuid


def follow(widget, kind):
    if widget is not None and not hasattr(widget, '_framework_binding'):
        widget._framework_binding = EditorBinding(widget, kind)
    return widget


def skinning():
    from maya_tools.scripts.ui import skinning_manager_UI
    return skinning_manager_UI.show()


def pose_blendshapes():
    from maya_tools.scripts.ui import pose_blendshapes_UI
    return follow(pose_blendshapes_UI.show(), 'blendshapes')


def pose_tester():
    from maya_tools.scripts.ui import pose_tester_UI
    pose_tester_UI.show()
    return follow(pose_tester_UI._window_instance, 'qa')


def picker():
    from maya_tools.scripts.tools import character_picker
    active = context.service().snapshot()
    return follow(character_picker.show(character=active.asset, root_uuid=active.root_uuid), 'picker')


def skin_export():
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    active = context.service().snapshot()
    selected = cmds.ls(selection=True, long=True) or []
    try:
        if active.mesh:
            cmds.select(active.mesh, replace=True)
        return SkinManager().export_skins()
    finally:
        valid = [value for value in selected if cmds.objExists(value)]
        cmds.select(valid, replace=True) if valid else cmds.select(clear=True)


def skin_source_export():
    from maya_tools.scripts.tools.mesh_data_exporter import SourceSkinExporter
    active = context.service().snapshot()
    targets = [active.mesh] if active.mesh else [value for value in cmds.ls(selection=True, long=True) or [] if context.is_mesh(value)]
    return SourceSkinExporter().export_all(meshes=targets)


def build(leg_impl='reference', leg_solver=None):
    from maya_tools.scripts.ui import auto_rig_UI
    active = context.service().snapshot()
    # The legacy build reads this existing asset selector, not the selection.
    cmds.optionVar(stringValue=('currentAssetRigName', active.asset))
    result = auto_rig_UI.rig(leg_impl=leg_impl, leg_solver=leg_solver)
    candidates = cmds.ls(active.asset, '*:' + active.asset, type='transform', long=True) or []
    if len(candidates) == 1:
        context.service().set_root(candidates[0])
    return result


def editor_layout():
    result = {}
    for module_name, variable, kind in (
        ('maya_tools.scripts.ui.skinning_manager_UI', '_panel', 'skinning'),
        ('maya_tools.scripts.ui.pose_tester_UI', '_window_instance', 'qa')):
        widget = getattr(sys.modules.get(module_name), variable, None)
        if widget is not None and isValid(widget):
            if kind == 'skinning' and not widget.disposed:
                result[kind] = [widget.tabs.currentIndex(), widget.skin_tabs.currentIndex()]
            elif kind == 'qa':
                result[kind] = [widget.general_rig.tabs.currentIndex()]
    return result


def restore_editor_layout(values):
    if not isinstance(values, dict):
        return
    for module_name, variable, kind in (
        ('maya_tools.scripts.ui.skinning_manager_UI', '_panel', 'skinning'),
        ('maya_tools.scripts.ui.pose_tester_UI', '_window_instance', 'qa')):
        widget = getattr(sys.modules.get(module_name), variable, None)
        indexes = values.get(kind)
        if widget is None or not isValid(widget) or not isinstance(indexes, list) or not all(type(i) is int for i in indexes):
            continue
        if kind == 'skinning' and len(indexes) == 2 and not widget.disposed:
            if 0 <= indexes[0] < widget.tabs.count() and 0 <= indexes[1] < widget.skin_tabs.count():
                widget.skin_tabs.setCurrentIndex(indexes[1]); widget.tabs.setCurrentIndex(indexes[0])
        elif kind == 'qa' and len(indexes) == 1 and 0 <= indexes[0] < widget.general_rig.tabs.count():
            widget.general_rig.tabs.setCurrentIndex(indexes[0])
