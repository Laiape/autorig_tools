from maya import cmds
from maya.api import OpenMaya as om
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary eyelid frame review')
values={}
try:
    for side in ('L','R'):
        frame=cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')
        for label in ('upper','lower'):
            plug=side+'_'+label+'LidRollPivot_MMX.matrixIn[0]'
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
            cmds.disconnectAttr(source,plug)
            cmds.setAttr(plug,frame,type='matrix')
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
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text()
    code=code.replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/tangent_trial')
    exec(compile(code,'capture_tangent','exec'))
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
