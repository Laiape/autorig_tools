import sys
import maya.cmds as cmds
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'modules':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith(('spine_module','rig_manager','curve_tool'))},'spine':[]}
for node in cmds.ls('C_spine*_CTL',type='transform') or []:
 if 'Attatched' in node:continue
 result['spine'].append({'node':node,'matrix':cmds.xform(node,q=True,ws=True,m=True),'parents':cmds.listRelatives(node,p=True,f=True),'visible':cmds.ls(node,visible=True),'connections':cmds.listConnections(node,s=True,d=False,p=True) or [],'attrs':cmds.listAttr(node,userDefined=True)})
result['guide_settings']={n:{a:cmds.getAttr(n+'.'+a) for a in (cmds.listAttr(n,userDefined=True) or []) if 'spine' in a.lower()} for n in cmds.ls('*guides_GRP',type='transform') or []}
