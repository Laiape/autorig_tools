import sys
import maya.cmds as cmds
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'selection':cmds.ls(sl=True,long=True),'nodes':{},'modules':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith(('leg_module_self','guide_frames'))}}
for n in cmds.ls('*frontLeg*Fetlock*CTL','*frontLeg*Pastern*CTL','*frontLeg*Pv_CTL','*frontLeg*Settings_CTL',type='transform') or []:
 result['nodes'][n]={'translate':cmds.getAttr(n+'.translate')[0],'rotate':cmds.getAttr(n+'.rotate')[0],'world_matrix':cmds.xform(n,q=True,ws=True,m=True),'attrs':{a:cmds.getAttr(n+'.'+a) for a in cmds.listAttr(n,userDefined=True) or [] if cmds.getAttr(n+'.'+a,type=True) in ('double','float','long','enum','bool')}}
