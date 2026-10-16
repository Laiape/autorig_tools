"""Primary Z pose uses the original moving main-control pivot."""
from test_eyelid_blink import build, sample
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
import math


def run():
    maya.standalone.initialize(name='python')
    for plugin in ('matrixNodes', 'lookdevKit'):
        cmds.loadPlugin(plugin, quiet=True)
    try:
        for side in ('L', 'R'):
            for surface in (False, True):
                eye = build(side, surface)
                for label in ('Up', 'Down'):
                    ctl = side+'_eyelid'+label+'_CTL'
                    curve = side+'_eyelid'+label+'Pose_CRV'
                    for translated in (False, True):
                        cmds.setAttr(ctl+'.translate', .1 if translated else 0, .2 if translated else 0, 0)
                        original = [om.MPoint(*cmds.pointPosition(cv, w=True)) for cv in cmds.ls(curve+'.cv[*]', fl=True)]
                        pivot = om.MMatrix(cmds.getAttr(side+'_eyelid'+label+'Local_JNT.worldMatrix[0]'))
                        rotation = om.MEulerRotation(0,0,math.radians(25)).asMatrix()
                        expected_world = pivot.inverse()*rotation*pivot
                        cmds.setAttr(ctl+'.rotateZ', 25)
                        actual = [om.MPoint(*cmds.pointPosition(cv, w=True)) for cv in cmds.ls(curve+'.cv[*]', fl=True)]
                        assert max((a-p*expected_world).length() for a,p in zip(actual, original)) < 1e-6
                        assert all((a-p).length() > .001 for index,(a,p) in enumerate(zip(actual,original)) if index != 3)
                        for attr in ('Upper_Blink','Lower_Blink'):
                            cmds.setAttr(eye.eye_direct_ctl+'.'+attr, 1)
                        closed = sample(eye)
                        assert np.max(abs(closed[0]-closed[1])) < 1e-5
                        for attr in ('Upper_Blink','Lower_Blink'):
                            cmds.setAttr(eye.eye_direct_ctl+'.'+attr, 0)
                        cmds.setAttr(ctl+'.rotateZ', 0)
                    cmds.setAttr(ctl+'.translate',0,0,0)
                assert not (cmds.cycleCheck(all=True, list=True) or [])
        print('PASS main-control pivot: rigid source pose, both lids/L/R, shared closure, no cycles')
    finally:
        maya.standalone.uninitialize()


if __name__ == '__main__':
    run()
