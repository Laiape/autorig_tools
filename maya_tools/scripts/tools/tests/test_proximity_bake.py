"""Run with mayapy: multi-driver wrap, bake SKC roundtrip, and static-ROM rollback."""
import os
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import numpy as np
import json
import tempfile
from tools import proximity_wrap, proximity_bake
from tools.skin_manager_api import SkinManager

try:
    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True)
    j1 = cmds.joint(name='bake_root')
    j2 = cmds.joint(name='bake_tip', position=(0, 4, 0))
    body = cmds.polyCylinder(name='body', height=8, radius=2, subdivisionsAxis=12,
                             subdivisionsHeight=8)[0]
    skin = cmds.skinCluster([j1, j2], body, toSelectedBones=True)[0]
    belt = cmds.polyCylinder(name='belt', height=1, radius=2.1, subdivisionsAxis=12,
                             subdivisionsHeight=2)[0]
    second = cmds.polyCylinder(name='body2', height=8, radius=2.2, subdivisionsAxis=12,
                               subdivisionsHeight=8)[0]
    cmds.skinCluster([j1, j2], second, toSelectedBones=True)
    cmds.skinCluster([j1, j2], belt, toSelectedBones=True)
    cmds.select(belt)
    wraps = proximity_wrap.apply_to_selected([body, second])
    assert len(cmds.proximityWrap(wraps[0], query=True, driverIndices=True)) == 2
    assert [cmds.nodeType(n) for n, _ in proximity_wrap.direct_deformers(proximity_wrap.mesh_shape(belt))] == ['proximityWrap']
    for attr, value in proximity_wrap.SETTINGS.items():
        assert cmds.getAttr(wraps[0] + '.' + attr) == value
    for frame, angle in [(0,0), (1,20), (2,-20), (3,35), (4,-35)]:
        cmds.setKeyframe(j2, attribute='rotateZ', time=frame, value=angle)
    cmds.currentTime(0)
    original = proximity_bake.points(belt)
    cmds.select(wraps)
    with tempfile.TemporaryDirectory() as folder:
        output = os.path.join(folder, 'asset_v001.skc')
        result = proximity_bake.bake_selected(0,4,1,0,2,output)
        assert len(result['records']) == 1
        record = result['records'][0]
        assert cmds.objExists(wraps[0]), 'source wrap changed'
        assert np.allclose(original, proximity_bake.points(belt))
        assert cmds.currentTime(query=True) == 0
        with open(output) as stream:
            data = json.load(stream)
        assert wraps[0] not in [node['name'] for node in data[SkinManager.SCENE_DEFORMERS_KEY]['nodes']]
        assert record['skin'] == data['|belt'][0]['name']
        assert not any('_BAKED' in name for name in data if name != SkinManager.SCENE_DEFORMERS_KEY)
        print('PASS bake + multi-driver wrap + full-scene SKC, max error:', record['worst_max'])
        cmds.delete(record['destination'])
        cmds.delete(wraps)
        manager = SkinManager()
        manager.import_skins(in_path=output, replace_existing=True)
        target_skins = [node for node, _ in proximity_wrap.direct_deformers(proximity_wrap.mesh_shape(belt))
                        if cmds.nodeType(node) == 'skinCluster']
        assert len(target_skins) == 1
        print('PASS imported baked skin onto original belt')
    cmds.select(belt)
    proximity_wrap.apply_to_selected([body])
    cmds.cutKey(j2, attribute='rotateZ', clear=True)
    cmds.setAttr(j2 + '.rotateZ', 0)
    before = set(cmds.ls())
    try:
        proximity_bake.bake_selected(0,4)
        raise AssertionError('static poses accepted')
    except RuntimeError as exc:
        assert 'no cambian' in str(exc)
    assert set(cmds.ls()) == before, 'failed bake left nodes behind'
    print('PASS static-ROM rejection and rollback')
finally:
    maya.standalone.uninitialize()
