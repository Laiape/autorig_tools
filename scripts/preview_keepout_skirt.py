"""Open the latest validated demo in Maya and capture viewport previews.

Run with runpy.run_path(path) from Maya. Any current modified scene is first
exported to an independent recovery file; its original file is not overwritten.
"""
import datetime
import json
import math
from pathlib import Path
import traceback
from maya import cmds
from maya.api import OpenMaya as om

ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/'maya_tools/assets/KeepOutSkirt/experiments'
status={}
try:
    reports=([Path(REPORT_PATH)] if 'REPORT_PATH' in globals() else
             sorted(directory.glob('evaluation_report_v*.json'),reverse=True))
    candidates=[json.loads(p.read_text(encoding='utf-8')) for p in reports]
    report=next(r for r in candidates if r['passed'] and
                r.get('surface_contact',{}).get('penetrating_triangle_capsule_pairs')==0)
    original=cmds.file(query=True,sceneName=True)
    status['previous_scene']=original
    status['previous_modified']=cmds.file(query=True,modified=True)
    if cmds.file(query=True,modified=True):
        recovery=ROOT.parent/'recovery'/('Before_KeepOutSkirt_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.ma')
        if recovery.exists(): raise FileExistsError(recovery)
        cmds.file(str(recovery),exportAll=True,type='mayaAscii',preserveReferences=True)
        status['recovery']=str(recovery)
        status['previous_scene']=original
    cmds.file(report['scene'],open=True,force=True)
    cmds.evaluationManager(mode='parallel')
    data=json.loads(cmds.getAttr('KOskirt_RIG_GRP.demoData'))
    panel=next((p for p in cmds.getPanel(type='modelPanel') if cmds.modelPanel(p,query=True,camera=True)=='persp'),'modelPanel4')
    cmds.modelEditor(panel,edit=True,displayAppearance='smoothShaded',wireframeOnShaded=True,
                      displayLights='default',grid=False,joints=False,cameras=False,
                      shadows=False,displayTextures=False,nurbsCurves=True,
                      polymeshes=True,locators=False)
    cmds.lookThru(panel,'persp')
    cmds.setAttr('perspShape.focalLength',40)
    cmds.setAttr('perspShape.nearClipPlane',.1)
    position=om.MVector(95,110,145); target=om.MVector(0,68,0)
    back=(position-target).normal()
    right=(om.MVector(0,1,0)^back).normal(); up=(back^right).normal()
    matrix=om.MMatrix([right.x,right.y,right.z,0,up.x,up.y,up.z,0,
                      back.x,back.y,back.z,0,position.x,position.y,position.z,1])
    cmds.xform('persp',worldSpace=True,matrix=list(matrix))
    cmds.select(clear=True)
    images=[]
    poses=(((1,'autorig_neutral'),) if 'autorig_module' in data else
           ((1,'neutral'),(25,'step'),(73,'squat'),(97,'spread'),(121,'global')))
    for frame,label in poses:
        cmds.currentTime(frame)
        cmds.refresh(force=True)
        image=directory/('KeepOutSkirt_'+label+'.png')
        if image.exists():
            image=directory/('KeepOutSkirt_'+label+'_'+datetime.datetime.now().strftime('%H%M%S')+'.png')
        result=cmds.playblast(frame=frame,format='image',compression='png',
                               completeFilename=str(image),widthHeight=(1280,960),
                               percent=100,viewer=False,showOrnaments=False,
                               offScreen=True,editorPanelName=panel)
        images.append(result)
    cmds.currentTime(1 if 'autorig_module' in data else 25)
    cmds.select(data['legs']['L']['ik'] if 'autorig_module' in data else data['waist'])
    cmds.refresh(force=True)
    # Save camera/view and selected review pose to the already generated demo.
    cmds.file(save=True,type='mayaAscii')
    status.update({'scene':report['scene'],'images':images,'mode':cmds.evaluationManager(query=True,mode=True)})
except Exception:
    status['error']=traceback.format_exc()
finally:
    (directory/'preview_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
