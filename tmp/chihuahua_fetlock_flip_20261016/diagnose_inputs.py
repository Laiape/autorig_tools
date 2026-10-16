import json
from pathlib import Path
import maya.cmds as cmds
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_fetlock_flip_20261016');rows=[]
for h in (0,2,3.8,4,4.05,4.1,4.125,4.15,4.2,4.3,5,6,7.4,8):
 cmds.setAttr('L_frontLegFetlockIk_CTL.ty',h)
 row={'h':h}
 for n in ('L_frontLegFetlockIk_CTL.worldMatrix[0]','L_frontLegFoot_CTL.worldMatrix[0]','L_frontLegPawPlantFollow_MMX.matrixSum','L_frontLegNodesEndPos_MMX.matrixSum','L_frontLegFetlockAim_AMX.inputMatrix','L_frontLegFetlockAim_AMX.outputMatrix','L_frontLegNodesRootFrame_AMX.outputMatrix','L_frontLegNodesMidFrame_AMX.outputMatrix','L_frontLegNodesLowFrame_AMX.outputMatrix'):
  if cmds.objExists(n):
   v=cmds.getAttr(n);row[n]={'pos':v[12:15],'x':v[:3],'z':v[8:11]}
 for n in ('L_frontLegNodesD2_DBT.distance','L_frontLegNodesLenA_FCN.inFloat','L_frontLegNodesLenB_FCN.inFloat','L_frontLegNodesLenC_FCN.inFloat','L_frontLegNodesChord_CND.outColorR'):
  if cmds.objExists(n):row[n]=cmds.getAttr(n)
 rows.append(row)
cmds.setAttr('L_frontLegFetlockIk_CTL.ty',0)
(base/'diagnose_inputs.json').write_text(json.dumps(rows,indent=2));result=rows
