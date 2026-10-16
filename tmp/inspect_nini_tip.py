import os
from maya import cmds
from maya.api import OpenMaya as om

def node_data(n):
    attrs=cmds.listAttr(n,userDefined=True) or []
    info=dict(type=cmds.nodeType(n),parent=cmds.listRelatives(n,p=True),
      t=cmds.getAttr(n+'.translate'),r=cmds.getAttr(n+'.rotate'),s=cmds.getAttr(n+'.scale'),
      world=cmds.xform(n,q=True,ws=True,t=True),
      inputs=cmds.listConnections(n,s=True,d=False,p=True,c=True) or [])
    info['attrs']={a:cmds.getAttr(n+'.'+a) for a in attrs if cmds.getAttr(n+'.'+a,type=True) in ('double','float','long','short','bool','enum')}
    return info

names=[n for n in cmds.ls(type='joint') if n.startswith(('L_','R_')) and any(w in n.lower() for w in ('leg','ankle','ball','tip','knee'))]
controls=[n for n in cmds.ls(type='transform') if n.endswith('_CTL') and any(w in n.lower() for w in ('ankle','ball','tip','legpole','legsetting'))]
result=dict(pid=os.getpid(),scene=cmds.file(q=True,sn=True),modified=cmds.file(q=True,modified=True),
    selection=cmds.ls(sl=True),time=cmds.currentTime(q=True),nodes={n:node_data(n) for n in names+controls},
    skins=cmds.ls(type='skinCluster'))
