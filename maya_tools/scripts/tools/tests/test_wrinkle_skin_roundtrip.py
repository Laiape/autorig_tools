"""Run with mayapy: .skc wrinkle round trip and local controller isolation."""
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import maya.api.OpenMaya as om
import numpy as np
from maya_tools.scripts.tools import bifrost_wrinkles as bw, skin_manager_api as sm


def positions(mesh):
    shape, path, fn = bw._mesh_fn(mesh)
    cmds.dgeval(shape + '.outMesh')
    return np.array([[p.x, p.y, p.z] for p in fn.getPoints()])


try:
    cmds.file(new=True, force=True)
    mesh = cmds.polyPlane(w=8, h=8, sx=8, sy=8, ch=False)[0]
    rest = positions(mesh)
    controls = [cmds.createNode('transform', name=n) for n in ('L_test_CTL', 'R_test_CTL')]
    patterns = {r: [1. if r == 'Forehead' else 0. for _ in rest] for r in bw.REGIONS}
    fields = [{'controller': n, 'masks': {'Forehead': [float((p[0] < 0) == (i == 0)) for p in rest]}}
              for i, n in enumerate(controls)]
    setup = bw.build(mesh, 'TestWrinkles', patterns, control_fields=fields, hide_source=True)
    cmds.setAttr(setup['settings'] + '.ManualActivation', 1)
    baseline = positions(setup['output'])
    cmds.setAttr(controls[0] + '.wrinkleDepth', 2)
    cmds.setAttr(controls[0] + '.wrinkleValue', .5)
    assert np.allclose(positions(setup['output']), baseline, atol=2e-5)
    cmds.setAttr(controls[0] + '.wrinkleValue', 0)
    altered = positions(setup['output'])
    assert np.allclose(altered[rest[:, 0] < 0], rest[rest[:, 0] < 0], atol=2e-5)
    assert np.allclose(altered[rest[:, 0] >= 0], baseline[rest[:, 0] >= 0], atol=2e-5)
    cmds.setAttr(controls[0] + '.wrinkleDepth', 1)
    cmds.setAttr(controls[0] + '.wrinkleValue', 1)
    cmds.setAttr(setup['settings'] + '.ManualActivation', 0)
    compressed = rest.copy(); compressed[:, [0, 2]] *= .9
    bw._mesh_fn(mesh)[2].setPoints(om.MPointArray([om.MPoint(*p) for p in compressed]))
    expected = positions(setup['output'])
    manager = sm.SkinManager.__new__(sm.SkinManager)
    manager.k_skin_attrs = []; manager.tolerance = 1e-5
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / 'test.skc')
        cmds.select(clear=True)
        assert manager.export_skins(path) == path
        data = json.loads(Path(path).read_text())
        assert len(data[manager.WRINKLES_KEY]) == 1
        bw.remove_setup(setup['settings'])
        for control in controls:
            cmds.deleteAttr(control + '.wrinkleDepth'); cmds.deleteAttr(control + '.wrinkleValue')
        manager.import_skins(path)
        assert np.allclose(positions('TestWrinkles_Face'), expected, atol=3e-5)
        manager.import_skins(path)
        assert len(cmds.ls(type='bifrostGraphShape')) == 1
        # Replacement uses saved rest arrays even while the source is compressed.
        manager.import_wrinkles(path, replace_existing=True)
        assert np.allclose(positions('TestWrinkles_Face'), expected, atol=3e-5)
        # A changed topology must fail before removing the working graph.
        record = data[manager.WRINKLES_KEY][0]; record['topology'] = 'wrong'
        try:
            bw.import_setups([record], replace_existing=True)
            raise AssertionError('Expected topology rejection')
        except ValueError:
            assert cmds.objExists('TestWrinklesGraphShape')
        scene = str(Path(folder) / 'result.mb')
        cmds.file(rename=scene); cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(new=True, force=True); cmds.file(scene, open=True, force=True)
        assert np.allclose(positions('TestWrinkles_Face'), expected, atol=3e-5)
        cmds.setAttr('L_test_CTL.wrinkleValue', 0)
        disabled = positions('TestWrinkles_Face')
        assert np.allclose(disabled[rest[:, 0] < 0], compressed[rest[:, 0] < 0], atol=3e-5)
    print('PASS wrinkle .skc: local depth/value, side isolation, posed export, automatic import, idempotence, replacement, topology guard, native reopen', flush=True)
finally:
    maya.standalone.uninitialize()
