"""Native scene reopen, ownership, construction isolation and runtime restoration."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'maya_tools/scripts')]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.utils import scene_evaluation as policy, build_timing
cmds.loadPlugin('deformerEvaluator', quiet=True)


class SceneEvaluationTests(unittest.TestCase):
    def setUp(self):
        policy.remove_callbacks()
        cmds.file(new=True, force=True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(policy.remove_callbacks)
        self.available = set(cmds.evaluator(query=True) or [])

    def expensive_flags(self):
        cmds.evaluationManager(mode='serial')
        for name in ('deformer', 'cache'):
            if name in self.available:
                cmds.evaluator(name=name, enable=True)

    def assert_baseline(self):
        actual = policy.capture()
        self.assertEqual(actual['mode'], 'parallel')
        self.assertFalse(any(actual['evaluators'].values()))

    def test_profile_changes_no_geometry_animation_or_artistic_settings(self):
        mesh = cmds.polyCube()[0]
        cmds.setKeyframe(mesh, attribute='translateX', time=1, value=0)
        cmds.setKeyframe(mesh, attribute='translateX', time=10, value=3)
        cmds.currentTime(7)
        before = cmds.xform(mesh, query=True, worldSpace=True, translation=True)
        cmds.select(mesh)
        policy.register(mesh)
        count = len(cmds.ls())
        policy.register(mesh)
        policy.apply()
        self.assert_baseline()
        self.assertEqual(len(cmds.ls()), count)
        self.assertEqual(cmds.currentTime(query=True), 7)
        self.assertEqual(cmds.ls(selection=True), [mesh])
        self.assertEqual(cmds.xform(mesh, query=True, worldSpace=True, translation=True), before)
        self.assertEqual(cmds.keyframe(mesh, query=True, keyframeCount=True), 2)
        self.assertFalse(cmds.ls(type='script'))

    def test_native_reopen_applies_to_different_names_and_namespaces(self):
        results = []
        for name in ('FirstCharacter', 'OtherCharacter:Root'):
            cmds.file(new=True, force=True)
            if ':' in name:
                cmds.namespace(add='OtherCharacter')
            root = cmds.createNode('transform', name=name)
            policy.register(root)
            path = str(Path(self.temp.name) / (name.replace(':', '_') + '.mb'))
            cmds.file(rename=path)
            cmds.file(save=True, type='mayaBinary')
            policy.install_callbacks(apply_current=False)
            self.expensive_flags()
            started = time.perf_counter()
            cmds.file(path, open=True, force=True)
            self.assert_baseline()
            self.assertFalse(cmds.file(query=True, modified=True))
            results.append({'character': name, 'native_open_seconds': time.perf_counter()-started})
        print('REOPEN ' + json.dumps(results))

    def test_unmarked_scene_and_unknown_contract_do_not_change_runtime(self):
        self.expensive_flags()
        initial = policy.capture()
        self.assertFalse(policy.apply_for_scene()['applied'])
        root = cmds.createNode('transform', name='ExternalAsset')
        cmds.addAttr(root, longName=policy.ATTRIBUTE, dataType='string')
        cmds.setAttr(root + '.' + policy.ATTRIBUTE, 'another_tool', type='string')
        self.assertFalse(policy.apply_for_scene()['applied'])
        self.assertEqual(policy.capture(), initial)
        with self.assertRaises(ValueError):
            policy.register(root)

    def test_open_callback_stays_out_of_active_construction(self):
        root = cmds.createNode('transform', name='Construction')
        policy.register(root)
        cmds.evaluationManager(mode='off')
        with build_timing.BuildTiming('Construction', self.temp.name):
            self.assertEqual(policy.apply_for_scene()['reason'], 'construction_in_progress')
            self.assertEqual(cmds.evaluationManager(query=True, mode=True), ['off'])

    def test_build_suspend_and_failure_restore_original_flags(self):
        self.expensive_flags()
        initial = policy.capture()
        previous = policy.suspend_for_build()
        self.assertEqual(cmds.evaluationManager(query=True, mode=True), ['off'])
        self.assertFalse(any(policy.capture()['evaluators'].values()))
        policy.restore(previous)
        self.assertEqual(policy.capture(), initial)

    def test_callback_install_is_idempotent_across_reload(self):
        policy.install_callbacks(apply_current=False)
        first = list(policy._CALLBACKS)
        importlib.reload(policy)
        policy.install_callbacks(apply_current=False)
        self.assertEqual(policy._CALLBACKS, first)
        policy.remove_callbacks()
        self.assertEqual(policy._CALLBACKS, [])

    def test_failed_apply_restores_caller_flags(self):
        self.expensive_flags()
        initial = policy.capture()
        original = cmds.evaluationManager
        def reject_parallel(*args, **kwargs):
            if kwargs.get('mode') == 'parallel' and not kwargs.get('query'):
                raise RuntimeError('Injected policy failure')
            return original(*args, **kwargs)
        with mock.patch.object(cmds, 'evaluationManager', side_effect=reject_parallel):
            with self.assertRaisesRegex(RuntimeError, 'Injected policy failure'):
                policy.apply()
        self.assertEqual(policy.capture(), initial)

    def test_settings_only_cost_is_reported_without_geometry_or_refresh(self):
        root = cmds.createNode('transform', name='CostFixture')
        start = time.perf_counter()
        with mock.patch.object(cmds, 'refresh', side_effect=AssertionError('Unexpected draw')), \
             mock.patch.object(cmds, 'deformerEvaluator', side_effect=AssertionError('Unexpected GPU partition query'), create=True):
            policy.register(root)
            report = policy.apply()
        print('PROFILE_OVERHEAD ' + json.dumps(dict(report, registration_and_apply_seconds=time.perf_counter()-start)))
        self.assert_baseline()


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SceneEvaluationTests))
assert result.wasSuccessful(), 'Scene evaluation regression failed'
