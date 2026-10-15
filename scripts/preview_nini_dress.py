"""Open the validated sparse dress rig in interactive Maya, preserving recovery."""
import datetime
import json
from pathlib import Path
import traceback
from maya import cmds
from maya.api import OpenMaya as om

ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/'maya_tools/assets/Nini/experiments/dress_keepout'
status={}
try:
    reports=sorted(directory.glob('nini_dress_report_v*.json'),reverse=True)
    report=next(r for r in (json.loads(p.read_text(encoding='utf-8')) for p in reports) if r['passed'])
    status['previous_scene']=cmds.file(q=True,sceneName=True)
    if cmds.file(q=True,modified=True):
        recovery=ROOT.parent/'recovery'/('Before_NiniDress_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.ma')
        recovery.parent.mkdir(parents=True,exist_ok=True)
        cmds.file(str(recovery),exportAll=True,type='mayaAscii',preserveReferences=True)
        status['recovery']=str(recovery)
    status['loading']=report['scene']
    (directory/'preview_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    cmds.file(report['scene'],open=True,force=True)
    cmds.evaluationManager(mode='parallel')
    panel=next((p for p in cmds.getPanel(type='modelPanel') if cmds.modelPanel(p,q=True,camera=True)=='persp'),'modelPanel4')
    cmds.lookThru(panel,'persp')
    cmds.modelEditor(panel,e=True,displayAppearance='smoothShaded',wireframeOnShaded=False,
                     displayLights='default',grid=False,joints=False,cameras=False,
                     displayTextures=False,nurbsCurves=True,polymeshes=True,locators=False)
    cmds.setAttr('perspShape.focalLength',40)
    cmds.setAttr('perspShape.nearClipPlane',.1)
    position=om.MVector(100,100,165);target=om.MVector(0,71,0)
    back=(position-target).normal();right=(om.MVector(0,1,0)^back).normal();up=(back^right).normal()
    cmds.xform('persp',ws=True,matrix=[right.x,right.y,right.z,0,up.x,up.y,up.z,0,
                                    back.x,back.y,back.z,0,position.x,position.y,position.z,1])
    cmds.select(clear=True)
    status['images']=[]
    def capture(label):
        cmds.refresh(force=True)
        path=directory/('Nini_dress_'+label+'_'+datetime.datetime.now().strftime('%H%M%S')+'.png')
        result=cmds.playblast(frame=cmds.currentTime(q=True),format='image',compression='png',
                             completeFilename=str(path),widthHeight=(1280,960),percent=100,
                             viewer=False,showOrnaments=False,offScreen=True,editorPanelName=panel)
        status['images'].append(result)
    capture('neutral')
    control='L_ankleIk_CTL';rest=cmds.xform(control,q=True,ws=True,t=True)
    try:
        cmds.xform(control,ws=True,t=[rest[0],rest[1]+15,rest[2]+18])
        capture('step')
        cmds.setAttr('C_dressSettings_CTL.showChains',True)
        cmds.modelEditor(panel,e=True,joints=True,jointXray=True,wireframeOnShaded=True)
        capture('chains')
    finally:
        cmds.xform(control,ws=True,t=rest)
    cmds.select('C_dressSettings_CTL')
    cmds.refresh(force=True)
    cmds.file(save=True,type='mayaAscii')
    status.update(scene=report['scene'],mode=cmds.evaluationManager(q=True,mode=True),
                  dress_joints=len(cmds.ls('NiniDress_*',type='joint')))
except Exception:
    status['error']=traceback.format_exc()
finally:
    (directory/'preview_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
