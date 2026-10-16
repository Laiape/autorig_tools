import json,math
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_fetlock_flip_20261016')
result={}
for side in ('L','R'):
 ctl=side+'_frontLegFetlockIk_CTL'
 if not cmds.objExists(ctl):continue
 joints=cmds.ls(side+'_frontLeg*Skinning_JNT',type='joint') or []
 extra=[side+'_frontLegPasternAim_AMX.outputMatrix',side+'_frontLegFetlockAim_AMX.outputMatrix',side+'_frontLegNodesRootFrame_AMX.outputMatrix',side+'_frontLegNodesMidFrame_AMX.outputMatrix',side+'_frontLegNodesLowFrame_AMX.outputMatrix']
 nodes=[j+'.worldMatrix[0]' for j in joints]+[p for p in extra if cmds.objExists(p)]
 previous=None;worst=[];rows=[]
 for step in range(201):
  height=step*.05;cmds.setAttr(ctl+'.ty',height)
  values={p:om.MTransformationMatrix(om.MMatrix(cmds.getAttr(p))).rotation(asQuaternion=True) for p in nodes}
  if previous:
   for p,q in values.items():
    a=previous[p];dot=abs(sum(x*y for x,y in zip((q.x,q.y,q.z,q.w),(a.x,a.y,a.z,a.w))))
    angle=math.degrees(2*math.acos(min(1.,dot)))
    worst.append((angle,height,p))
  rows.append({'height':height,'fetlock':cmds.xform(side+'_frontLegFetlockSkinning_JNT',q=True,ws=True,t=True),'pastern':cmds.xform(side+'_frontLegPasternSkinning_JNT',q=True,ws=True,t=True)})
  previous=values
 cmds.setAttr(ctl+'.ty',0)
 result[side]={'largest_angle_steps':sorted(worst,reverse=True)[:18],'positions':rows}
(base/'sweep.json').write_text(json.dumps(result,indent=2))
result={s:v['largest_angle_steps'] for s,v in result.items()}
