from maya import cmds
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary eyelid roll frame review')
try:
    for side in ('L','R'):
        frame=cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')
        for label in ('upper','lower'):
            plug=side+'_'+label+'LidRollPivot_MMX.matrixIn[0]'
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
            cmds.disconnectAttr(source,plug);cmds.setAttr(plug,frame,type='matrix')
        for label,ctl in (('upper','Up'),('down','Down')):
            nodes=cmds.ls(side+'_'+label+'Eyelid*Proj_MMX',type='multMatrix')
            for n in nodes:
                i=int(n.split('Eyelid0')[1].split('Proj')[0]);i=i if label=='upper' else i-21
                t=min(i,20-i)/10.
                own=.5+.5*(3*t*t-2*t*t*t)
                sums=cmds.createNode('plusMinusAverage')
                for index,(source,weight) in enumerate(((side+'_eyelid'+ctl+'_CTL.rz',own),(side+'_eyelid'+('Down' if ctl=='Up' else 'Up')+'_CTL.rz',1-own))):
                    mul=cmds.createNode('multDoubleLinear');cmds.connectAttr(source,mul+'.input1');cmds.setAttr(mul+'.input2',weight)
                    cmds.connectAttr(mul+'.output',sums+'.input1D[%d]'%index)
                cmx=cmds.createNode('composeMatrix');cmds.connectAttr(sums+'.output1D',cmx+'.inputRotateZ')
                mmx=cmds.createNode('multMatrix')
                cmds.connectAttr(cmx+'.outputMatrix',mmx+'.matrixIn[0]')
                cmds.connectAttr(cmds.connectionInfo(n+'.matrixIn[0]',sourceFromDestination=True),mmx+'.matrixIn[1]')
                cmds.connectAttr(mmx+'.matrixSum',n+'.matrixIn[0]',force=True)
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text().replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/rollframe_trial')
    exec(compile(code,'capture_rollframe','exec'))
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
