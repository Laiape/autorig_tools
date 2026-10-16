"""Large independent eyelid rolls retain shared, finite, on-globe corners."""
from pathlib import Path
import tempfile
import math
import numpy as np
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om
from test_eyelid_blink import build


def run():
    maya.standalone.initialize(name='python')
    for plugin in ('matrixNodes','lookdevKit'):cmds.loadPlugin(plugin,quiet=True)
    try:
        for side in ('L','R'):
            frame=om.MTransformationMatrix()
            frame.setRotation(om.MEulerRotation(.3,-.5,.6))
            frame.setScale((1.3,.85,1.1),om.MSpace.kTransform)
            frame.setTranslation(om.MVector(7,4,9),om.MSpace.kTransform)
            for count,eye_frame in ((7,None),(11,None),(11,list(frame.asMatrix()))):
                eye=build(side,True,samples=count,eye_frame=eye_frame)
                eye_inverse=om.MMatrix(eye.eye_guide_matrix).inverse()
                # Calibrated tangent transport must preserve the neutral bind.
                aims=cmds.ls(side+'_*Eyelid*Skinning_AIM',type='aimMatrix')
                neutral=np.array([cmds.getAttr(n+'.outputMatrix') for n in aims])
                for n in aims:cmds.setAttr(n+'.secondaryMode',0)
                original=np.array([cmds.getAttr(n+'.outputMatrix') for n in aims])
                assert np.max(abs(neutral-original))<1e-5,('neutral orientation',np.max(abs(neutral-original)))
                for n in aims:cmds.setAttr(n+'.secondaryMode',2)
                for mode in ('off','serial','parallel'):
                    cmds.evaluationManager(mode=mode)
                    for angle in (0,-25.241064,-45,-60,-75,-90,90,75,60,45,25.241064,0):
                        for lid in ('Up','Down'):
                            cmds.setAttr(side+'_eyelidUp_CTL.rz',angle if lid=='Up' else 0)
                            cmds.setAttr(side+'_eyelidDown_CTL.rz',angle if lid=='Down' else 0)
                            cmds.setAttr(side+'_eyelid'+lid+'_CTL.ty',-.21)
                            # Keep the old central feel, with pinned endpoints
                            # and less than 10% displacement near each corner.
                            for branch,curve_label in (('upper','Up'),('lower','Down')):
                                info=side+'_'+branch+'LidOrbit_CVI'
                                curve=side+'_'+branch+'LidJoined_CRV'
                                for index in (0,1,3,5,6):
                                    raw=om.MVector(*[cmds.getAttr(info+'.controlPoints[%d].%sValue'%(index,axis)) for axis in 'xyz'])
                                    actual=om.MVector(*cmds.pointPosition(curve+'.cv[%d]'%index,w=True))
                                    full=om.MVector(*cmds.pointPosition(side+'_eyelid'+curve_label+'Pose_CRV.cv[%d]'%index,w=True))
                                    if index in (0,6) or curve_label!=lid:
                                        assert (actual-raw).length()<1e-5
                                    elif index in (1,5):
                                        assert (actual-raw).length()<.1*(full-raw).length()+1e-5
                                    else:
                                        assert (actual-full).length()<1e-5
                            for blink in (0,.5,1):
                                for attr in ('Upper_Blink','Lower_Blink'):
                                    cmds.setAttr(eye.eye_direct_ctl+'.'+attr,blink)
                                for index in (0,count-1):
                                    a=np.array(cmds.xform(side+'_upperEyelid0%dSkinning_JNT'%index,q=True,ws=True,t=True))
                                    b=np.array(cmds.xform(side+'_downEyelid0%dSkinning_JNT'%index,q=True,ws=True,t=True))
                                    assert np.linalg.norm(a-b)<1e-4,(side,lid,angle,blink,index,a,b)
                                for label in ('upper','down'):
                                    points=[]
                                    for index in range(count):
                                        joint=side+'_'+label+'Eyelid0%dSkinning_JNT'%index
                                        matrix=cmds.getAttr(joint+'.worldMatrix[0]')
                                        assert np.isfinite(matrix).all()
                                        p=om.MPoint(*matrix[12:15])*eye_inverse
                                        assert abs(om.MVector(p.x,p.y,p.z).length()-eye.eye_radius)<1e-4,(side,lid,angle,blink,index)
                                        points.append(np.array(matrix[12:15]))
                                    assert min(np.linalg.norm(b-a) for a,b in zip(points,points[1:]))>.001
                                if blink==1:
                                    upper=np.array([cmds.getAttr(side+'_upperEyelid0%dSkinning_JNT.worldMatrix[0]'%i) for i in range(count)])
                                    lower=np.array([cmds.getAttr(side+'_downEyelid0%dSkinning_JNT.worldMatrix[0]'%i) for i in range(count)])
                                    assert np.max(abs(upper-lower))<1e-4,('contact orientation',side,angle,np.max(abs(upper-lower)))
                            cmds.setAttr(side+'_eyelid'+lid+'_CTL.ty',0)
                assert not (cmds.cycleCheck(all=True,list=True) or [])
                with tempfile.TemporaryDirectory() as folder:
                    path=str(Path(folder)/'joined.ma')
                    joints=cmds.ls(side+'_*Eyelid*Skinning_JNT',type='joint')
                    expected=np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joints])
                    cmds.file(rename=path);cmds.file(save=True,type='mayaAscii',force=True)
                    cmds.file(path,open=True,force=True)
                    actual=np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joints])
                    assert np.allclose(actual,expected,atol=1e-6,rtol=0)
        print('PASS shared corners: independent Up/Down roll -90..90, translation, blink position/orientation, unchanged bind, L/R, 7/11 guides, rotated/scaled eye frames, DG/Serial/Parallel, native reopen')
    finally:
        maya.standalone.uninitialize()


if __name__=='__main__':run()
