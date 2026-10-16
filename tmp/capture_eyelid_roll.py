from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om
folder=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/docs/validation/eyelid_variants_20261016/visual_roll')
folder.mkdir(exist_ok=True)
panel=next(p for p in cmds.getPanel(type='modelPanel') if cmds.modelEditor(p,q=True,activeView=True))
camera_before=cmds.modelPanel(panel,q=True,camera=True)
curves_before=cmds.modelEditor(panel,q=True,nurbsCurves=True)
selection=cmds.ls(sl=True,long=True)
modified=cmds.file(q=True,modified=True)
undo=cmds.undoInfo(q=True,state=True)
attrs=[side+'_eyeDirect_CTL.'+attr for side in ('L','R') for attr in ('Upper_Blink','Lower_Blink')]
attrs+=[side+'_eyelid'+label+'_CTL.rz' for side in ('L','R') for label in ('Up','Down')]
values={attr:cmds.getAttr(attr) for attr in attrs}
if any(not cmds.getAttr(attr,settable=True) for attr in attrs):raise RuntimeError('Animated pose channels: capture in isolated scene instead')
camera=None
cmds.undoInfo(stateWithoutFlush=False)
try:
    left=list(cmds.getAttr('L_eyeSkinning_JNT.worldMatrix[0]'))
    right=list(cmds.getAttr('R_eyeSkinning_JNT.worldMatrix[0]'))
    a,b=om.MVector(*left[12:15]),om.MVector(*right[12:15])
    location=(a+b)*.5+om.MVector(*left[8:11]).normal()*(a-b).length()*3.8
    left[12:15]=[location.x,location.y,location.z]
    camera=cmds.camera(name='eyelidRollReview_TEMP',focalLength=60)[0]
    cmds.xform(camera,ws=True,m=left);cmds.lookThru(panel,camera)
    cmds.modelEditor(panel,e=True,nurbsCurves=False)
    images=[]
    for state in ('open','lower_roll','closed_roll'):
        for attr in attrs:cmds.setAttr(attr,0)
        if state!='open':
            cmds.setAttr('L_eyelidDown_CTL.rz',20)
            cmds.setAttr('R_eyelidDown_CTL.rz',-20)
        if state=='closed_roll':
            for side in ('L','R'):
                for attr in ('Upper_Blink','Lower_Blink'):cmds.setAttr(side+'_eyeDirect_CTL.'+attr,1)
        cmds.refresh(force=True)
        path=str(folder/(state+'.png'))
        cmds.playblast(format='image',compression='png',completeFilename=path,
                       frame=cmds.currentTime(q=True),widthHeight=(960,640),percent=100,
                       showOrnaments=False,viewer=False,offScreen=True,forceOverwrite=True,editorPanelName=panel)
        images.append(path)
finally:
    for attr,value in values.items():cmds.setAttr(attr,value)
    cmds.lookThru(panel,camera_before);cmds.modelEditor(panel,e=True,nurbsCurves=curves_before)
    if camera and cmds.objExists(camera):cmds.delete(camera)
    cmds.select(selection,r=True) if selection else cmds.select(clear=True)
    cmds.undoInfo(stateWithoutFlush=undo);cmds.file(modified=modified)
    cmds.refresh(force=True)
result={'images':images,'pose_restored':True}
