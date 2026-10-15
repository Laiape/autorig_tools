"""Apply the tested smooth weights to the live rig, preserving its current pose."""
import datetime
import importlib
import json
from pathlib import Path
import traceback
from maya import cmds
from maya_tools.scripts.tools import muscle_keepout_skirt as tool
importlib.reload(tool)

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'maya_tools/assets/KeepOutSkirt/experiments'
status={}
selection=cmds.ls(selection=True,long=True) or []
try:
    report=json.loads((DIRECTORY/'smooth_weights_validation.json').read_text(encoding='utf-8'))
    if not report['passed']: raise RuntimeError('Smoothed weights have not passed validation.')
    data=json.loads(cmds.getAttr('KOskirt_RIG_GRP.demoData'))
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    recovery=ROOT.parent/'recovery'/('Before_SmoothSkirtWeights_'+stamp+'.ma')
    if recovery.exists(): raise FileExistsError(recovery)
    cmds.file(str(recovery),exportAll=True,type='mayaAscii',preserveReferences=True)
    status['recovery']=str(recovery)
    # Capture the user's current pose/view, then edit just weights and cushion.
    panel=cmds.getPanel(withFocus=True)
    if panel not in cmds.getPanel(type='modelPanel'):
        panel=next(p for p in cmds.getPanel(type='modelPanel') if cmds.modelPanel(p,q=True,camera=True)=='persp')
    images=[]
    for phase in ('before','after'):
        if phase=='after':
            cmds.undoInfo(openChunk=True,chunkName='Smooth skirt skin weights')
            try:
                cmds.setAttr(data['waist']+'.collisionMargin',max(cmds.getAttr(data['waist']+'.collisionMargin'),
                                                                report['collision_margin_cm']))
                profile=report['weight_profile']
                status['weights']=tool.smooth_skin_weights(data,sigma=profile['sigma_cm'],
                         strength=profile['strength'],waist_rows=profile['waist_fade_rows'],undoable=True)
            finally: cmds.undoInfo(closeChunk=True)
        cmds.refresh(force=True)
        path=DIRECTORY/('Skirt_smooth_weights_'+phase+'_'+stamp+'.png')
        images.append(cmds.playblast(frame=cmds.currentTime(q=True),format='image',compression='png',
             completeFilename=str(path),widthHeight=(1280,960),percent=100,viewer=False,
             showOrnaments=False,offScreen=True,editorPanelName=panel))
    snapshot=tool._snapshot(data)
    clearance,count,triangles=tool._triangle_body_clearances(data,snapshot['points'])
    status['current_pose_contact']={'minimum_body_clearance_cm':clearance,
                                     'penetrating_pairs':count,'triangles':triangles}
    status['collision_margin_cm']=cmds.getAttr(data['waist']+'.collisionMargin')
    status['mode']=cmds.evaluationManager(q=True,mode=True)
    status['fallback']=cmds.evaluationManager(q=True,fallbackTriggered=True)
    if count: raise RuntimeError('Current pose penetrates the body after blending weights.')
    version=1
    while (DIRECTORY/'KeepOutSkirt_autorig_smooth_v{:03d}.ma'.format(version)).exists(): version+=1
    scene=DIRECTORY/'KeepOutSkirt_autorig_smooth_v{:03d}.ma'.format(version)
    cmds.select(selection,replace=True) if selection else cmds.select(clear=True)
    cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii')
    status.update({'scene':str(scene),'images':images,'passed':True})
except Exception:
    status['error']=traceback.format_exc()
    status['passed']=False
finally:
    cmds.select(selection,replace=True) if selection else cmds.select(clear=True)
    (DIRECTORY/'smooth_weights_applied.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
