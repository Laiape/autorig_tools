from maya import cmds
from maya.api import OpenMaya as om
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary world eyelid frames')
try:
    for side in ('L','R'):
        frame=cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')
        for label in ('upper','lower'):
            plug=side+'_'+label+'LidRollPivot_MMX.matrixIn[0]'
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
            cmds.disconnectAttr(source,plug);cmds.setAttr(plug,frame,type='matrix')
        for label,ctl in (('upper','Up'),('down','Down')):
            for n in cmds.ls(side+'_'+label+'Eyelid*Skinning_AIM',type='aimMatrix'):
                i=int(n.split('Eyelid0')[1].split('Skinning')[0]);i=i if label=='upper' else i-21
                t=min(i,20-i)/10.;own=.5+.5*(3*t*t-2*t*t*t)
                sums=cmds.createNode('plusMinusAverage')
                for index,(source,weight) in enumerate(((side+'_eyelid'+ctl+'_CTL.rz',own),(side+'_eyelid'+('Down' if ctl=='Up' else 'Up')+'_CTL.rz',1-own))):
                    mul=cmds.createNode('multDoubleLinear');cmds.connectAttr(source,mul+'.input1');cmds.setAttr(mul+'.input2',weight)
                    cmds.connectAttr(mul+'.output',sums+'.input1D[%d]'%index)
                cmx=cmds.createNode('composeMatrix');cmds.connectAttr(sums+'.output1D',cmx+'.inputRotateZ')
                pure=list(frame);pure[12:15]=[0,0,0]
                rot=cmds.createNode('multMatrix')
                cmds.setAttr(rot+'.matrixIn[0]',list(om.MMatrix(pure).inverse()),type='matrix')
                cmds.connectAttr(cmx+'.outputMatrix',rot+'.matrixIn[1]')
                cmds.setAttr(rot+'.matrixIn[2]',pure,type='matrix')
                original=cmds.connectionInfo(n+'.inputMatrix',sourceFromDestination=True)
                basis=cmds.createNode('pickMatrix');cmds.connectAttr(original,basis+'.inputMatrix');cmds.setAttr(basis+'.useTranslate',0)
                position=cmds.createNode('pickMatrix');cmds.connectAttr(original,position+'.inputMatrix')
                for component in ('Rotate','Scale','Shear'):cmds.setAttr(position+'.use'+component,0)
                matrix=cmds.createNode('multMatrix')
                for j,source in enumerate((basis+'.outputMatrix',rot+'.matrixSum',position+'.outputMatrix')):cmds.connectAttr(source,matrix+'.matrixIn[%d]'%j)
                cmds.connectAttr(matrix+'.matrixSum',n+'.inputMatrix',force=True)
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text().replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/worldframe_trial')
    exec(compile(code,'capture_worldframe','exec'))
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
