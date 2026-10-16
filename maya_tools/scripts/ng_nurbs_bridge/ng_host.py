"""Reversible attachment to the installed NG UI, without vendor file edits."""
from maya import cmds, OpenMayaUI as omui

from .qt import QtWidgets, wrapInstance


def _autorig_parent(parent):
    while parent:
        if parent.objectName() == 'AutoRigSkinningManager':
            return True
        parent = parent.parentWidget()
    return False


def _wrap(parent, native):
    from .ui import build_panel
    host = QtWidgets.QTabWidget(parent)
    host.setObjectName('ngNurbsStandaloneTabs')
    host.setDocumentMode(True)
    host.addTab(native, 'Layers / Paint')
    scroll = build_panel(host)
    host.addTab(scroll, 'NURBS Skin')
    def changed(index):
        from . import brush
        from ngSkinTools2.api import PaintTool
        if PaintTool.is_painting():
            cmds.setToolTo('selectSuperContext')
        brush.stop()
        if index == 1:
            scroll.nurbs_panel.refresh()
    host.currentChanged.connect(changed)
    return host


def install():
    if cmds.about(batch=True):
        return False
    from ngSkinTools2.ui import mainwindow
    if not getattr(mainwindow.build_ui, '_ng_nurbs_original', None):
        original = mainwindow.build_ui
        def build_ui(parent):
            native, options = original(parent)
            if _autorig_parent(parent):
                return native, options
            return _wrap(parent, native), options
        build_ui._ng_nurbs_original = original
        mainwindow.build_ui = build_ui
    if not cmds.about(batch=True) and cmds.workspaceControl(mainwindow.DOCK_NAME, query=True, exists=True):
        pointer = omui.MQtUtil.findControl(mainwindow.DOCK_NAME)
        widget = wrapInstance(int(pointer), QtWidgets.QWidget)
        if not widget.findChild(QtWidgets.QTabWidget, 'ngNurbsStandaloneTabs'):
            layout = widget.layout()
            if layout and layout.count() == 1 and layout.itemAt(0).widget():
                from . import brush
                from ngSkinTools2.api import PaintTool
                brush.stop()
                if PaintTool.is_painting():
                    cmds.setToolTo('selectSuperContext')
                native = layout.takeAt(0).widget()
                layout.addWidget(_wrap(widget, native))
    return True


def uninstall():
    from . import brush
    brush.stop()
    if cmds.about(batch=True):
        return
    from ngSkinTools2.ui import mainwindow
    original = getattr(mainwindow.build_ui, '_ng_nurbs_original', None)
    if original:
        mainwindow.build_ui = original
    for host in list(QtWidgets.QApplication.allWidgets()):
        if host.objectName() == 'ngNurbsStandaloneTabs':
            parent = host.parentWidget()
            native = host.widget(0)
            host.removeTab(0)
            native.setParent(parent)
            parent.layout().replaceWidget(host, native)
            host.setParent(None)
            host.deleteLater()
