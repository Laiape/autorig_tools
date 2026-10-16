import sys
import maya.cmds as cmds
from maya_tools.scripts.utils import rig_manager
root='C_guides_GRP'
joints=cmds.listRelatives(root,allDescendents=True,type='joint',fullPath=True) or []
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'asset':rig_manager.get_character_name_from_build(),'modules':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith(('guides_manager','rig_manager','eye_module','leg_module_self','spine_module'))},'selection':cmds.ls(sl=True,long=True),'guides':{},'settings':{},'meshes':cmds.ls(type='mesh',long=True)}
for n in joints:
 result['guides'][n]={'matrix':cmds.xform(n,q=True,ws=True,m=True),'jointOrient':cmds.getAttr(n+'.jointOrient')[0],'rotate':cmds.getAttr(n+'.rotate')[0],'translate':cmds.getAttr(n+'.translate')[0],'scale':cmds.getAttr(n+'.scale')[0],'rotateOrder':cmds.getAttr(n+'.rotateOrder'),'parent':cmds.listRelatives(n,p=True,f=True),'children':cmds.listRelatives(n,c=True,type='joint',f=True) or [],'uuid':cmds.ls(n,uuid=True)[0]}
for n in cmds.listRelatives(root,allDescendents=True,type='transform',fullPath=True) or []:
 if 'hip' in n.lower() and n not in result['guides']:
  result['guides'][n]={'matrix':cmds.xform(n,q=True,ws=True,m=True),'type':cmds.nodeType(n)}
result['settings']={a:cmds.getAttr(root+'.'+a) for a in cmds.listAttr(root,userDefined=True) or []}
