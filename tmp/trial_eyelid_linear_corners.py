from maya import cmds
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary affine eyelid corners')
try:
    for side in ('L','R'):
        frame=cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')
        for label in ('upper','lower'):
            plug=side+'_'+label+'LidRollPivot_MMX.matrixIn[0]'
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
            cmds.disconnectAttr(source,plug);cmds.setAttr(plug,frame,type='matrix')
            for i,t in enumerate((0,1/12.,.25,.5,.75,11/12.,1)):
                total=side+'_'+label+'LidJoined%02d_PMA'%i
                for ci,(corner,weight) in enumerate((('In',1-t),('Out',t))):
                    mul=cmds.createNode('multiplyDivide')
                    delta=side+'_'+label+'Lid'+corner+'Delta_PMA'
                    for axis,child in zip('XYZ','xyz'):
                        cmds.connectAttr(delta+'.output3D'+child,mul+'.input1'+axis)
                        cmds.setAttr(mul+'.input2'+axis,weight)
                        cmds.connectAttr(mul+'.output'+axis,total+'.input3D[%d].input3D%s'%(ci+1,child),force=True)
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text().replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/linear_trial')
    exec(compile(code,'capture_linear','exec'))
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
