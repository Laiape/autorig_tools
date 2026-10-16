from maya import cmds
from maya.api import OpenMaya as om
from pathlib import Path
import json
cmds.undoInfo(openChunk=True,chunkName='Temporary eyelid orbit review')
try:
    frames={}
    for side in ('L','R'):
        frame=cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')
        frames[side]=frame
        for label in ('upper','lower'):
            plug=side+'_'+label+'LidRollPivot_MMX.matrixIn[0]'
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
            cmds.disconnectAttr(source,plug)
            cmds.setAttr(plug,frame,type='matrix')
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text()
    code=code.replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/orbit_trial')
    exec(compile(code,'capture_orbit','exec'))
    diagnostics={}
    for angle in (0,-25,-60,60,90):
        cmds.setAttr('L_eyelidDown_CTL.rz',angle)
        rows=[]
        inv=om.MMatrix(frames['L']).inverse()
        for i in range(21):
            stem='L_downEyelid0%d'% (i+21)
            j='L_downEyelid0%dSkinning_JNT'%i
            p=om.MPoint(*cmds.xform(j,q=True,ws=True,t=True))*inv
            rows.append([p.x,p.y,p.z])
        diagnostics[str(angle)]=rows
    Path('C:/proyectos/auto-rig/tmp/orbit_diagnostics.json').write_text(json.dumps(diagnostics))
finally:
    cmds.undoInfo(closeChunk=True)
    cmds.undo()
    cmds.refresh(force=True)
result={'restored':True}
