"""Catalogue contract and real native Qt interaction, run with mayapy."""
import ast
import os
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'maya_tools' / 'scripts'))
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from maya_tools.scripts.framework import registry


class CatalogueTests(unittest.TestCase):
    def test_every_adapter_exists_and_accepts_its_arguments(self):
        for tool in registry.TOOLS:
            module, function = tool.entrypoint.split(':')
            path = ROOT.joinpath(*module.split('.')).with_suffix('.py')
            functions = {node.name: node for node in ast.parse(path.read_text(encoding='utf-8')).body
                         if isinstance(node, ast.FunctionDef)}
            with self.subTest(tool=tool.id):
                self.assertIn(function, functions)
                arguments = functions[function].args
                allowed = {arg.arg for arg in arguments.args + arguments.kwonlyargs}
                self.assertTrue(arguments.kwarg or set(tool.kwargs).issubset(allowed))
                self.assertIn(tool.group, registry.GROUPS)
                self.assertTrue(Path(registry.icon_path(tool.icon)).is_file())
                self.assertTrue(Path(registry.icon_path(tool.icon, 'svg')).is_file())

    def test_workflow_search_can_find_nested_features(self):
        self.assertIn('pose_tester', [tool.id for tool in registry.search('surface contact')])
        self.assertIn('skinning', [tool.id for tool in registry.search('ngSkinTools')])
        self.assertEqual([tool.id for tool in registry.search('skin', ids={'skin_import'})], ['skin_import'])
        self.assertEqual(registry.search('skin', group='MODELING'), [])
        self.assertEqual(registry.search('BUILD LEG')[0].id, 'build_leg')

    def test_unfinished_legacy_action_is_never_imported(self):
        with patch.object(registry, 'import_module') as load:
            with self.assertRaisesRegex(RuntimeError, 'unfinished'):
                registry.invoke('build_leg')
            load.assert_not_called()


class NativePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from maya_tools.scripts.ui import tool_framework_UI
        cls.ui = tool_framework_UI
        cls.app = cls.ui.QtWidgets.QApplication.instance() or cls.ui.QtWidgets.QApplication([])
        cls.ui.QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf')
        cls.app.setFont(cls.ui.QtGui.QFont('Arial', 9))
        import maya.standalone
        maya.standalone.initialize(name='python')

    def setUp(self):
        self.cmds = self.ui.cmds
        from maya_tools.scripts.framework import execution, state, context
        self.tmp = tempfile.TemporaryDirectory()
        self.old_journal = execution._JOURNAL
        execution._JOURNAL = execution.Journal(Path(self.tmp.name) / 'operations.jsonl')
        self.old_option = state.OPTION
        state.OPTION = 'AutoRigFrameworkTestStateV2'
        self.cmds.optionVar(remove=state.OPTION)
        context.service().reset()
        self.owned = []
        self.cmds.optionVar(remove=self.ui.PREFERENCES)
        self.panel = self.ui.ToolFramework()

    def tearDown(self):
        from maya_tools.scripts.framework import execution, state, context
        self.panel.dispose()
        self.panel.close()
        self.panel.deleteLater()
        self.cmds.optionVar(remove=self.ui.PREFERENCES)
        self.app.processEvents()
        self.cmds.optionVar(remove=state.OPTION)
        state.OPTION = self.old_option
        execution._JOURNAL = self.old_journal
        context.service().reset()
        valid = [node for node in self.owned if self.cmds.objExists(node)]
        if valid:
            self.cmds.delete(valid)
        self.tmp.cleanup()

    def character(self, label):
        root = self.cmds.createNode('transform', name=label)
        self.cmds.addAttr(root, longName='artRigSchema', attributeType='long', defaultValue=1)
        mesh = self.cmds.polyPlane(name=label + '_body', subdivisionsX=2, subdivisionsY=2)[0]
        mesh = self.cmds.parent(mesh, root)[0]
        joint = self.cmds.createNode('joint', name=label + '_joint', parent=root)
        skin = self.cmds.skinCluster(joint, mesh, toSelectedBones=True)[0]
        self.owned.extend([root, skin])
        return self.cmds.ls(root, long=True)[0], self.cmds.ls(mesh, long=True)[0], skin

    def asset_inputs(self, label='FrameworkAsset'):
        from maya_tools.scripts.framework import context
        assets = Path(self.tmp.name) / 'assets'
        for folder, filename, data in (('models', label + '.ma', '// Test input; never built'),
                                        ('guides', label + '.guides', '{"guides": [1]}'),
                                        ('build', label + '.build', '{"build": true}')):
            path = assets / label / folder / filename
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(data)
        patcher = patch.object(context, 'ASSETS', assets)
        patcher.start(); self.addCleanup(patcher.stop)
        context.service().set_asset(label)
        return assets / label

    def test_favorites_survive_reopening_and_malformed_data(self):
        self.panel.query.setText('Character Picker')
        self.assertEqual(self.panel.selected_id(), 'picker')
        self.panel.favorite_button.click()
        favorites, recent = self.ui._read_preferences()
        self.assertEqual(favorites, {'picker'})
        self.panel.scope.setCurrentIndex(self.panel.scope.findData('favorites'))
        self.assertEqual(self.panel.tree.topLevelItemCount(), 1)
        self.panel.favorite_button.click()
        self.assertEqual(self.panel.tree.topLevelItemCount(), 0)
        self.assertFalse(self.panel.open_button.isEnabled())
        self.cmds.optionVar(stringValue=(self.ui.PREFERENCES, '{broken'))
        self.assertEqual(self.ui._read_preferences(), (set(), []))
        self.cmds.optionVar(stringValue=(self.ui.PREFERENCES, '{"favorites": [[], "picker", "picker", "missing"]}'))
        self.assertEqual(self.ui._read_preferences(), ({'picker'}, []))

    def test_launch_real_editor_and_record_recent_without_scene_changes(self):
        self.panel.query.setText('De Boor Ribbon')
        self.assertEqual(self.panel.selected_id(), 'ribbon')
        before = set(self.cmds.ls(long=True))
        from maya_tools.scripts.ui import deboor_tools_UI
        # Standalone has no Maya main-window pointer; keep the real editor and
        # real command, supplying only a valid Qt parent for this headless test.
        with patch.object(deboor_tools_UI, '_maya_main_window', return_value=self.panel):
            self.panel.open_button.click()
        self.assertIn('Launched:', self.panel.status.text())
        self.assertEqual(self.panel.recent[0], 'ribbon')
        self.assertEqual(set(self.cmds.ls(long=True)), before)
        self.panel.query.clear()
        self.panel.scope.setCurrentIndex(self.panel.scope.findData('recent'))
        self.assertEqual(self.panel.selected_id(), 'ribbon')
        deboor_tools_UI._window_instance.close()

    def test_cancelled_build_never_replaces_scene(self):
        cube = self.cmds.polyCube(name='FrameworkPreservedMesh')[0]
        self.panel.query.setText('CREATE RIG SELF MATH')
        with patch.object(self.cmds, 'confirmDialog', return_value='Cancel'), patch.object(registry, 'invoke') as invoke:
            self.panel.open_button.click()
            invoke.assert_not_called()
        self.assertTrue(self.cmds.objExists(cube))
        self.assertFalse(self.panel.recent)
        self.cmds.delete(cube)

    def test_narrow_layout_and_unfinished_tool(self):
        self.panel.resize(320, 740)
        self.panel.show()
        self.app.processEvents()
        for control in (self.panel.query, self.panel.scope, self.panel.open_button, self.panel.favorite_button):
            self.assertLessEqual(control.geometry().right(), self.panel.width())
            self.assertGreater(control.width(), 40)
        self.panel.query.setText('BUILD LEG')
        self.assertEqual(self.panel.selected_id(), 'build_leg')
        self.assertFalse(self.panel.open_button.isEnabled())
        self.assertIn('unfinished', self.panel.description.text())

    def test_context_survives_rename_and_never_retargets_a_recreated_name(self):
        from maya_tools.scripts.framework import context
        root, mesh, skin = self.character('FrameworkHero')
        self.cmds.select(mesh)
        active = context.service().capture_selection()
        self.assertEqual(active.root, root)
        self.assertEqual(active.skin, skin)
        renamed = self.cmds.rename(root, 'FrameworkRenamedHero')
        self.owned[0] = renamed
        self.assertTrue(context.service().snapshot().mesh.startswith('|FrameworkRenamedHero|'))
        self.cmds.delete(renamed)
        replacement = self.cmds.createNode('transform', name='FrameworkRenamedHero')
        self.owned.append(replacement)
        self.assertEqual(context.service().snapshot().root, '')
        self.assertEqual(context.service().snapshot().mesh, '')

    def test_multiple_characters_and_foreign_mesh_are_rejected_atomically(self):
        from maya_tools.scripts.framework import context
        first = self.character('FrameworkFirst')
        second = self.character('FrameworkSecond')
        service = context.service()
        service.set_root(first[0])
        previous = service.snapshot()
        self.cmds.select([first[1], second[1]])
        with self.assertRaisesRegex(ValueError, 'multiple characters'):
            service.capture_selection()
        with self.assertRaisesRegex(ValueError, 'active character'):
            service.set_mesh(second[1])
        self.assertEqual(service.snapshot(), previous)
        self.panel.scene_changed()
        self.assertEqual(service.snapshot().mesh, first[1])

    def test_preflight_blocks_missing_inputs_without_mutating_scene_or_loading_plugins(self):
        from dataclasses import replace
        from maya_tools.scripts.framework import execution
        before = (set(self.cmds.ls(long=True)), self.cmds.ls(sl=True), self.cmds.file(q=True, modified=True),
                  set(self.cmds.pluginInfo(query=True, listPlugins=True) or []))
        dispatch = unittest.mock.Mock()
        result = execution.run('skin_copy', dispatch=dispatch)
        self.assertEqual(result['status'], 'blocked')
        dispatch.assert_not_called()
        missing = replace(registry.BY_ID['rig_tools'], id='missing_plugin', requirements=('plugin:AutoRigMissingTestPlugin',))
        with patch.dict(registry.BY_ID, missing_plugin=missing):
            self.assertFalse(execution.preflight('missing_plugin').ready)
        after = (set(self.cmds.ls(long=True)), self.cmds.ls(sl=True), self.cmds.file(q=True, modified=True),
                 set(self.cmds.pluginInfo(query=True, listPlugins=True) or []))
        self.assertEqual(before, after)

    def test_validated_build_cancellation_preserves_scene_and_invalid_json_is_blocked(self):
        from maya_tools.scripts.framework import execution
        asset = self.asset_inputs()
        self.assertTrue(execution.preflight('create_rig').ready)
        before = set(self.cmds.ls(long=True))
        dispatch = unittest.mock.Mock()
        result = execution.run('create_rig', confirm=lambda tool: False, dispatch=dispatch)
        self.assertEqual(result['status'], 'cancelled')
        dispatch.assert_not_called()
        self.assertEqual(set(self.cmds.ls(long=True)), before)
        (asset / 'guides' / 'FrameworkAsset.guides').write_text('broken json')
        self.assertIn('Invalid saved guides', ' '.join(execution.preflight('create_rig').errors))

    def test_journal_keeps_distinct_outcomes_and_real_artifact_paths(self):
        from maya_tools.scripts.framework import execution
        path = Path(self.tmp.name) / 'result.json'
        path.write_text('{"verified":true}')
        self.assertEqual(execution.run('ribbon', dispatch=lambda: None)['status'], 'opened')
        self.assertEqual(execution.run('correctives_import', dispatch=lambda: None)['status'], 'returned')
        self.assertEqual(execution.run('correctives_import', dispatch=lambda: False)['status'], 'cancelled')
        def fail():
            raise RuntimeError('Test operation failed')
        failure = execution.run('correctives_import', dispatch=fail)
        self.assertEqual(failure['status'], 'failed')
        self.assertIn('Test operation failed', failure['traceback'])
        complete = execution.run('correctives_import', dispatch=lambda: path)
        self.assertEqual(complete['files'], [str(path)])
        self.assertEqual(complete['status'], 'completed')
        journal = execution.Journal(execution.journal().path)
        self.assertEqual(len(journal.rows), 5)
        self.assertTrue(all(row['duration_ms'] >= 0 and row['timestamp'] for row in journal.rows))

    def test_work_profiles_restore_scope_search_tab_and_saved_selection(self):
        from maya_tools.scripts.framework import state
        self.panel.profile_choice.setCurrentText('Rigging')
        self.assertEqual(self.panel.scope.currentData(), 'RIGGING')
        self.panel.query.setText('Guide')
        self.panel.tabs.setCurrentIndex(1)
        self.panel.save_layout()
        expected = self.panel.view()
        self.panel.profile_choice.setCurrentText('Deformers')
        self.assertEqual(self.panel.scope.currentData(), 'DEFORMERS')
        self.panel.profile_choice.setCurrentText('Rigging')
        self.assertEqual(self.panel.query.text(), 'Guide')
        self.assertEqual(self.panel.tabs.currentIndex(), 1)
        self.assertEqual(self.panel.selected_id(), expected['selected'])
        self.assertEqual(state.profile('Rigging')['scope'], 'RIGGING')

    def test_workflow_review_is_explicit_and_isolated_between_characters(self):
        from maya_tools.scripts.framework import context, state
        first = self.character('FrameworkWorkflowA')
        second = self.character('FrameworkWorkflowB')
        context.service().set_root(first[0])
        key = context.service().snapshot().key
        with patch.object(self.panel, 'launch_tool', return_value={'status': 'opened'}) as launch:
            self.panel.workflow.open_step()
            self.assertEqual(state.workflow(key)['model']['status'], 'in_progress')
            self.panel.workflow.next_step()
            self.assertEqual(launch.call_count, 1)
        state.set_step(key, 'model', 'reviewed', 'Reviewed the actual model report')
        with self.assertRaisesRegex(ValueError, 'Explain'):
            state.set_step(key, 'guides', 'skipped')
        context.service().set_root(second[0])
        self.assertEqual(state.workflow(context.service().snapshot().key), {})
        context.service().set_root(first[0])
        self.assertEqual(state.workflow(key)['model']['status'], 'reviewed')

    def test_real_blendshape_editor_follows_the_shared_mesh_and_unsubscribes_on_close(self):
        from maya_tools.scripts.framework import context, adapters
        first = self.character('FrameworkPoseA')
        second = self.character('FrameworkPoseB')
        context.service().set_root(first[0])
        window = adapters.pose_blendshapes()
        try:
            self.assertEqual(window.mesh.text(), first[1])
            context.service().set_root(second[0])
            self.assertEqual(window.mesh.text(), second[1])
            window.close()
            self.assertFalse(window._framework_binding.active)
        finally:
            window.close(); window.deleteLater()

    def test_nested_framework_action_is_blocked_while_outer_action_runs(self):
        from maya_tools.scripts.framework import execution
        results = []
        def nested():
            results.append(execution.run('ribbon', dispatch=lambda: None))
        outer = execution.run('ribbon', dispatch=nested)
        self.assertEqual(outer['status'], 'opened')
        self.assertEqual(results[0]['status'], 'blocked')

    def test_namespace_reparenting_and_stacked_skin_targets_are_unambiguous(self):
        from maya_tools.scripts.framework import context
        ns = self.cmds.namespace(add='FrameworkNamespace')
        self.addCleanup(lambda: self.cmds.namespace(removeNamespace=ns))
        root, mesh, skin = self.character(ns + ':Hero')
        holder = self.cmds.createNode('transform', name='FrameworkWorld')
        self.owned.append(holder)
        self.cmds.parent(root, holder)
        mesh = self.cmds.ls(ns + ':Hero_body', long=True)[0]
        joint = self.cmds.createNode('joint', name=ns + ':ExtraJoint', parent=ns + ':Hero')
        stacked = self.cmds.skinCluster(joint, mesh, toSelectedBones=True, multi=True)[0]
        self.owned.append(stacked)
        self.cmds.select(mesh)
        active = context.service().capture_selection()
        self.assertEqual(active.root, '|FrameworkWorld|' + ns + ':Hero')
        self.assertEqual(active.namespace, ns)
        self.assertEqual(active.skin, '')
        context.service().set_skin(stacked)
        self.assertEqual(context.service().snapshot().skin, stacked)
        self.cmds.rename(ns + ':Hero', ns + ':Renamed')
        context.service().refresh()
        self.assertTrue(context.service().snapshot().mesh.startswith('|FrameworkWorld|' + ns + ':Renamed|'))
        self.owned.append(ns + ':Renamed')

    def test_live_sculpt_rejects_context_change_before_notifying_editors(self):
        from maya_tools.scripts.framework import context
        from maya_tools.scripts.tools import pose_blendshapes
        first = self.character('FrameworkLiveA')
        second = self.character('FrameworkLiveB')
        context.service().set_root(first[0])
        before = context.service().snapshot()
        with patch.object(pose_blendshapes, 'edit_session', return_value={'active': True}):
            with self.assertRaisesRegex(ValueError, 'Finish the live sculpt'):
                context.service().set_root(second[0])
        self.assertEqual(context.service().snapshot(), before)

    def test_real_skin_export_uses_active_asset_instead_of_stale_build_cache(self):
        import json
        from maya_tools.scripts.framework import context, execution
        asset = self.asset_inputs()
        root, mesh, skin = self.character('FrameworkAsset')
        context.service().set_root(root)
        self.cmds.select(mesh)
        before = (set(self.cmds.ls(long=True)), self.cmds.ls(selection=True, long=True))
        result = execution.run('skin_export')
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(len(result['files']), 1)
        exported = Path(result['files'][0])
        self.assertEqual(exported.parent, asset / 'skin_clusters')
        self.assertTrue(json.loads(exported.read_text()))
        self.assertEqual(before, (set(self.cmds.ls(long=True)), self.cmds.ls(selection=True, long=True)))

    def test_activity_export_and_profile_reopen_preserve_the_saved_view(self):
        import json
        from maya_tools.scripts.framework import execution
        execution.run('ribbon', dispatch=lambda: None)
        destination = Path(self.tmp.name) / 'history.json'
        with patch.object(self.ui.QtWidgets.QFileDialog, 'getSaveFileName', return_value=(str(destination), '')):
            self.panel.activity.export()
        self.assertEqual(json.loads(destination.read_text())[-1]['status'], 'opened')
        self.panel.profile_choice.setCurrentText('Deformers')
        self.panel.scope.setCurrentIndex(self.panel.scope.findData('DEFORMERS:Blendshapes'))
        self.panel.tabs.setCurrentIndex(2)
        self.panel.save_layout()
        reopened = self.ui.ToolFramework()
        try:
            self.assertEqual(reopened.profile_choice.currentText(), 'Deformers')
            self.assertEqual(reopened.scope.currentData(), 'DEFORMERS:Blendshapes')
            self.assertEqual(reopened.tabs.currentIndex(), 2)
        finally:
            reopened.dispose(); reopened.close(); reopened.deleteLater()

    def test_preflight_checks_the_actual_newest_input_instead_of_ignoring_bad_files(self):
        import os
        from maya_tools.scripts.framework import execution
        asset = self.asset_inputs()
        unexpected = asset / 'build' / 'unexpected.txt'
        unexpected.write_text('This would be chosen by the legacy build loader.')
        newest = max(path.stat().st_mtime for path in (asset / 'build').iterdir()) + 5
        os.utime(unexpected, (newest, newest))
        self.assertIn('unsupported type', ' '.join(execution.preflight('create_rig').errors))

    def test_build_with_live_sculpt_is_blocked_before_the_save_prompt(self):
        from maya_tools.scripts.framework import execution
        from maya_tools.scripts.tools import pose_blendshapes
        self.asset_inputs()
        confirm = unittest.mock.Mock(return_value=True)
        dispatch = unittest.mock.Mock()
        with patch.object(pose_blendshapes, 'edit_session', return_value={'active': True}):
            row = execution.run('create_rig', confirm=confirm, dispatch=dispatch)
        self.assertEqual(row['status'], 'blocked')
        confirm.assert_not_called(); dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
