"""Interactive tests for the independent and AutoRig hosts. Disposable GUI only."""
from pathlib import Path


def run(output):
    from maya import cmds, OpenMayaUI as legacy_ui
    from maya.api import OpenMaya as om, OpenMayaUI as omui
    from ng_nurbs_bridge import core, brush, ng_host
    from ng_nurbs_bridge.qt import QtCore, QtWidgets, wrapInstance
    from PySide6 import QtTest
    from ngSkinTools2.ui import mainwindow
    from maya_tools.scripts.ui import skinning_manager_UI

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    def stage(name):
        (output/'stage.txt').write_text(name)
    result = {}
    import faulthandler
    faulthandler.dump_traceback_later(12, file=(output/'hang_stack.log').open('w'))
    stage('new scene')
    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True)
    surface = cmds.nurbsPlane(name='paintSurface', patchesU=4, patchesV=6,
                              axis=(0, 1, 0), width=8, constructionHistory=False)[0]
    joints = [cmds.createNode('joint', name='influence%s' % i) for i in range(3)]
    cmds.setAttr(joints[0]+'.tx', -3)
    cmds.setAttr(joints[2]+'.tx', 3)
    skin = cmds.skinCluster(joints, surface, toSelectedBones=True)[0]
    cmds.select(surface)
    stage('install standalone host')
    ng_host.install()
    mainwindow.open()
    QtWidgets.QApplication.processEvents()
    cmds.evalDeferred(lambda: None)
    QtTest.QTest.qWait(200)
    stage('find standalone tabs')
    pointer = legacy_ui.MQtUtil.findControl(mainwindow.DOCK_NAME)
    widget = wrapInstance(int(pointer), QtWidgets.QWidget)
    tabs = widget.findChild(QtWidgets.QTabWidget, 'ngNurbsStandaloneTabs')
    assert tabs is not None, 'Standalone NG attachment did not appear.'
    assert [tabs.tabText(i) for i in range(tabs.count())] == ['Layers / Paint', 'NURBS Skin']
    ng_host.install()
    assert len(widget.findChildren(QtWidgets.QTabWidget, 'ngNurbsStandaloneTabs')) == 1
    tabs.setCurrentIndex(1)
    panel = tabs.widget(1).nurbs_panel
    panel.load_selection()
    stage('create bridge')
    panel.create_bridge()
    stage('add layer')
    assert panel.bridge is not None
    assert panel.layer_tree.topLevelItemCount() == 1
    result['standalone_tabs'] = [tabs.tabText(i) for i in range(tabs.count())]
    panel.add_layer()
    stage('layer added')
    assert panel.layer_tree.topLevelItemCount() == 2
    panel.intensity.setValue(1)
    panel.value.setValue(.8)
    stage('flood')
    panel.flood()
    stage('start paint')
    assert panel.target() is not None
    # Select an influence explicitly, not mask or DQ.
    for i in range(panel.influences.topLevelItemCount()):
        item = panel.influences.topLevelItem(i)
        if item.data(0, QtCore.Qt.UserRole) == 0:
            panel.influences.setCurrentItem(item)
            break
    panel.value.setValue(.2)
    panel.start_paint()
    stage('set camera')
    controller = brush.active()
    assert controller is not None
    cmds.lookThru('top')
    cmds.select(surface)
    cmds.viewFit('top', fitFactor=.7)
    cmds.refresh(force=True)
    stage('camera refreshed')
    QtTest.QTest.qWait(200)
    view = omui.M3dView.active3dView()
    view_widget = wrapInstance(int(view.widget()), QtWidgets.QWidget)
    x, y, visible = view.worldToView(om.MPoint(0, 0, 0))
    assert visible
    before = core.layer_snapshot(panel.bridge, panel.layer_id())
    pos = QtCore.QPoint(x, view.portHeight()-y)
    stage('viewport mouse press')
    QtTest.QTest.mousePress(view_widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    stage('viewport mouse move')
    QtTest.QTest.mouseMove(view_widget, pos+QtCore.QPoint(15, 0), 60)
    QtTest.QTest.mouseRelease(view_widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos+QtCore.QPoint(15, 0))
    stage('stroke released')
    QtWidgets.QApplication.processEvents()
    cmds.refresh(force=True)
    result['stroke_dabs'] = controller.dabs
    result['stroke_error'] = controller.error
    result['context'] = cmds.currentCtx()
    assert controller.dabs > 0, 'The actual MPxContext did not receive a painted dab: '+controller.error
    after = core.layer_snapshot(panel.bridge, panel.layer_id())
    assert before != after, 'Viewport stroke did not edit the selected NG layer.'
    cmds.undo()
    assert core.layer_snapshot(panel.bridge, panel.layer_id()) == before
    cmds.redo()
    assert core.layer_snapshot(panel.bridge, panel.layer_id()) == after
    # Capture the real native panel and the actual viewport with its brush overlay.
    widget.resize(600, 760)
    QtWidgets.QApplication.processEvents()
    widget.grab().save(str(output/'standalone_ng.png'))
    view_widget.grab().save(str(output/'surface_brush.png'))
    color = om.MImage()
    view.readColorBuffer(color, True)
    color.writeToFile(str(output/'surface_brush_buffer.png'), 'png')
    tabs.setCurrentIndex(0)
    assert brush.active() is None
    result['standalone_tool_release'] = True
    manager = skinning_manager_UI.show()
    stage('autorig host')
    manager.pages[0].ensure()
    ng = manager.pages[0].content
    assert ng is not None, manager.pages[0].message.text()
    labels = [ng.editor_tabs.tabText(i) for i in range(ng.editor_tabs.count())]
    assert labels == ['Layers / Paint', 'Loop Rigger (Preview)', 'NURBS Skin'], labels
    ng.editor_tabs.setCurrentIndex(2)
    cmds.select(surface)
    ng.nurbs_skin.load_selection()
    ng.nurbs_skin.start_paint()
    assert brush.active() is not None
    ng.editor_tabs.setCurrentIndex(1)
    assert brush.active() is None
    ng.editor_tabs.setCurrentIndex(2)
    assert all(not a.isEnabled() for actions in ng.rigger_actions.values() for a in actions)
    ng.resize(620, 780)
    QtWidgets.QApplication.processEvents()
    ng.grab().save(str(output/'autorig_ng.png'))
    result['autorig_tabs'] = labels
    result['autorig_tool_release'] = True
    result['callbacks'] = len(ng.nurbs_skin.callbacks)
    ng_host.uninstall()
    QtWidgets.QApplication.processEvents()
    assert not widget.findChild(QtWidgets.QTabWidget, 'ngNurbsStandaloneTabs')
    result['standalone_unhook'] = True
    faulthandler.cancel_dump_traceback_later()
    return result
