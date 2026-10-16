"""Regional editing, empty support, detail restoration, undo and SKC portability."""
import os
from pathlib import Path
import sys
import tempfile
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from maya_tools.scripts.tools import bifrost_wrinkles as bw, wrinkle_presets as wp, rig_performance as rp
from maya_tools.scripts.tools import skin_manager_api as sm


def points(mesh):
    shape = bw._mesh_fn(mesh)[0]
    cmds.dgeval(shape + '.outMesh')
    return np.asarray([[p.x, p.y, p.z] for p in bw._mesh_fn(shape)[2].getPoints()])


try:
    root = cmds.createNode('transform', name='Character')
    high = cmds.polyPlane(w=8, h=8, sx=12, sy=12, ch=False)[0]
    low = cmds.polyCube()[0]
    control = cmds.createNode('transform', name='Fold_CTL', parent=root)
    cmds.parent(high, low, root)
    first_joint = cmds.createNode('joint', name='Base_JNT', parent=root)
    second_joint = cmds.createNode('joint', name='Local_JNT', parent=root)
    cmds.skinCluster([first_joint], high, name='BaseSkin', toSelectedBones=True)
    cmds.skinCluster([second_joint], high, name='LocalSkin', toSelectedBones=True, multi=True)
    rest = points(high)
    patterns = {r: [0.] * len(rest) for r in bw.REGIONS}
    patterns['Forehead'][0] = 1
    setup = bw.build(high, 'Local', patterns, compact=True, in_place=True)
    rp.create_detail_modes(root, [high], [low], [setup['settings']])
    rp.install_compute_bypass(root)
    cmds.setAttr(setup['settings'] + '.ManualActivation', 1)
    expected = points(high)
    assert abs(expected[0, 1] - .3) < 2e-5
    rp.set_detail_mode(root, 0)
    wp.set_patterns(setup['settings'], {'Forehead': [1.] * len(rest)})
    assert cmds.getAttr(setup['settings'] + '.Envelope') == 0
    rp.set_detail_mode(root, 1)
    assert np.allclose(points(high)[:, 1], .3, atol=2e-5)
    wp.assign_controls(setup['settings'], 'Forehead', [control])
    assert np.allclose(points(high)[:, 1], .3, atol=2e-5)
    assert np.allclose(wp._rest_geometry(high)['points'], rest, atol=2e-5)
    wp.set_patterns(setup['settings'], {'Forehead': [0.] * len(rest)})
    assert np.allclose(points(high), rest, atol=2e-5)
    cmds.undo()
    assert np.allclose(points(high)[:, 1], .3, atol=2e-5)
    with tempfile.TemporaryDirectory() as folder:
        preset = str(Path(folder) / 'local.wrinkles.json')
        wp.export_preset(setup['settings'], preset)
        wp.apply_preset(preset, high, 'Local', replace_existing=True)
        expected = points(high)
        assert np.allclose(expected[:, 1], .3, atol=2e-5)
        manager = sm.SkinManager.__new__(sm.SkinManager)
        manager.k_skin_attrs = []; manager.tolerance = 1e-5
        skc = str(Path(folder) / 'local.skc')
        cmds.select(clear=True)
        manager.export_skins(skc)
        import json
        exported = json.loads(Path(skc).read_text())
        assert len(exported[bw._mesh_fn(high)[0].rsplit('|', 1)[-1]]) == 2, 'In-place detail hid the stacked skins from export.'
        bw.remove_setup(setup['settings'])
        manager.import_skins(skc)
        assert np.allclose(points(high), expected, atol=2e-5)
        assert not cmds.objExists('Local_Face')
        assert len(cmds.ls(type='bifrostGraphShape')) == 1
    print('PASS regional workflow: vertex zero, expansion, empty support, Undo, local controls, neutral export, preset and SKC replacement', flush=True)
finally:
    maya.standalone.uninitialize()
