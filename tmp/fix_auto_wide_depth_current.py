from maya import cmds
import importlib
import sys
controls=cmds.ls('*.autoWideDepth',objectsOnly=True) or []
changes=[]
for node in controls:
 plug=node+'.autoWideDepth'
 if cmds.referenceQuery(node,isNodeReferenced=True):
  raise RuntimeError('Referenced control: '+node)
 destinations=cmds.listConnections(plug,s=False,d=True,p=True) or []
 changes.append((node,plug,destinations))
cmds.undoInfo(openChunk=True,chunkName='Fix Auto Wide Depth at 1')
try:
 for node,plug,destinations in changes:
  for destination in destinations:
   cmds.disconnectAttr(plug,destination)
   cmds.setAttr(destination,1.0)
  if cmds.getAttr(plug,lock=True):
   cmds.setAttr(plug,lock=False)
  cmds.deleteAttr(plug)
 for node,plug,destinations in changes:
  assert not cmds.objExists(plug),plug
  for destination in destinations:
   assert not cmds.connectionInfo(destination,isDestination=True),destination
   assert cmds.getAttr(destination)==1.0,destination
except BaseException:
 cmds.undoInfo(closeChunk=True)
 cmds.undo()
 raise
else:
 cmds.undoInfo(closeChunk=True)
for name,module in list(sys.modules.items()):
 if name.endswith('jaw_module_nurbs'):
  importlib.reload(module)
result={'controls':[n for n,p,d in changes],'fixed_inputs':{d:cmds.getAttr(d) for n,p,ds in changes for d in ds},'remaining_depth_attrs':cmds.ls('*.autoWideDepth') or []}
