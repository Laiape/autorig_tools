import maya.cmds as c
controls=[n for n in c.ls(type='transform') if c.attributeQuery('wrinkleValue',node=n,exists=True) and c.attributeQuery('wrinkleDepth',node=n,exists=True)]
result=[]
c.undoInfo(openChunk=True,chunkName='Wrinkle defaults and order')
try:
 for n in controls:
  links={}
  for a in ('wrinkleValue','wrinkleDepth'):
   p=n+'.'+a
   links[a]={'in':c.listConnections(p,s=True,d=False,p=True) or [],'out':c.listConnections(p,s=False,d=True,p=True) or []}
   if c.getAttr(p,lock=True): c.setAttr(p,lock=False)
   c.deleteAttr(p)
  for a,label,default in (('wrinkleValue','Wrinkle Value',1.),('wrinkleDepth','Wrinkle Depth',0.)):
   kwargs=dict(longName=a,niceName=label,attributeType='double',defaultValue=default,minValue=0.,keyable=True)
   if a=='wrinkleValue': kwargs['maxValue']=1.
   c.addAttr(n,**kwargs)
   p=n+'.'+a
   for src in links[a]['in']: c.connectAttr(src,p,force=True)
   for dst in links[a]['out']: c.connectAttr(p,dst,force=True)
   if not links[a]['in']: c.setAttr(p,default)
  attrs=c.listAttr(n,ud=True)
  assert attrs.index('wrinkleValue')<attrs.index('wrinkleDepth')
  assert c.attributeQuery('wrinkleDepth',node=n,listDefault=True)==[0.]
  assert c.attributeQuery('wrinkleValue',node=n,listDefault=True)==[1.]
  result.append(n)
finally:
 c.undoInfo(closeChunk=True)
