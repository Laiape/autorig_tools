import sys
import os
from pathlib import Path
import numpy as np
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
sys.path.insert(0, 'C:/proyectos/auto-rig/autorig_tools')
from maya_tools.scripts.tools import eyelid_contact

snapshot = os.environ.get('EYELID_TEST_SCENE', 'C:/proyectos/auto-rig/recovery/eyelids_before_20261016_v001.mb')
cmds.file(snapshot, open=True, force=True)
cmds.evaluationManager(mode='off')
cmds.undoInfo(state=True)

def points():
    return np.array([cmds.xform(n, q=True, ws=True, m=True) for n in sorted(cmds.ls('*Eyelid*Skinning_JNT', type='joint'))])

before = points()
print('UPGRADE', eyelid_contact.upgrade(), flush=True)
after = points()
print('NEUTRAL_MAX', np.max(abs(before-after)), flush=True)
assert np.max(abs(before-after)) < 1e-5
assert not eyelid_contact.upgrade()
for side in ('L', 'R'):
    for height in (0, .2, .5, 1):
        for attr in ('Upper_Blink','Lower_Blink'):
            cmds.setAttr(side+'_eyeDirect_CTL.'+attr, 1)
        cmds.setAttr(side+'_eyeDirect_CTL.Blink_Height', height)
        cmds.setAttr(side+'_eyelidUp_CTL.rotate', 15, -10, 12)
        cmds.setAttr(side+'_eyelidDown_CTL.rotate', -10, 7, -8)
        curves = [np.array([cmds.pointOnCurve(side+'_eyelid'+label+'Rebuilded_CRV', pr=i/32, top=True, p=True) for i in range(33)]) for label in ('Up','Down')]
        print('CONTACT',side,height,float(np.max(abs(curves[0]-curves[1]))),flush=True)
        assert np.max(abs(curves[0]-curves[1])) < 1e-5
        joints = []
        for label in ('upper','down'):
            joints.append(sorted(cmds.ls(side+'_'+label+'Eyelid*Skinning_JNT'), key=lambda n:int(n.split('Eyelid0')[1].split('Skinning')[0])))
        if len(joints[0]) == len(joints[1]):
            gap = max(np.linalg.norm(np.array(cmds.xform(a,q=True,ws=True,t=True))-cmds.xform(b,q=True,ws=True,t=True)) for a,b in zip(*joints))
            print('JOINT_GAP',gap,flush=True)
            assert gap < 1e-4
print('PASS REAL SCENE',flush=True)
