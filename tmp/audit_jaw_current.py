from maya import cmds
from collections import Counter
result={'scene':cmds.file(q=True,sn=True),'evaluation_mode':cmds.evaluationManager(q=True,mode=True),'groups':{},'jaw_upstream':{},'deformers':{},'node_types':dict(Counter(cmds.nodeType(n) for n in cmds.ls()))}
roots=['C_jawModule_GRP','C_jawSkinning_GRP','C_jawControllers_GRP','C_lipsSkinning_GRP']
for root in roots:
 if cmds.objExists(root):
  nodes=cmds.listRelatives(root,ad=True,fullPath=True) or []
  result['groups'][root]={'nodes':len(nodes),'types':dict(Counter(cmds.nodeType(n) for n in nodes))}
outputs=cmds.listRelatives('C_lipsSkinning_GRP',ad=True,type='joint') or []
up=set()
for node in outputs:
 up.update(cmds.listHistory(node,pruneDagObjects=True) or [])
result['jaw_upstream']={'outputs':len(outputs),'nodes':len(up),'types':dict(Counter(cmds.nodeType(n) for n in up))}
for mesh in ['cabeza_low','cabeza_high']:
 if cmds.objExists(mesh):
  hist=cmds.listHistory(mesh,pruneDagObjects=True) or []
  result['deformers'][mesh]=[{'node':n,'type':cmds.nodeType(n),'envelope':cmds.getAttr(n+'.envelope') if cmds.objExists(n+'.envelope') else None} for n in hist if cmds.objectType(n,isAType='geometryFilter') or cmds.nodeType(n)=='bifrostGraphShape']
result['dgtimer_help']=cmds.help('dgtimer')
