import sys
import maya.cmds as c
controls=sorted(set((c.ls('*.wrinkleDepth',objectsOnly=True) or [])+(c.ls('*.wrinkleValue',objectsOnly=True) or [])))
result={'scene':c.file(q=True,sn=True),'modules':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith('bifrost_wrinkles')},'controls':{}}
for n in controls:
 attrs=c.listAttr(n,ud=True) or []
 result['controls'][n]={'order':[a for a in attrs if a in ('wrinkleValue','wrinkleDepth')]}
 for a in ('wrinkleValue','wrinkleDepth'):
  if c.attributeQuery(a,node=n,exists=True):
   p=n+'.'+a
   result['controls'][n][a]={'default':c.attributeQuery(a,node=n,listDefault=True),'value':c.getAttr(p),'locked':c.getAttr(p,lock=True),'incoming':c.listConnections(p,s=True,d=False,p=True) or [],'outgoing':c.listConnections(p,s=False,d=True,p=True) or []}
