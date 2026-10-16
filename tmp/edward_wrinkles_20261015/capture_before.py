import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaUI as omui
from maya_tools.scripts.tools import pose_blendshapes as poses, rig_validation as qa
from maya_tools.scripts.tools import bifrost_wrinkles as bw

WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_wrinkles_20261015')
settings='EdwardWrinkles_Settings'
controls=cmds.ls('*eyebrow*CTL','*lip*CTL','*Lip*CTL','*jaw*CTL',type='transform') or []
neutral={c+'.'+a:0.0 for c in controls for a in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ') if cmds.objExists(c+'.'+a) and cmds.getAttr(c+'.'+a,settable=True)}
original={p:cmds.getAttr(p) for p in neutral}
(WORK/'original_pose.json').write_text(json.dumps(original,indent=2))
cases={'neutral':{},'brow_up':{'L_eyebrowMain_CTL.translateY':2.,'R_eyebrowMain_CTL.translateY':2.},
 'brow_in':{'L_eyebrowMain_CTL.translateX':-1.5,'R_eyebrowMain_CTL.translateX':-1.5},
 'brow_down':{'L_eyebrowMain_CTL.translateY':-2.,'R_eyebrowMain_CTL.translateY':-2.},
 'smile':{p:v for p,v in original.items() if 'lipCorner' in p}}
(WORK/'cases.json').write_text(json.dumps({'neutral':neutral,'cases':cases},indent=2))
def points():
    shape,path,fn=bw._mesh_fn('cabeza_high')
    return np.array(fn.getPoints())[:,:3].copy()

data={}; summary={}
with qa._session():
    with poses._temporary_values(neutral):
        for name,values in cases.items():
            with poses._temporary_values(values):
                data[name]=points()
                # In-place primary input is sampled without changing graph routing.
                plug=cmds.connectionInfo('EdwardWrinklesGraphShape.AnimatedFace',sourceFromDestination=True)
                sl=om.MSelectionList();sl.add(plug)
                data[name+'_primary']=np.array(om.MFnMesh(sl.getPlug(0).asMObject()).getPoints())[:,:3].copy()
                delta=np.linalg.norm(data[name]-data[name+'_primary'],axis=1)
                summary[name]={'max_wrinkle_cm':float(delta.max()),'vertices_above_0p001':int((delta>.001).sum()),
                  'brow_positions':{s:cmds.xform(s+'_eyebrowMain_CTL',q=True,ws=True,t=True) for s in ('L','R')}}
    cmds.refresh(force=True)
    view=omui.M3dView.active3dView();im=om.MImage();view.readColorBuffer(im,True);im.writeToFile(str(WORK/'current_before.png'),'png')
np.savez_compressed(str(WORK/'before.npz'),**data)
result=summary
