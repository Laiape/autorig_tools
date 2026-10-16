from pathlib import Path
import maya.cmds as cmds
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016')
tag=globals().get('TRIAL_ARGUMENTS',{}).get('tag','before')
panel='modelPanel4'
cmds.modelEditor(panel,e=True,displayAppearance='smoothShaded',wireframeOnShaded=False,grid=False,joints=False,locators=False,nurbsSurfaces=False,polymeshes=True,nurbsCurves=True,cameras=False,displayTextures=True)
for name,pos,target in [('overall',(52,31,59),(0,11,4)),('front',(0,13,80),(0,12,4)),('side',(75,15,4),(0,12,4))]:
    cam,shape=cmds.camera(name='shapeReviewCamera')
    cmds.setAttr(shape+'.focalLength',45)
    cmds.xform(cam,ws=True,t=pos)
    aim=cmds.aimConstraint(cmds.spaceLocator(name='reviewTarget')[0],cam,aimVector=(0,0,-1),upVector=(0,1,0))
    cmds.delete(aim)
    cmds.delete('reviewTarget')
    locator=cmds.spaceLocator(name='reviewTarget')[0];cmds.xform(locator,ws=True,t=target)
    cmds.delete(cmds.aimConstraint(locator,cam,aimVector=(0,0,-1),upVector=(0,1,0)));cmds.delete(locator)
    cmds.lookThru(panel,cam)
    cmds.select(clear=True);cmds.refresh(force=True)
    cmds.playblast(completeFilename=str(base/(tag+'_'+name+'.png')),format='image',compression='png',widthHeight=(1400,1000),percent=100,viewer=False,offScreen=True,forceOverwrite=True,frame=cmds.currentTime(q=True),editorPanelName=panel)
    cmds.lookThru(panel,'persp');cmds.delete(cam)
result={'tag':tag,'images':[str(base/(tag+'_'+n+'.png')) for n in ('overall','front','side')]}
