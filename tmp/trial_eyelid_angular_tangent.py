from maya import cmds
from maya.api import OpenMaya as om
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary angular eyelid corners')
values={}
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
        for ctl in cmds.ls(side+'_*eyelid*CTL')+cmds.ls(side+'_*Eyelid*CTL'):
            for channel in ('tx','ty','tz','rx','ry','rz'):
                plug=ctl+'.'+channel
                if cmds.getAttr(plug,settable=True):
                    values[plug]=cmds.getAttr(plug);cmds.setAttr(plug,0)
    for mtp in cmds.ls('*Eyelid*_MTP',type='motionPath'):
        stem=mtp[:-4]
        old=stem+'ProjRot_PMX'
        original=om.MMatrix(cmds.getAttr(old+'.outputMatrix'))
        info=cmds.createNode('pointOnCurveInfo')
        cmds.connectAttr(cmds.connectionInfo(mtp+'.geometryPath',sourceFromDestination=True),info+'.inputCurve')
        cmds.connectAttr(cmds.connectionInfo(mtp+'.uValue',sourceFromDestination=True),info+'.parameter')
        aim=cmds.createNode('aimMatrix')
        cmds.connectAttr(stem+'ProjPos_F4X4.output',aim+'.inputMatrix')
        cmds.setAttr(aim+'.primaryInputAxis',0,0,-1)
        cmds.setAttr(aim+'.primaryTargetMatrix',cmds.getAttr(stem+'Skinning_AIM.primaryTargetMatrix'),type='matrix')
        cmds.setAttr(aim+'.secondaryMode',2)
        cmds.setAttr(aim+'.secondaryInputAxis',1,0,0)
        cmds.connectAttr(info+'.normalizedTangent',aim+'.secondaryTargetVector')
        pmx=cmds.createNode('pickMatrix')
        cmds.connectAttr(aim+'.outputMatrix',pmx+'.inputMatrix');cmds.setAttr(pmx+'.useTranslate',0)
        current=om.MMatrix(cmds.getAttr(pmx+'.outputMatrix'))
        mmx=cmds.createNode('multMatrix')
        cmds.setAttr(mmx+'.matrixIn[0]',list(original*current.inverse()),type='matrix')
        cmds.connectAttr(pmx+'.outputMatrix',mmx+'.matrixIn[1]')
        cmds.connectAttr(mmx+'.matrixSum',stem+'Proj_MMX.matrixIn[0]',force=True)
    for plug,value in values.items():cmds.setAttr(plug,value)
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text().replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/angular_tangent_trial')
    exec(compile(code,'capture_angular','exec'))
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
