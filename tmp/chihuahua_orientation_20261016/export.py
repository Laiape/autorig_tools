from pathlib import Path
from importlib import reload
import json
import maya.cmds as cmds
from maya_tools.scripts.utils import guides_manager
reload(guides_manager)
root='C_guides_GRP'
cmds.undoInfo(openChunk=True,chunkName='Chihuahua Authored Guide Settings')
try:
 for attr in ('spine_tangents','authored_guide_orientation'):
  if not cmds.objExists(root+'.'+attr):
   cmds.addAttr(root,longName=attr,attributeType='enum',enumName='off:on',keyable=True)
  cmds.setAttr(root+'.'+attr,1)
 cmds.setAttr(root+'.spine_controllers',3)
finally:cmds.undoInfo(closeChunk=True)
folder=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua/guides')
version=max(int(p.stem.rsplit('_v',1)[1]) for p in folder.glob('chihuahua_v*.guides'))+1
path=folder/('chihuahua_v%03d.guides'%version)
result={'guides':guides_manager.get_guides_info(str(path)),'joint_matrices':{},'curves':{}}
for n in cmds.listRelatives(root,ad=True,type='joint',fullPath=True) or []:result['joint_matrices'][n.rsplit('|',1)[-1]]=cmds.xform(n,q=True,ws=True,m=True)
for n in cmds.ls('*_CRV',type='transform',long=True) or []:
 if 'controls_GRP' not in n and 'rig_GRP' not in n:
  for s in cmds.listRelatives(n,s=True,type='nurbsCurve',f=True) or []:
   result['curves'][s.rsplit('|',1)[-1]]=cmds.xform(s+'.cv[*]',q=True,ws=True,t=True)
result['settings']={a:cmds.getAttr(root+'.'+a) for a in ('spine_controllers','spine_tangents','authored_guide_orientation')}
