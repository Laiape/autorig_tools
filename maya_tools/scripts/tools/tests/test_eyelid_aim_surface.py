"""Portable aim globe coverage: affine frames, ellipsoids, poles, contact/reopen."""
import math
from pathlib import Path
import tempfile
import numpy as np
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om
from test_eyelid_blink import build


def run():
    maya.standalone.initialize(name='python')
    for plugin in ('matrixNodes','lookdevKit'):
        cmds.loadPlugin(plugin,quiet=True)
    from maya_tools.scripts.tools import eyelid_candidates
    try:
        cases=[]
        for translation,rotation,scale,radii in (
                ((3,12,-4),(0,0,0),(1,1,1),(2,2,2)),
                ((-20,30,11),(27,-41,18),(1,1,1),(3,1.7,2.4)),
                ((100,-12,5),(-35,76,53),(1.6,.7,2.1),(.9,1.5,1.1))):
            transform=om.MTransformationMatrix()
            transform.setTranslation(om.MVector(*translation),om.MSpace.kWorld)
            transform.setRotation(om.MEulerRotation(*[math.radians(x) for x in rotation]))
            transform.setScale(scale,om.MSpace.kTransform)
            cases.append((list(transform.asMatrix()),radii))
        maximum=0.
        for side in ('L','R'):
            for frame,radii in cases:
                eye=build(side,True,eye_frame=frame,radii=radii,samples=11)
                result=eyelid_candidates.aim(side,radii=radii,eye_matrix=frame)
                scale=om.MMatrix([radii[0],0,0,0,0,radii[1],0,0,0,0,radii[2],0,0,0,0,1])
                inverse=(scale*om.MMatrix(frame)).inverse()
                joints=sorted(cmds.ls(side+'_*Eyelid*Skinning_JNT',type='joint'))
                for mode in ('off','serial','parallel'):
                    cmds.evaluationManager(mode=mode)
                    for blink,roll,translation in ((0,0,0),(.4,25,.2),(1,-30,.1),(.7,5,-.3),(0,0,100),(0,0,-100),(0,0,0)):
                        for label in ('Up','Down'):
                            cmds.setAttr(side+'_eyelid'+label+'_CTL.rotateZ',roll if label=='Down' else -roll*.3)
                            cmds.setAttr(side+'_eyelid'+label+'_CTL.translateY',translation)
                        for attr in ('Upper_Blink','Lower_Blink'):
                            cmds.setAttr(eye.eye_direct_ctl+'.'+attr,blink)
                        for joint in joints:
                            value=cmds.getAttr(joint+'.worldMatrix[0]')
                            assert np.isfinite(value).all(),(side,mode,joint)
                            point=om.MPoint(*value[12:15])*inverse
                            error=abs(point.x**2+point.y**2+point.z**2-1)
                            maximum=max(maximum,error)
                            assert error<1e-6,(side,mode,radii,error)
                        if blink==1:
                            for index in range(11):
                                a=cmds.xform(side+'_upperEyelid0%dSkinning_JNT'%index,q=True,ws=True,t=True)
                                b=cmds.xform(side+'_downEyelid0%dSkinning_JNT'%index,q=True,ws=True,t=True)
                                assert np.linalg.norm(np.array(a)-b)<1e-4
                assert not (cmds.cycleCheck(all=True,list=True) or [])
                expected=np.array([cmds.getAttr(j+'.worldMatrix[0]') for j in joints])
                with tempfile.TemporaryDirectory() as folder:
                    path=str(Path(folder)/'aim.ma')
                    cmds.file(rename=path);cmds.file(save=True,type='mayaAscii',force=True)
                    cmds.file(path,open=True,force=True)
                    actual=np.array([cmds.getAttr(j+'.worldMatrix[0]') for j in joints])
                    assert np.allclose(actual,expected,atol=1e-6,rtol=0)
        print('PASS portable aim: L/R, spheres/ellipsoids, arbitrary affine rest frames, extremes/poles, contact, DG/serial/parallel, six builds/reopens; max normalized surface error',maximum)
    finally:
        maya.standalone.uninitialize()


if __name__=='__main__':run()
