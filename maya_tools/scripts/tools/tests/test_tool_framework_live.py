"""Interactive regression using an isolated namespace; never open/save a scene.

Call run() from interactive Maya after loading the updated framework modules.
The caller may redirect state.OPTION and execution._JOURNAL to test storage.
"""
import hashlib
import array
import traceback
from maya import cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
from PySide6 import QtCore, QtWidgets
from maya_tools.scripts.framework import context, adapters, execution, state
from maya_tools.scripts.ui import tool_framework_UI as ui, skinning_manager_UI as skin_ui


def weights_digest(skin, mesh):
    selection = om.MSelectionList(); selection.add(skin)
    fn = oma.MFnSkinCluster(selection.getDependNode(0))
    selection = om.MSelectionList(); selection.add(mesh)
    dag = selection.getDagPath(0); dag.extendToShape()
    component = om.MFnSingleIndexedComponent()
    vertices = component.create(om.MFn.kMeshVertComponent)
    component.addElements(range(om.MFnMesh(dag).numVertices))
    values, count = fn.getWeights(dag, vertices)
    return hashlib.sha256(array.array('d', values).tobytes()).hexdigest()


def run():
    if cmds.about(batch=True):
        raise RuntimeError('Run this regression in interactive Maya.')
    from maya_tools.scripts.tools import pose_blendshapes
    if pose_blendshapes.edit_session():
        raise RuntimeError('Finish the active sculpt before running the live regression.')
    framework, skin_panel = ui.show(), skin_ui.show()
    service = context.service()
    original_context = service.snapshot()
    selected = cmds.ls(selection=True, long=True) or []
    tool = cmds.currentCtx()
    modified = cmds.file(query=True, modified=True)
    undo = cmds.undoInfo(query=True, state=True)
    namespace = cmds.namespaceInfo(currentNamespace=True)
    baseline = set(cmds.ls(long=True))
    original_skin_tabs = skin_panel.tabs.currentIndex(), skin_panel.skin_tabs.currentIndex()
    digest = weights_digest(original_context.skin, original_context.mesh) if original_context.skin else None
    test_ns = None
    editors = []
    result = {}
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        test_ns = cmds.namespace(add='frameworkLive')
        cmds.namespace(set=test_ns)

        def character(name):
            root = cmds.createNode('transform', name=name)
            cmds.addAttr(root, longName='artRigSchema', attributeType='long', defaultValue=1)
            mesh = cmds.polyPlane(name=name + '_body', subdivisionsX=2, subdivisionsY=2)[0]
            mesh = cmds.parent(mesh, root)[0]
            joint = cmds.createNode('joint', name=name + '_joint', parent=root)
            skin = cmds.skinCluster(joint, mesh, toSelectedBones=True)[0]
            return cmds.ls(root, long=True)[0], cmds.ls(mesh, long=True)[0], skin

        first, second = character('First'), character('Second')
        service.set_root(first[0])
        assert skin_panel.current_mesh == first[1]
        cmds.select(first[1], replace=True)
        skin_panel.scene_changed()
        ng = skin_panel.pages[0].content
        assert ng is not None
        assert ng.skin_cluster.currentData() == first[2]
        poses = adapters.pose_blendshapes(); editors.append(poses)
        qa = adapters.pose_tester(); editors.append(qa)
        assert poses.mesh.text() == first[1]
        assert qa.general_rig.root == first[0]
        assert qa._report_meshes == [first[1]]
        result['shared_editor_context'] = True

        service.set_root(second[0])
        assert poses.mesh.text() == second[1]
        assert qa.general_rig.root == second[0]
        assert skin_panel.current_mesh == second[1]
        cmds.select(first[1], replace=True)
        skin_panel.scene_changed()
        assert service.snapshot().mesh == second[1]
        assert skin_panel.current_mesh == second[1]
        assert not ng.native_ui.isEnabled()
        result['foreign_selection_does_not_retarget_ng'] = True

        blocked = framework.launch_tool('skin_copy')
        assert blocked['status'] == 'blocked'
        assert execution.journal().rows[-1]['status'] == 'blocked'
        result['preflight_and_journal'] = True
        framework.profile_choice.setCurrentText('Rigging')
        framework.query.setText('Guides')
        framework.tabs.setCurrentIndex(1)
        framework.save_layout()
        framework.profile_choice.setCurrentText('Deformers')
        assert framework.scope.currentData() == 'DEFORMERS'
        framework.profile_choice.setCurrentText('Rigging')
        assert framework.query.text() == 'Guides' and framework.tabs.currentIndex() == 1
        result['profile_restore'] = True
        key = service.snapshot().key
        state.set_step(key, 'model', 'reviewed', 'Live regression review marker')
        service.set_root(first[0])
        assert state.workflow(service.snapshot().key) == {}
        service.set_root(second[0])
        assert state.workflow(key)['model']['status'] == 'reviewed'
        result['workflow_isolation'] = True

        jobs = list(framework.jobs)
        assert len(jobs) == 5
        cmds.workspaceControl(ui.WORKSPACE, edit=True, close=True)
        QtWidgets.QApplication.processEvents()
        assert all(not cmds.scriptJob(exists=job) for job in jobs)
        assert ui.show() is framework
        QtWidgets.QApplication.processEvents()
        assert len(framework.jobs) == 5
        result['hide_reopen_owns_callbacks'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        for editor in editors:
            editor.close(); editor.deleteLater()
        service._set(original_context, force=True)
        cmds.setToolTo('selectSuperContext')
        cmds.namespace(set=namespace)
        if test_ns and cmds.namespace(exists=test_ns):
            cmds.namespace(removeNamespace=test_ns, deleteNamespaceContent=True)
        cmds.select(selected, replace=True) if selected else cmds.select(clear=True)
        skin_panel.skin_tabs.setCurrentIndex(original_skin_tabs[1])
        skin_panel.tabs.setCurrentIndex(original_skin_tabs[0])
        skin_panel.scene_changed()
        if cmds.contextInfo(tool, exists=True):
            cmds.setToolTo(tool)
        cmds.undoInfo(stateWithoutFlush=undo)
        QtWidgets.QApplication.processEvents()
        result['remaining_nodes'] = sorted(set(cmds.ls(long=True)) - baseline)
        result['missing_nodes'] = sorted(baseline - set(cmds.ls(long=True)))
        result['original_skin_weights_preserved'] = digest is None or weights_digest(original_context.skin, original_context.mesh) == digest
        if not modified and not result['remaining_nodes'] and not result['missing_nodes'] and result['original_skin_weights_preserved']:
            cmds.file(modified=False)
        result['selection_preserved'] = selected == (cmds.ls(selection=True, long=True) or [])
        result['modified_flag_preserved'] = cmds.file(query=True, modified=True) == modified
    return result
