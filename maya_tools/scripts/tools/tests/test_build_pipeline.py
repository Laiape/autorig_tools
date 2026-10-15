"""Native Maya: safe audits, complete build guard, failure cleanup and SKC reuse."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'maya_tools/scripts')]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import rig_validation, skin_manager_api, bifrost_wrinkles, rig_performance
from maya_tools.scripts.utils import create_rig, basic_structure, build_timing, data_manager, model_cache
from maya_tools.scripts.ui import rig_progress


class Progress:
    def __init__(self, *args, **kwargs):
        self.finished = self.failed = False
        Progress.last = self

    def show(self): pass
    def _set_pct(self, *args): pass
    def finish(self, elapsed): self.finished = True
    def fail(self, error): self.failed = True


class BuildTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.optionVar(stringValue=('currentAssetRigName', 'BuildCharacter'))
        cmds.evaluationManager(mode='serial')
        cmds.undoInfo(state=True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_automatic_audit_never_queries_native_gpu_partitions(self):
        mesh = cmds.polyCube()[0]
        with mock.patch.object(cmds, 'deformerEvaluator', side_effect=AssertionError('Unsafe GPU query'), create=True), \
             mock.patch.object(cmds, 'about', return_value=False):
            report = rig_validation.audit_deformers([mesh])
        self.assertEqual(report[0]['gpu']['status'], 'not_queried')

    def run_build(self, fail=False, validate=True):
        rig = create_rig.AutoRig()
        observed = []
        def stage():
            observed.append((cmds.evaluationManager(q=True, mode=True)[0], cmds.undoInfo(q=True, state=True)))
        def structure():
            cmds.createNode('transform', name='BuildCharacter')
            with mock.patch.object(cmds, 'refresh') as refresh:
                basic_structure._suspend_eval()()
                refresh.assert_not_called()
        def weights():
            stage()
            if fail:
                raise RuntimeError('Injected skin import failure')
            return mock.Mock(import_wrinkles=stage)
        rig.basic_structure = structure
        rig.make_rig = lambda **kwargs: (stage(), kwargs['on_step']('Building test module', 1, 1))
        for name in ('label_joints', 'hide_connections', 'inherit_transforms',
                     'localize_correctives', 'import_corrective_blendshapes', 'hide_all_utility_nodes'):
            setattr(rig, name, stage)
        rig.import_weights = weights
        with mock.patch.object(create_rig, 'reload', side_effect=lambda module: module), \
             mock.patch.object(rig_progress, 'RigProgressDialog', Progress), \
             mock.patch.object(create_rig.rig_manager, 'build_rig_from_data', return_value={}), \
             mock.patch.object(create_rig.rig_manager, 'asset_path', return_value=self.temp.name), \
             mock.patch.object(data_manager.DataExportBiped, 'new_build'):
            if fail:
                with self.assertRaisesRegex(RuntimeError, 'Injected skin import failure'):
                    rig.build(validate=validate)
            else:
                rig.build(validate=True) if validate else rig.build()
        self.assertTrue(observed)
        self.assertTrue(all(state == ('off', False) for state in observed))
        self.assertEqual(cmds.evaluationManager(q=True, mode=True)[0], 'serial')
        self.assertTrue(cmds.undoInfo(q=True, state=True))
        self.assertIsNone(build_timing.active())
        receipts = list(Path(self.temp.name).glob('*.buildtiming.json'))
        report = json.loads(receipts[-1].read_text())
        self.assertEqual(report['status'], 'failed' if fail else 'complete')
        self.assertEqual(Progress.last.finished, not fail)
        self.assertEqual(Progress.last.failed, fail)

    def test_guard_covers_skin_correctives_wrinkles_and_validation(self):
        self.run_build()

    def test_normal_build_does_not_run_the_optional_health_audit(self):
        with mock.patch.object(rig_validation, 'write_build_health') as audit:
            self.run_build(validate=False)
            audit.assert_not_called()

    def test_failure_restores_maya_and_does_not_report_complete(self):
        self.run_build(fail=True)

    def test_recursive_build_is_rejected(self):
        with build_timing.BuildTiming('ExistingBuild', self.temp.name):
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                with build_timing.BuildTiming('NestedBuild', self.temp.name):
                    self.fail('Recursive build was accepted')

    def test_all_rig_families_load_their_native_math_dependencies(self):
        with mock.patch.object(create_rig.rig_manager, 'build_rig'):
            create_rig.AutoRig().make_rig()
        for kind, attribute in (('inverseMatrix', 'inputMatrix'),
                                ('quatToEuler', 'inputQuat'), ('floatConstant', 'inFloat')):
            node = cmds.createNode(kind)
            self.assertNotEqual(cmds.nodeType(node), 'unknown')
            self.assertTrue(cmds.attributeQuery(attribute, node=node, exists=True))

    def test_model_cache_preserves_source_geometry_and_invalidates_content(self):
        root = Path(self.temp.name)
        source = root/'Model.ma'
        mesh = cmds.polyCube(name='Model')[0]
        cmds.setAttr(mesh+'.translateX', 3)
        cmds.file(rename=str(source))
        cmds.file(save=True, type='mayaAscii')
        original_bytes = source.read_bytes()
        with mock.patch.dict(os.environ, {'AUTORIG_MODEL_CACHE_DIR': str(root/'cache')}):
            first = model_cache.open_model(source)
            self.assertFalse(first['cache_hit'])
            points = rig_validation.mesh_data('Model')
            second = model_cache.open_model(source)
            self.assertTrue(second['cache_hit'])
            self.assertEqual(rig_validation.mesh_data('Model'), points)
            self.assertEqual(source.read_bytes(), original_bytes)
            # A damaged derived cache is rejected before attempting to open it.
            Path(second['binary']).write_bytes(b'damaged')
            self.assertFalse(model_cache.open_model(source)['cache_hit'])
            self.assertEqual(rig_validation.mesh_data('Model'), points)
            cmds.setAttr('Model.translateX', 7)
            cmds.file(rename=str(source))
            cmds.file(save=True, type='mayaAscii')
            changed = model_cache.open_model(source)
            self.assertFalse(changed['cache_hit'])
            self.assertNotEqual(changed['source_sha256'], first['source_sha256'])
            self.assertEqual(cmds.getAttr('Model.translateX'), 7)

    def test_sticky_lips_accept_unequal_upper_and_lower_guide_counts(self):
        from maya_tools.scripts.biped.autorig.jaw_module_nurbs import JawModule
        for counts in ((3, 5), (5, 3), (3, 3)):
            cmds.file(new=True, force=True)
            module = JawModule.__new__(JawModule)
            module.jaw_ctl = cmds.createNode('transform', name='jaw_CTL')
            cmds.addAttr(module.jaw_ctl, longName='mouthHeight', attributeType='double', defaultValue=.5)
            reverse = cmds.createNode('reverse')
            cmds.connectAttr(module.jaw_ctl+'.mouthHeight', reverse+'.inputX')
            frames = {}
            for part, count, y in (('upper', counts[0], 2), ('lower', counts[1], -2)):
                frames[part] = []
                for i in range(count):
                    node = cmds.createNode('transform')
                    cmds.setAttr(node+'.translate', i*10./(count-1), y, 0, type='double3')
                    frames[part].append(node+'.worldMatrix[0]')
            meeting = module._sticky_meeting_frames(frames, reverse)
            for part, count in zip(('upper', 'lower'), counts):
                self.assertEqual(len(meeting[part]), count)
                for i, plug in enumerate(meeting[part]):
                    matrix = cmds.getAttr(plug)
                    self.assertAlmostEqual(matrix[12], i*10./(count-1), places=7)
                    self.assertAlmostEqual(matrix[13], 0, places=7)
            if counts[0] == counts[1]:
                self.assertIs(meeting['upper'], meeting['lower'])

    def test_nested_model_root_is_not_parented_below_its_own_geometry(self):
        outer = cmds.createNode('transform', name='sourceRoot')
        main = cmds.createNode('transform', name='Giraffe', parent=outer)
        geo = cmds.createNode('transform', name='geo_GRP', parent=main)
        final = cmds.createNode('transform', name='FINAL', parent=geo)
        mesh = cmds.polyCube(name='ModelMesh')[0]
        cmds.parent(mesh, main)
        original = rig_validation.mesh_data(mesh)
        parent = cmds.parent
        with mock.patch.object(cmds, 'parent', wraps=parent) as calls:
            basic_structure._parent_model_under_final(main, geo, final, 'giraffe')
        self.assertFalse(any(outer in call.args for call in calls.call_args_list))
        self.assertEqual(rig_validation.mesh_data(mesh), original)

    def test_skin_payload_is_reused_and_invalidated_when_file_changes(self):
        path = Path(self.temp.name) / 'weights.skc'
        path.write_text(json.dumps({'__wrinkles__': [], '__scene_deformers__': {'detail_modes': []}}))
        manager = skin_manager_api.SkinManager.__new__(skin_manager_api.SkinManager)
        manager.get_latest_version_path = lambda: str(path)
        load = json.load
        with mock.patch.object(skin_manager_api.json, 'load', wraps=load) as reads, \
             mock.patch.object(bifrost_wrinkles, 'import_setups', return_value=[]) as restore, \
             mock.patch.object(rig_performance, 'restore_detail_modes'):
            manager.import_skins(in_path=str(path), import_wrinkles=False)
            self.assertEqual(reads.call_count, 1)
            manager.import_wrinkles()
            self.assertEqual(reads.call_count, 1)
            path.write_text(json.dumps({'__wrinkles__': [{'changed': True}]}))
            manager.import_wrinkles()
            self.assertEqual(reads.call_count, 2)
            self.assertEqual(restore.call_args.args[0], [{'changed': True}])


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BuildTests))
assert result.wasSuccessful(), 'Build pipeline regression failed'
print('PASS build lifecycle, crash-safe audits, SKC reuse and failure cleanup')
