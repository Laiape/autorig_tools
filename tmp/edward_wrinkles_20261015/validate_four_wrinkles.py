import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaUI as omui
from maya_tools.scripts.tools import bifrost_wrinkles as bw, pose_blendshapes as poses, rig_validation as qa

WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_wrinkles_20261015')
config=json.loads((WORK/'cases.json').read_text())
old=json.loads((WORK/'original_setups.json').read_text())[0]
before=np.load(str(WORK/'before.npz'))
removed=np.logical_or(np.abs(old['patterns']['Eyes'])>0,np.abs(old['patterns']['Chin'])>0)
record=next(r for r in bw.export_setups() if r['prefix']=='EdwardWrinkles')
assert all(v==0 for r in ('Eyes','Chin') for v in record['patterns'][r])
assert all(r not in f['masks'] for r in ('Eyes','Chin') for f in record['controls'])
assert all(record['patterns'][r]==old['patterns'][r] for r in ('Forehead','Nose','Cheeks'))
def points():
    return np.array(bw._mesh_fn('cabeza_high')[2].getPoints())[:,:3].copy()
def primary():
    plug=cmds.connectionInfo('EdwardWrinklesGraphShape.AnimatedFace',sourceFromDestination=True)
    sl=om.MSelectionList();sl.add(plug)
    return np.array(om.MFnMesh(sl.getPlug(0).asMObject()).getPoints())[:,:3].copy()

result={'poses':{},'retained_patterns_exact':True,'retained_rest_exact':record['rest']==old['rest'],
 'removed_patterns_zero':True,'removed_controller_masks_absent':True}
data={}
with qa._session():
    view=omui.M3dView.active3dView()
    old_camera=view.getCamera().partialPathName()
    panels=[p for p in cmds.getPanel(type='modelPanel') if cmds.modelPanel(p,q=True,camera=True) in (old_camera,old_camera.replace('Shape',''))]
    panel=panels[-1] if panels else cmds.getPanel(type='modelPanel')[-1]
    cam,camshape=cmds.camera(name='EdwardFourWrinklesValidation_CAM',focalLength=50)
    cmds.setAttr(cam+'.translate',0,198,65,type='double3')
    cmds.setAttr(cam+'.rotate',0,0,0,type='double3')
    flags=('displayAppearance','displayTextures','nurbsCurves','joints','locators','grid','hud')
    display={f:cmds.modelEditor(panel,q=True,**{f:True}) for f in flags}
    try:
        cmds.modelPanel(panel,e=True,camera=cam)
        cmds.modelEditor(panel,e=True,displayAppearance='smoothShaded',displayTextures=False,nurbsCurves=False,joints=False,locators=False,grid=False,hud=False)
        with poses._temporary_values(config['neutral']):
            for name,values in config['cases'].items():
                with poses._temporary_values(values):
                    data[name]=points();base=primary();data[name+'_primary']=base
                    delta=np.linalg.norm(data[name]-base,axis=1)
                    error=np.linalg.norm(data[name]-before[name],axis=1)
                    primary_error=float(np.linalg.norm(base-before[name+'_primary'],axis=1).max())
                    if name=='brow_in': zone=(np.abs(base[:,0])<1.8)&(base[:,1]>202)&(base[:,1]<208)
                    elif name=='brow_down': zone=(np.abs(base[:,0])<1.8)&(base[:,1]>199.5)&(base[:,1]<203.5)
                    elif name=='brow_up': zone=(base[:,1]>204.5)&(np.abs(base[:,0])<7)
                    elif name=='smile': zone=(np.abs(base[:,0])>2)&(base[:,1]<197)&(base[:,1]>186)
                    else:zone=np.ones(len(base),dtype=bool)
                    result['poses'][name]={'primary_max_error_cm':primary_error,
                       'retained_area_max_error_cm':float(error[~removed].max()),
                       'expression_zone_max_wrinkle_cm':float(delta[zone].max()),
                       'overall_max_wrinkle_cm':float(delta.max())}
                    assert primary_error<1e-6,(name,primary_error)
                    assert float(error[~removed].max())<1e-4,(name,float(error[~removed].max()))
                    if name!='neutral':assert float(delta[zone].max())>.001,(name,'Inactive expression')
                    cmds.refresh(force=True)
                    cmds.playblast(completeFilename=str(WORK/(name+'_after.png')),format='image',compression='png',
                        startTime=cmds.currentTime(q=True),endTime=cmds.currentTime(q=True),viewer=False,
                        forceOverwrite=True,showOrnaments=False,offScreen=True,widthHeight=(900,1000),percent=100,
                        editorPanelName=panel)
    finally:
        cmds.modelPanel(panel,e=True,camera=old_camera)
        cmds.modelEditor(panel,e=True,**display)
        cmds.delete(cam)
        cmds.refresh(force=True)
np.savez_compressed(str(WORK/'after.npz'),**data)
(WORK/'validation.json').write_text(json.dumps(result,indent=2))
