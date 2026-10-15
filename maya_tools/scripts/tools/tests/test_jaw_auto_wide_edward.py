"""Explicit integration regression: rebuild Edward and test real skinned geometry.

Run via scripts/run_maya_test.py in a disposable mayapy process. All derived
build caches and native scene files live in a private temporary directory.
"""
import json
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
import numpy as np
from maya_tools.scripts.utils import create_rig
from maya_tools.scripts.framework import context

MESHES = ('cabeza_high', 'cabeza_low', 'cuerpo_base')


def mesh_function(mesh):
    shape = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True)[0]
    return om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))


def points():
    return {mesh: np.array([[p.x, p.y, p.z] for p in mesh_function(mesh).getPoints(om.MSpace.kWorld)])
            for mesh in MESHES}


def normals(p, triangles):
    return np.cross(p[triangles[:, 1]] - p[triangles[:, 0]],
                    p[triangles[:, 2]] - p[triangles[:, 0]])


try:
    with tempfile.TemporaryDirectory(prefix='edward_auto_wide_') as folder:
        os.environ['AUTORIG_BUILD_CACHE_DIR'] = str(Path(folder) / 'cache')
        context.service().set_asset('Edward')
        cmds.optionVar(stringValue=('currentAssetRigName', 'Edward'))
        started = time.perf_counter()
        create_rig.AutoRig().build()
        build_seconds = time.perf_counter() - started
        cmds.evaluationManager(mode='off')
        triangles = {mesh: np.asarray(mesh_function(mesh).getTriangles()[1], dtype=int).reshape(-1, 3)
                     for mesh in MESHES}
        records = []
        for angle in (0, 20, 30):
            cmds.setAttr('C_jaw_CTL.rx', angle)
            for amount in (0, .5, 1):
                for side in ('L', 'R'):
                    cmds.setAttr(side + '_lipCorner_CTL.autoNarrow', amount)
                for side in ('L', 'R'):
                    cmds.setAttr(side + '_lipCorner_CTL.autoWide', 0)
                before = points()
                for side in ('L', 'R'):
                    cmds.setAttr(side + '_lipCorner_CTL.autoWide', 1)
                after = points()
                case = {'jaw': angle, 'autoNarrow': amount, 'meshes': {}}
                for mesh in MESHES:
                    a, b = before[mesh], after[mesh]
                    assert np.isfinite(b).all(), (angle, amount, mesh)
                    delta = b - a
                    moved = np.linalg.norm(delta, axis=1) > 1e-7
                    n0, n1 = normals(a, triangles[mesh]), normals(b, triangles[mesh])
                    affected = moved[triangles[mesh]].any(axis=1)
                    valid = np.linalg.norm(n0, axis=1) > 1e-8
                    flips = int(np.count_nonzero(affected & valid & (np.sum(n0*n1, axis=1) < 0)))
                    case['meshes'][mesh] = dict(vertices=len(b), moved_vertices=int(moved.sum()),
                                               maximum_forward=float(delta[:, 2].max()),
                                               minimum_forward=float(delta[:, 2].min()),
                                               new_triangle_reversals=flips)
                    assert flips == 0, (angle, amount, mesh, flips)
                    if amount == 0 or mesh == 'cuerpo_base':
                        assert not moved.any(), (angle, amount, mesh)
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
        path = Path(folder) / 'Edward_auto_wide.mb'
        cmds.file(rename=str(path))
        cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(new=True, force=True)
        cmds.file(str(path), open=True, force=True)
        reopened = points()
        reopen_error = max(float(np.abs(reopened[m] - expected[m]).max()) for m in MESHES)
        assert reopen_error < 1e-5, reopen_error
        print('PASS Edward Auto Wide: real meshes, unchanged neutral/body, no new triangle reversals, sticky and reopen')
        print(json.dumps(dict(build_seconds=build_seconds, reopen_error=reopen_error, poses=records)), flush=True)
finally:
    maya.standalone.uninitialize()
