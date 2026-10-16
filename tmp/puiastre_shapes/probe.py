import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as c
src=c.circle(ch=False)[0]; s=c.listRelatives(src,s=True,f=True)[0]; tgt=c.createNode('transform'); n=c.createNode('nurbsCurve',parent=tgt)
c.connectAttr(s+'.local',n+'.create'); print('CONNECTED',c.getAttr(n+'.controlPoints',size=True),c.xform(n+'.cv[*]',q=True,os=True,t=True)); c.disconnectAttr(s+'.local',n+'.create'); c.delete(src); print('DISCONNECTED',c.getAttr(n+'.controlPoints',size=True),c.xform(n+'.cv[*]',q=True,os=True,t=True))
result=True
