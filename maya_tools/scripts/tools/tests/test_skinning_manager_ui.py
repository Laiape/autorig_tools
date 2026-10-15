"""Interactive Maya 2026 regression for embedded native skinning editors.

Run with runpy.run_path(path, run_name="__main__") inside Maya, not mayapy.
Requires installed ngSkinTools2, brSmoothWeights and rampWeights modules.
Temporary scene data is removed without opening or saving a scene.
"""

from functools import wraps


def isolated_framework_context(check):
    @wraps(check)
    def run(*args, **kwargs):
        from maya import cmds
        from maya_tools.scripts.framework import context
        service = context.service()
        active, tool = service.snapshot(), cmds.currentCtx()
        had_asset = cmds.optionVar(exists='currentAssetRigName')
        asset = cmds.optionVar(query='currentAssetRigName') if had_asset else ''
        try:
            service.reset()
            return check(*args, **kwargs)
        finally:
            service._set(active, force=True)
            if had_asset:
                cmds.optionVar(stringValue=('currentAssetRigName', asset))
            else:
                cmds.optionVar(remove='currentAssetRigName')
            if cmds.contextInfo(tool, exists=True):
                cmds.setToolTo(tool)
    return run


@isolated_framework_context
def run_integration():
    import json, traceback
    from importlib import reload
    from maya import cmds, mel
    from PySide6 import QtCore, QtWidgets, QtTest
    from maya_tools.scripts.ui import skinning_manager_UI as ui
    from maya_tools.scripts.ui import skinning_tool_adapters as adapters
    from maya_tools.scripts.ui import pose_blendshapes_UI as poses_ui
    from maya_tools.scripts.tools import pose_blendshapes as poses

    result = {}
    baseline = set(cmds.ls(long=True))
    selected = cmds.ls(selection=True, long=True)
    context = cmds.currentCtx()
    modified = cmds.file(query=True, modified=True)
    undo = cmds.undoInfo(query=True, state=True)
    namespace = cmds.namespaceInfo(currentNamespace=True)
    test_ns = None
    brush_settings = {}
    try:
        assert poses.edit_session() is None, 'An existing sculpt session is active.'
        if cmds.workspaceControl(ui.WORKSPACE, exists=True):
            ui.close()
            cmds.deleteUI(ui.WORKSPACE)
            QtWidgets.QApplication.processEvents()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        reload(adapters); reload(poses_ui); reload(ui)
        p = ui.show()
        assert p is ui.show(), 'Duplicate workspace created.'
        assert not cmds.workspaceControl(ui.WORKSPACE, query=True, floating=True)
        cmds.undoInfo(stateWithoutFlush=False)
        test_ns = cmds.namespace(add='arSkinIntegration')
        cmds.namespace(set=test_ns)
        mesh = cmds.polyPlane(name='skinTest', subdivisionsX=4, subdivisionsY=4, width=4, height=4)[0]
        joints = [cmds.createNode('joint', name='L_test_JNT'), cmds.createNode('joint', name='R_test_JNT')]
        cmds.setAttr(joints[0] + '.tx', -2); cmds.setAttr(joints[1] + '.tx', 2)
        skin = cmds.skinCluster(joints, mesh, toSelectedBones=True, normalizeWeights=1)[0]
        cmds.skinPercent(skin, mesh, transformValue=[(joints[0], 1), (joints[1], 0)])
        cmds.skinPercent(skin, mesh+'.vtx[12]', transformValue=[(joints[0], 0), (joints[1], 1)])
        cmds.select(mesh, replace=True)
        p.load_selection()
        result['shared_mesh'] = p.current_mesh.endswith(mesh)
        result['brushes'] = []
        for i in (1, 2):
            p.skin_tabs.setCurrentIndex(i)
            brush = p.pages[i].content
            assert brush, p.pages[i].message.text()
            brush.activate()
            brush_settings[brush.prefix] = (cmds.currentCtx(), mel.eval('{}Context -query -strength "{}";'.format(brush.prefix, cmds.currentCtx())))
            assert brush.controls.isEnabled()
            assert len(cmds.treeView('arSkin_' + brush.prefix + 'JointTree', query=True, children='') or []) == 2
            value = 'arSkin_' + brush.prefix + 'Strength'
            native_group = adapters.native_widget(value)
            field = native_group.findChild(QtWidgets.QLineEdit)
            assert field, 'Native strength field not found.'
            field.setText('0.37')
            QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return)
            strength = mel.eval('{}Context -query -strength "{}";'.format(brush.prefix, cmds.currentCtx()))
            assert abs(strength - .37) < 1e-5, strength
            if i == 1:
                before = cmds.skinPercent(skin, mesh+'.vtx[12]', query=True, transform=joints[1])
                flood = adapters.native_widget('arSkin_brSmoothWeightsFloodButton')
                QtTest.QTest.mouseClick(flood, QtCore.Qt.LeftButton)
                after = cmds.skinPercent(skin, mesh+'.vtx[12]', query=True, transform=joints[1])
                assert abs(after-before) > .01, (before, after)
                result['smooth_flood'] = [before, after]
            # Original Tool Settings and private controls must coexist.
            mel.eval('toolPropertyWindow;')
            brush.refresh()
            result['brushes'].append({'type': brush.prefix, 'strength': strength,
                'native_context': cmds.currentCtx(), 'controls': cmds.control(value, exists=True)})
        cmds.setToolTo('selectSuperContext')
        cmds.select(mesh, replace=True)
        p.skin_tabs.setCurrentIndex(0)
        from maya import utils as maya_utils
        maya_utils.processIdleEvents()
        QtTest.QTest.qWait(150)
        ng = p.pages[0].content
        from ngSkinTools2.api.session import session
        from ngSkinTools2.api import target_info
        result['ng_state'] = {'skin': session.state.selectedSkinCluster, 'selection': cmds.ls(selection=True),
            'related': target_info.get_related_skin_cluster(mesh), 'available': session.state.layersAvailable,
            'status': p.status.text(), 'refresh': hasattr(ng, 'refresh'), 'panel_enabled': p.isEnabled(), 'ng_enabled': ng.isEnabled(),
            'handlers': len(session.events.targetChanged.signal.handlers)}
        initialize = [b for b in ng.findChildren(QtWidgets.QPushButton) if 'Initialize Skinning Layers' in b.text()]
        assert initialize and initialize[0].isEnabled(), 'NG did not follow selection: ' + str([(b.text(), b.isEnabled()) for b in ng.findChildren(QtWidgets.QPushButton)])
        initialize[0].click()
        QtWidgets.QApplication.processEvents()
        from ngSkinTools2.api import Layers
        assert len(Layers(mesh).list()) >= 1
        result['ng_layers'] = len(Layers(mesh).list())
        p.skin_tabs.setCurrentIndex(3)
        ramp = p.pages[3].content
        cmds.select(clear=True)
        mel.eval('brWeightsControllerPerformCreate rampWeights;')
        ramp_nodes = cmds.ls(type='rampWeights') or []
        assert ramp_nodes, 'Ramp create button failed.'
        result['ramp_created'] = ramp_nodes
        ramp.kind.setCurrentIndex(1)
        assert 'weightsServer' in ramp.editors
        mel.eval('brWeightsControllerPerformCreate weightsServer;')
        result['weights_server_created'] = cmds.ls(type='weightsServer')
        assert result['weights_server_created']
        ramp.kind.setCurrentIndex(0)
        cmds.select(mesh, replace=True)
        p.tabs.setCurrentIndex(1)
        editor = p.correctives
        assert editor and editor.mesh.text().endswith(mesh)
        editor.create_blendshape()
        bs = editor.current_blendshape()
        control = cmds.createNode('transform', name='L_test_CTL')
        cmds.createNode('transform', name='R_test_CTL')
        cmds.setAttr(control + '.rotateZ', 30)
        cmds.select(control, replace=True)
        dialog = poses_ui.CaptureDialog(editor)
        assert dialog.add.isEnabled(), dialog.error.text()
        dialog.create()
        assert poses.edit_session(), dialog.error.text()
        cmds.move(0, .2, 0, mesh+'.vtx[5]', relative=True, objectSpace=True)
        editor.finish(True)
        assert poses.edit_session() is None
        assert editor.targets.count() == 1
        editor.go_pose(True)
        assert cmds.getAttr(bs+'.weight[0]') == 0
        editor.go_pose(False)
        assert abs(cmds.getAttr(bs+'.weight[0]') - 1) < 1e-5
        result['corrective_capture_sculpt_save'] = True
        editor.edit_target()
        cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
        QtWidgets.QApplication.processEvents()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        p = ui.show()
        p.tabs.setCurrentIndex(1)
        editor = p.correctives
        assert poses.edit_session() and editor.save.isEnabled()
        result['corrective_session_recovered_after_close'] = True
        editor.finish(False)
        assert poses.edit_session() is None
        result['corrective_cancel'] = True
        p.tabs.setCurrentIndex(0)
        p.skin_tabs.setCurrentIndex(4)
        # Copy utility binds a fresh destination and copies from explicit skin nodes.
        destination = cmds.polyPlane(name='copyTest', subdivisionsX=4, subdivisionsY=4, width=4, height=4)[0]
        cmds.select(mesh, destination, replace=True)
        p.copy_weights()
        assert ui.skin_cluster(destination)
        p.load_selection(required=False)
        p.normalize()
        p.prune()
        result['utilities_copy_normalize_prune'] = True
        for _ in range(2):
            for i in range(5):
                p.skin_tabs.setCurrentIndex(i)
                assert p.pages[i].content
        p.skin_tabs.setCurrentIndex(1)
        p.pages[1].content.activate()
        assert len(cmds.treeView('arSkin_brSmoothWeightsJointTree', query=True, children='') or []) == 2
        p.toggle_dock()
        assert cmds.workspaceControl(ui.WORKSPACE, query=True, floating=True)
        p.toggle_dock()
        assert not cmds.workspaceControl(ui.WORKSPACE, query=True, floating=True)
        result['float_and_redock'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if poses.edit_session() and test_ns:
            try: poses.finish_edit(False)
            except Exception: pass
        for prefix, (brush_context, strength) in brush_settings.items():
            if cmds.contextInfo(brush_context, exists=True):
                mel.eval('{}Context -edit -strength {} "{}";'.format(prefix, strength, brush_context))
        cmds.setToolTo(context)
        cmds.namespace(set=namespace)
        if test_ns and cmds.namespace(exists=test_ns):
            cmds.namespace(removeNamespace=test_ns, deleteNamespaceContent=True)
        cmds.select(selected, replace=True) if selected else cmds.select(clear=True)
        cmds.undoInfo(stateWithoutFlush=undo)
        remaining = sorted(set(cmds.ls(long=True)) - baseline)
        result['remaining_test_nodes'] = remaining
        if not modified and not remaining:
            cmds.file(modified=False)
        result['status'] = ui._panel.status.text() if ui._panel else None
    return result


@isolated_framework_context
def run_lifecycle():
    import json, traceback
    from maya import cmds
    from PySide6 import QtCore, QtWidgets
    from importlib import reload
    from maya_tools.scripts.ui import skinning_manager_UI as ui
    from maya_tools.scripts.ui import pose_blendshapes_UI as poses_ui
    from ngSkinTools2.api.session import session
    try:
        result = {'cycles': []}
        for cycle in range(3):
            if cmds.workspaceControl(ui.WORKSPACE, exists=True):
                cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
                QtWidgets.QApplication.processEvents()
                QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            if cycle == 0:
                reload(poses_ui); reload(ui)
            p = ui.show()
            for i in range(5):
                p.skin_tabs.setCurrentIndex(i)
                assert p.pages[i].content, p.pages[i].message.text()
            p.tabs.setCurrentIndex(1)
            assert p.correctives, p.correctives_page.message.text()
            QtWidgets.QApplication.processEvents()
            assert p.correctives.save.isVisible(), 'Save sculpt not visible in dock footer.'
            assert p.correctives.cancel.isVisible()
            assert session.active()
            jobs = list(p.jobs)
            cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
            QtWidgets.QApplication.processEvents()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            assert p.disposed
            assert all(not cmds.scriptJob(exists=job) for job in jobs)
            assert not cmds.window('arSkin_brSmoothWeightsHost', exists=True)
            assert not cmds.window('arSkin_brTransferWeightsHost', exists=True)
            assert not cmds.window('brRampWeightsEditWin', exists=True)
            assert not cmds.window('brWeightsServerEditWin', exists=True)
            assert not session.active(), session.references
            result['cycles'].append('all native editors closed without jobs or session references')
        ui.show()
        result['reopened'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    return result


@isolated_framework_context
def run_existing_editor():
    import json, traceback
    from importlib import reload
    from maya import cmds, mel
    from PySide6 import QtCore, QtWidgets, QtTest
    from maya_tools.scripts.ui import skinning_manager_UI as ui
    from maya_tools.scripts.ui import skinning_tool_adapters as adapters
    try:
        if cmds.workspaceControl(ui.WORKSPACE, exists=True):
            cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
            QtWidgets.QApplication.processEvents()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        reload(adapters); reload(ui)
        mel.eval('source brWeightsControllerCommon; source brEditRampWeights; brEditWeightsController rampWeights;')
        native = adapters.native_widget('brRampWeightsEditWin', window=True)
        original_parent, original_flags = native.parentWidget(), native.windowFlags()
        p = ui.show()
        p.skin_tabs.setCurrentIndex(3)
        ramp = p.pages[3].content
        record = ramp.editors['rampWeights']
        assert not record['created']
        assert record.get('callbacks'), record
        switch = adapters.native_widget(record['callbacks'][0][0].rsplit('|', 1)[-1])
        QtWidgets.QApplication.processEvents()
        QtTest.QTest.mouseClick(switch, QtCore.Qt.LeftButton)
        QtTest.QTest.qWait(450)
        assert ramp.kind.currentData() == 'weightsServer', (str(type(switch)), switch.isVisible(), switch.size().toTuple(),
            record['callbacks'], [(str(type(c)), c.objectName()) for c in switch.children()])
        cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
        QtWidgets.QApplication.processEvents()
        assert cmds.window('brRampWeightsEditWin', exists=True)
        assert native.parentWidget() == original_parent
        assert native.windowFlags() == original_flags
        assert native.isVisible()
        cmds.deleteUI('brRampWeightsEditWin', window=True)
        result = {'preexisting_editor_restored': True, 'native_type_switch_integrated': True}
        ui.show()
    except Exception:
        result = {'error': traceback.format_exc()}
    return result


@isolated_framework_context
def run_ng_selector():
    import json, traceback
    from importlib import reload
    from maya import cmds
    from PySide6 import QtCore, QtWidgets
    from maya_tools.scripts.ui import skinning_manager_UI as ui
    from maya_tools.scripts.ui import skinning_tool_adapters as adapters
    from ngSkinTools2.api import Layers, PaintTool, target_info
    from ngSkinTools2.api.session import session

    result = {}
    baseline = set(cmds.ls(long=True))
    selection = cmds.ls(selection=True, long=True)
    context = cmds.currentCtx()
    modified = cmds.file(query=True, modified=True)
    undo = cmds.undoInfo(query=True, state=True)
    namespace = cmds.namespaceInfo(currentNamespace=True)
    ns = None
    paint_settings = None
    try:
        if cmds.workspaceControl(ui.WORKSPACE, exists=True):
            cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
            QtWidgets.QApplication.processEvents()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        reload(adapters); reload(ui)
        panel = ui.show()
        ng = panel.pages[0].content
        assert isinstance(ng, adapters.NGPanel), panel.pages[0].message.text()
        cmds.undoInfo(stateWithoutFlush=False)
        ns = cmds.namespace(add='ngSelectorTest')
        cmds.namespace(set=ns)
        mesh = cmds.polyPlane(name='body', subdivisionsX=4, subdivisionsY=4)[0]
        base_joints = [cmds.createNode('joint', name='baseA'), cmds.createNode('joint', name='baseB')]
        corrective_joints = [cmds.createNode('joint', name='correctiveA'), cmds.createNode('joint', name='correctiveB')]
        base = cmds.skinCluster(base_joints, mesh, name='baseSkin', toSelectedBones=True)[0]
        corrective = cmds.skinCluster(corrective_joints, mesh, name='correctiveSkin', toSelectedBones=True, multi=True)[0]
        cmds.skinPercent(base, mesh, transformValue=[(base_joints[0], .2), (base_joints[1], .8)])
        cmds.skinPercent(corrective, mesh, transformValue=[(corrective_joints[0], .75), (corrective_joints[1], .25)])
        cmds.select(mesh, replace=True)
        panel.load_selection(); ng.refresh()
        assert ng.skin_cluster.count() == 3
        result['clusters'] = [ng.skin_cluster.itemData(i) for i in range(1, ng.skin_cluster.count())]
        initialize = next(button for button in ng.native_ui.findChildren(QtWidgets.QPushButton) if button.text() == 'Initialize Skinning Layers')
        for skin, joint in ((base, base_joints[1]), (corrective, corrective_joints[1])):
            ng.skin_cluster.setCurrentIndex(ng.skin_cluster.findData(skin))
            ng.skin_cluster.activated.emit(ng.skin_cluster.currentIndex())
            assert session.state.selectedSkinCluster == skin, session.state.selectedSkinCluster
            assert initialize.isEnabled()
            initialize.click()
            layers = Layers(skin).list()
            assert len(layers) == 1
            layer = layers[0]
            layer.name = skin.rsplit(':', 1)[-1] + ' weights'
            layer.paint_target = next(info.logicalIndex for info in target_info.list_influences(skin) if (info.path or info.name).endswith(joint.rsplit(':', 1)[-1]))
            assert joint in (cmds.skinCluster(session.state.selectedSkinCluster, query=True, influence=True) or [])
            session.events.currentLayerChanged.emitIfChanged()
            session.events.currentInfluenceChanged.emitIfChanged()
        assert Layers(base).list()[0].name == 'baseSkin weights'
        assert Layers(corrective).list()[0].name == 'correctiveSkin weights'
        result['independent_layer_data'] = True
        # A component selection must keep the chosen corrective deformer target.
        cmds.select(mesh + '.vtx[12]', replace=True)
        panel.load_selection(); ng.refresh()
        assert session.state.selectedSkinCluster == corrective
        assert cmds.filterExpand(cmds.ls(selection=True), selectionMask=31)
        result['component_selection_kept'] = True
        PaintTool.start()
        assert PaintTool.is_painting()
        ng.skin_cluster.setCurrentIndex(ng.skin_cluster.findData(base))
        ng.choose_cluster()
        assert PaintTool.is_painting()
        assert session.state.selectedSkinCluster == base
        assert session.state.currentLayer.layer.name == 'baseSkin weights'
        ng.refresh()
        assert ng.skin_cluster.count() == 3
        assert ng.skin_cluster.currentData() == base
        result['switch_while_painting'] = True
        cmds.setToolTo('selectSuperContext')
        # Real native Flood action operates on this layer and leaves the other skin.
        before = Layers(corrective).list()[0].get_weights(0)
        cmds.select(base, replace=True)
        ng.refresh()
        PaintTool.start()
        session.events.toolChanged.emit()
        layer = session.state.currentLayer.layer
        layer.paint_target = 0
        brush = session.paint_tool
        paint_settings = json.dumps({'common': brush.primary_settings.to_dict(), 'mode_settings': brush.mode_settings,
                                     'projection_settings': brush.projection_settings})
        from ngSkinTools2.api.paint import PaintMode
        brush.mode = PaintMode.replace
        brush.intensity = .4
        brush.limit_to_component_selection = False
        brush.mirror = False
        session.events.currentInfluenceChanged.emitIfChanged()
        base_before = layer.get_weights(0)
        flood = next(button for button in ng.native_ui.findChildren(QtWidgets.QPushButton) if button.text() == 'Flood')
        assert flood.isEnabled()
        flood.click()
        base_after = layer.get_weights(0)
        assert any(abs(a-b) > .01 for a,b in zip(base_before,base_after)), (base_before,base_after)
        assert Layers(corrective).list()[0].get_weights(0) == before
        result['native_flood_isolated'] = True
        cmds.setToolTo('selectSuperContext')
        # Unskinned meshes have a disabled selector; returning finds both clusters.
        empty = cmds.polyCube(name='unskinned')[0]
        cmds.select(empty, replace=True); panel.load_selection(); ng.refresh()
        assert not ng.skin_cluster.isEnabled()
        cmds.select(mesh, replace=True); panel.load_selection(); ng.refresh()
        assert ng.skin_cluster.count() == 3, (panel.current_mesh, cmds.ls(selection=True),cmds.ls(type='skinCluster'),
            cmds.listHistory(mesh),cmds.listHistory(mesh,pruneDagObjects=True),cmds.listRelatives(mesh,children=True,fullPath=True),cmds.ls(type='mesh',long=True),
            [(ng.skin_cluster.itemText(i),ng.skin_cluster.itemData(i)) for i in range(ng.skin_cluster.count())])
        result['mesh_changes'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        cmds.setToolTo(context)
        if paint_settings is not None:
            session.paint_tool.storage_func_save(paint_settings)
            session.paint_tool.load_settings()
        cmds.namespace(set=namespace)
        if ns and cmds.namespace(exists=ns):
            cmds.namespace(removeNamespace=ns, deleteNamespaceContent=True)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
        cmds.undoInfo(stateWithoutFlush=undo)
        result['remaining_nodes'] = sorted(set(cmds.ls(long=True)) - baseline)
        if not modified and not result['remaining_nodes']:
            cmds.file(modified=False)
        ui._panel.scene_changed()
    return result


@isolated_framework_context
def run_brush_lifecycle():
    """Check real brush contexts without drawing any strokes on user geometry."""
    import traceback
    from maya import cmds, mel
    from PySide6 import QtWidgets
    from maya_tools.scripts.ui import skinning_manager_UI as ui
    from maya_tools.scripts.tools import pose_blendshapes

    if pose_blendshapes.edit_session():
        raise RuntimeError('Finish the existing sculpt session before this regression.')
    panel = ui.show()
    selection, context = cmds.ls(selection=True, long=True), cmds.currentCtx()
    namespace = cmds.namespaceInfo(currentNamespace=True)
    original_mesh = panel.current_mesh
    original_tabs = panel.tabs.currentIndex(), panel.skin_tabs.currentIndex()
    baseline = set(cmds.ls(long=True))
    modified = cmds.file(query=True, modified=True)
    undo = cmds.undoInfo(query=True, state=True)
    test_ns = None
    result = {}
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        test_ns = cmds.namespace(add='arBrushLifecycle')
        cmds.namespace(set=test_ns)
        mesh = cmds.polyPlane(name='brushTest', subdivisionsX=2, subdivisionsY=2)[0]
        joint = cmds.createNode('joint', name='testJoint')
        skin = cmds.skinCluster(joint, mesh, toSelectedBones=True)[0]
        vertices = cmds.ls(mesh + '.vtx[*]', flatten=True)
        weights = [cmds.skinPercent(skin, vertex, query=True, value=True) for vertex in vertices]
        cmds.select(mesh, replace=True)
        panel.load_selection()
        panel.tabs.setCurrentIndex(0)
        for index in (1, 2):
            panel.skin_tabs.setCurrentIndex(index)
            brush = panel.pages[index].content
            assert brush is not None, panel.pages[index].message.text()
            brush.activate()
            assert cmds.currentCtx() == brush.context
            assert not mel.eval('{}Context -query -message {};'.format(brush.prefix, brush.context))
            for _ in range(3):
                panel.scene_changed()
                assert cmds.currentCtx() == brush.context
                assert not mel.eval('{}Context -query -message {};'.format(brush.prefix, brush.context))
            panel.skin_tabs.setCurrentIndex(4)
            assert cmds.currentCtx() == 'selectSuperContext', 'Inactive tab kept its paint context.'
            panel.skin_tabs.setCurrentIndex(index)
            brush.activate()
            panel.hide()
            QtWidgets.QApplication.processEvents()
            assert cmds.currentCtx() == 'selectSuperContext', 'Hidden manager kept its paint context.'
            panel.show()
            assert cmds.currentCtx() == 'selectSuperContext', 'Showing the panel reactivated painting.'
            result[brush.prefix] = 'quiet banner, tab exit and hide release verified'
        result['weights_preserved'] = [cmds.skinPercent(skin, vertex, query=True, value=True)
                                       for vertex in vertices] == weights
        assert result['weights_preserved']
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        panel.release_brushes()
        panel.current_mesh = original_mesh
        panel.mesh.setText(original_mesh.rsplit('|', 1)[-1])
        panel.mesh.setToolTip(original_mesh)
        cmds.namespace(set=namespace)
        if test_ns and cmds.namespace(exists=test_ns):
            cmds.namespace(removeNamespace=test_ns, deleteNamespaceContent=True)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
        panel.skin_tabs.setCurrentIndex(original_tabs[1])
        panel.tabs.setCurrentIndex(original_tabs[0])
        cmds.setToolTo(context)
        cmds.undoInfo(stateWithoutFlush=undo)
        result['remaining_test_nodes'] = sorted(set(cmds.ls(long=True)) - baseline)
        if not modified and not result['remaining_test_nodes']:
            cmds.file(modified=False)
        panel.scene_changed()
    return result


def run():
    from maya import cmds
    if cmds.about(batch=True):
        raise RuntimeError('Run this integration test in interactive Maya.')
    results = {}
    for check in (run_ng_selector, run_integration, run_lifecycle, run_existing_editor, run_brush_lifecycle):
        result = check()
        if 'error' in result:
            raise AssertionError(result['error'])
        results[check.__name__] = result
        print('PASS: ' + check.__name__)
    return results


if __name__ == '__main__':
    run()
