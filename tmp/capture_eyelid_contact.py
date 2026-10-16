from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om
folder = Path('C:/proyectos/auto-rig/tmp/eyelid_visual_20261016')
folder.mkdir(exist_ok=True)
panels = cmds.getPanel(type='modelPanel')
panel = next((p for p in panels if cmds.modelEditor(p, q=True, activeView=True)), panels[0])
original_camera = cmds.modelPanel(panel, q=True, camera=True)
selection = cmds.ls(sl=True, long=True)
attrs = [side+'_eyeDirect_CTL.'+attr for side in ('L','R') for attr in ('Upper_Blink','Lower_Blink')]
values = [cmds.getAttr(attr) for attr in attrs]
visibility = 'C_face_CTL.Eyes'
has_visibility = cmds.objExists(visibility)
eyes_visibility = cmds.getAttr(visibility) if has_visibility else None
camera = None
try:
    left = om.MMatrix(cmds.getAttr('L_eyeSkinning_JNT.worldMatrix[0]'))
    right = om.MMatrix(cmds.getAttr('R_eyeSkinning_JNT.worldMatrix[0]'))
    a,b = om.MVector(*list(left)[12:15]),om.MVector(*list(right)[12:15])
    center = (a+b)*.5
    distance = (a-b).length()*3.8
    axis = om.MVector(*list(left)[8:11]).normal()
    location = center+axis*distance
    matrix = list(left)
    matrix[12:15] = [location.x,location.y,location.z]
    camera = cmds.camera(name='eyelidReview_TEMP', focalLength=60)[0]
    cmds.xform(camera, ws=True, m=matrix)
    cmds.lookThru(panel, camera)
    if has_visibility:
        cmds.setAttr(visibility, 0)
    for state in ('open','closed'):
        for attr in attrs:
            cmds.setAttr(attr, 1 if state == 'closed' else 0)
        cmds.refresh(force=True)
        cmds.playblast(format='image', compression='png', completeFilename=str(folder/(state+'.png')),
                       frame=cmds.currentTime(q=True), widthHeight=(960,640), percent=100,
                       showOrnaments=False, viewer=False, offScreen=True, forceOverwrite=True,
                       editorPanelName=panel)
finally:
    for attr,value in zip(attrs,values):
        cmds.setAttr(attr,value)
    if has_visibility:
        cmds.setAttr(visibility,eyes_visibility)
    cmds.lookThru(panel,original_camera)
    if camera and cmds.objExists(camera):
        cmds.delete(camera)
    cmds.select(selection, r=True) if selection else cmds.select(clear=True)
    cmds.refresh(force=True)
result = {'images': [str(folder/(state+'.png')) for state in ('open','closed')]}
