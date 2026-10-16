import json
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_fetlock_flip_20261016')
guides=json.loads(Path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016/exported.json').read_text())['result']['joint_matrices']
result=[]
for side in ('L','R'):
 for limb in ('frontLeg','backLeg'):
  foot=side+'_'+limb+'Foot_CTL'
  inv=om.MMatrix(cmds.getAttr(foot+'.worldInverseMatrix[0]'))
  for label,joint in (('Fetlock','Fetlock'),('Pastern','Pastern')):
   amx=side+'_'+limb+label+'Aim_AMX'
   axis=cmds.getAttr(amx+'.primaryInputAxis')[0]
   lateral=(0,0,1)
   rest=om.MMatrix(guides[side+'_'+limb+joint+'_JNT'])
   up=(om.MVector(*lateral)*rest*inv).normal()
   cmds.setAttr(amx+'.secondaryInputAxis',*lateral,type='double3')
   cmds.setAttr(amx+'.secondaryTargetVector',*up,type='double3')
   cmds.connectAttr(foot+'.worldMatrix[0]',amx+'.secondaryTargetMatrix',force=True)
   cmds.setAttr(amx+'.secondaryMode',2)
   result.append(amx)
