from maya import cmds
import sys
result={'scene':cmds.file(q=True,sn=True),'modules':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith('jaw_module_nurbs')},'attrs':{}}
for node in cmds.ls('*.autoWideDepth',objectsOnly=True) or []:
 plug=node+'.autoWideDepth'
 result['attrs'][plug]={'value':cmds.getAttr(plug),'locked':cmds.getAttr(plug,lock=True),'referenced':cmds.referenceQuery(node,isNodeReferenced=True),'incoming':cmds.listConnections(plug,s=True,d=False,p=True) or [],'outgoing':cmds.listConnections(plug,s=False,d=True,p=True) or []}
