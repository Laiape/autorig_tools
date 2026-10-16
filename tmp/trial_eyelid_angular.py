from maya import cmds
from maya.api import OpenMaya as om
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary angular eyelid corners')
try:
    for side in ('L','R'):
        frame=om.MMatrix(cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix'))
        for label,ctl in (('upper','Up'),('lower','Down')):
            pose=side+'_eyelid'+ctl+'Pose_CRV'
            world=om.MMatrix(cmds.getAttr(pose+'.worldMatrix[0]'))
            pivot=frame*world.inverse()
            info=cmds.createNode('curveInfo')
            src=cmds.connectionInfo(side+'_'+label+'LidRoll_TG.inputGeometry',sourceFromDestination=True)
            cmds.connectAttr(src,info+'.inputCurve')
            joined=cmds.listRelatives(side+'_'+label+'LidJoined_CRV',s=True,ni=True,f=True)[0]
            for i,weight in enumerate((.5,.5,.75,1,.75,.5,.5)):
                sums=cmds.createNode('plusMinusAverage')
                for j,(source,w) in enumerate(((side+'_eyelid'+ctl+'_CTL.rz',weight),(side+'_eyelid'+('Down' if ctl=='Up' else 'Up')+'_CTL.rz',1-weight))):
                    mul=cmds.createNode('multDoubleLinear');cmds.connectAttr(source,mul+'.input1');cmds.setAttr(mul+'.input2',w)
                    cmds.connectAttr(mul+'.output',sums+'.input1D[%d]'%j)
                cmx=cmds.createNode('composeMatrix');cmds.connectAttr(sums+'.output1D',cmx+'.inputRotateZ')
                matrix=cmds.createNode('multMatrix')
                cmds.setAttr(matrix+'.matrixIn[0]',list(pivot.inverse()),type='matrix')
                cmds.connectAttr(cmx+'.outputMatrix',matrix+'.matrixIn[1]');cmds.setAttr(matrix+'.matrixIn[2]',list(pivot),type='matrix')
                point=cmds.createNode('pointMatrixMult');cmds.connectAttr(matrix+'.matrixSum',point+'.inMatrix')
                for axis in 'xyz':
                    cmds.connectAttr(info+'.controlPoints[%d].%sValue'%(i,axis),point+'.inPoint'+axis.upper())
                    cmds.connectAttr(point+'.output'+axis.upper(),joined+'.controlPoints[%d].%sValue'%(i,axis),force=True)
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text().replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/angular_trial')
    exec(compile(code,'capture_angular','exec'))
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
