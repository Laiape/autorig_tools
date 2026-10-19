"""Explicit integration regression: rebuild Edward and test real skinned geometry.

Run via scripts/run_maya_test.py in a disposable mayapy process. All derived
build caches and native scene files live in a private temporary directory.
"""
import json
import bisect
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'maya_tools/scripts')]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya.api import OpenMayaAnim as oma
import numpy as np
from maya_tools.scripts.utils import create_rig
from maya_tools.scripts.framework import context
from fixtures import surface_reversals

MESHES = ('cabeza_high', 'cabeza_low', 'cuerpo_base')


def mesh_function(mesh):
    shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True)[0]
    return om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))


def points():
    return {mesh: np.array([[p.x, p.y, p.z] for p in mesh_function(mesh).getPoints(om.MSpace.kWorld)])
            for mesh in MESHES}


try:
    with tempfile.TemporaryDirectory(prefix='edward_auto_wide_') as folder:
        os.environ['AUTORIG_BUILD_CACHE_DIR'] = str(Path(folder) / 'cache')
        context.service().set_asset('Edward')
        cmds.optionVar(stringValue=('currentAssetRigName', 'Edward'))
        started = time.perf_counter()
        create_rig.AutoRig().build()
        build_seconds = time.perf_counter() - started
        cmds.evaluationManager(mode='off')
        from maya_tools.scripts.tools import pose_blendshapes as poses
        from maya_tools.scripts.tools.skin_manager_api import SkinManager
        saved = json.loads(Path(SkinManager().get_latest_version_path()).read_text())
        low_record = next(r for r in saved['cabeza_low_Shape'] if r['name'] == 'skinCluster41')
        skin = oma.MFnSkinCluster(om.MSelectionList().add('skinCluster41').getDependNode(0))
        component = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
        vertex_ids = (2942, 3080)
        om.MFnSingleIndexedComponent(component).addElements(vertex_ids)
        shape = cmds.listRelatives('cabeza_low', shapes=True, noIntermediate=True, fullPath=True)[0]
        weights, influence_count = skin.getWeights(om.MSelectionList().add(shape).getDagPath(0), component)
        for column, influence in enumerate(skin.influenceObjects()):
            name = influence.partialPathName()
            values = low_record['sparse_weights'].get(name, {'ix': [], 'v': []})
            value_key = next(k for k in values if k != 'ix')
            for row, vertex in enumerate(vertex_ids):
                index = bisect.bisect_left(values['ix'], vertex)
                expected = values[value_key][index] if index < len(values['ix']) and values['ix'][index] == vertex else 0.
                assert abs(weights[row*influence_count+column] - expected) < 1e-12, (vertex, name, 'lossless skin import')
        captured = saved.get('__scene_deformers__', {}).get('pose_targets', [])
        for target in captured:
            bs, index = target['blendShape'], target['targetIndex']
            assert cmds.objExists(bs), ('Missing saved corrective', bs)
            assert poses.pose_record(bs, index), (bs, index, 'Missing saved driver')
            assert dict(poses.targets(bs))[index] == target['targetName']
            assert poses.geometry_index(bs, target['mesh']) == 0
        for side in ('L', 'R'):
            for attr in ('autoNarrow', 'autoWide'):
                assert cmds.getAttr(side + '_lipCorner_CTL.' + attr) == 1
        wrinkle_controls = cmds.ls('*.wrinkleValue', objectsOnly=True)
        assert wrinkle_controls
        for control in wrinkle_controls:
            assert cmds.getAttr(control + '.wrinkleValue') == 1, control
            assert cmds.attributeQuery('wrinkleValue', node=control, listDefault=True) == [1.]
        records = []
        for corrective, sign in (('autoWide', -1), ('autoNarrow', 1)):
            for angle in (0, 20, 30):
                cmds.setAttr('C_jaw_CTL.rx', angle)
                for amount in (0, .5, 1):
                    for side in ('L', 'R'):
                        scale = cmds.getAttr(side + '_lipSignedX_MUL.input[1]')
                        cmds.setAttr(side + '_lipCorner_CTL.tx', sign * .25 * amount / scale)
                        cmds.setAttr(side + '_lipCorner_CTL.' + corrective, 0)
                    before = points()
                    before_surface = {mesh: surface_reversals.capture(mesh_function(mesh)) for mesh in MESHES}
                    for side in ('L', 'R'):
                        cmds.setAttr(side + '_lipCorner_CTL.' + corrective, 1)
                    after = points()
                    after_surface = {mesh: surface_reversals.capture(mesh_function(mesh)) for mesh in MESHES}
                    case = {'corrective': corrective, 'jaw': angle,
                            'signed_x_fraction': sign * .25 * amount, 'meshes': {}}
                    for mesh in MESHES:
                        a, b = before[mesh], after[mesh]
                        assert np.isfinite(b).all(), (corrective, angle, amount, mesh)
                        delta = b - a
                        moved = np.linalg.norm(delta, axis=1) > 1e-7
                        surface = surface_reversals.compare(before_surface[mesh], after_surface[mesh])
                        case['meshes'][mesh] = dict(vertices=len(b), moved_vertices=int(moved.sum()),
                                                   maximum_forward=float(delta[:, 2].max()),
                                                   minimum_forward=float(delta[:, 2].min()),
                                                   **surface)
                        assert surface['new_triangle_reversals'] == 0, (corrective, angle, amount, mesh, surface)
                        assert surface['new_polygon_reversals'] == 0, (corrective, angle, amount, mesh, surface)
                        if amount == 0 or mesh == 'cuerpo_base':
                            assert not moved.any(), (corrective, angle, amount, mesh)
                    if amount:
                        assert case['meshes']['cabeza_high']['moved_vertices'] > 0
                    records.append(case)
        cmds.setAttr('C_jaw_CTL.stickyLips', 1)
        for i in range(25):
            prefix = 'R_' if i < 12 else 'C_' if i == 12 else 'L_'
            index = i if i < 12 else 0 if i == 12 else 24-i
            a = cmds.xform(prefix + 'upperLip%02d_JNT' % index, q=True, ws=True, t=True)
            b = cmds.xform(prefix + 'lowerLip%02d_JNT' % index, q=True, ws=True, t=True)
            assert np.allclose(a, b, atol=1e-5, rtol=0)
        cmds.setAttr('C_jaw_CTL.stickyLips', 0)
        expected = points()
        # Retain the source format when batch Maya preserves editor-only nodes
        # as unknown; changing formats is forbidden for such native scenes.
        scene_type = cmds.file(query=True, type=True)[0]
        extension = '.mb' if scene_type == 'mayaBinary' else '.ma'
        path = Path(folder) / ('Edward_auto_wide' + extension)
        cmds.file(rename=str(path))
        cmds.file(save=True, type=scene_type, force=True)
        cmds.file(new=True, force=True)
        cmds.file(str(path), open=True, force=True)
        reopened = points()
        reopen_error = max(float(np.abs(reopened[m] - expected[m]).max()) for m in MESHES)
        assert reopen_error < 1e-5, reopen_error
        print('PASS Edward signed Narrow/Wide: real meshes, defaults, unchanged neutral/body, no new triangle reversals, sticky and reopen')
        print(json.dumps(dict(build_seconds=build_seconds, saved_correctives=len(captured), reopen_error=reopen_error, poses=records)), flush=True)
finally:
    maya.standalone.uninitialize()
