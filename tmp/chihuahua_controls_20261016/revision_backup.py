import hashlib
import json
import struct
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
assert cmds.objExists('chihuahua')
backup=OUT/'chihuahua_before_revision.mb'
assert not backup.exists()
data=dict(scene=cmds.file(q=True,sn=True),modified=cmds.file(q=True,modified=True),frame=cmds.currentTime(q=True),selection=cmds.ls(sl=True,l=True),shapes={},meshes={},transforms={})
for n in cmds.ls(type='transform',l=True)+cmds.ls(type='joint',l=True):
    if n.startswith('|chihuahua|'):
        data['transforms'][n]=cmds.xform(n,q=True,ws=True,m=True)
for s in cmds.ls(type='mesh',l=True):
    if not cmds.getAttr(s+'.intermediateObject'):
        sl=om.MSelectionList();sl.add(s);fn=om.MFnMesh(sl.getDagPath(0))
        data['meshes'][s]=hashlib.sha256(b''.join(struct.pack('ddd',p.x,p.y,p.z) for p in fn.getPoints(om.MSpace.kWorld))).hexdigest()
for n in cmds.ls('*_CTL',type='transform',l=True):
    for s in cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []:
        data['shapes'][s]=cmds.xform(s+'.cv[*]',q=True,os=True,t=True)
cmds.file(str(backup),exportAll=True,type='mayaBinary',force=True,preserveReferences=True)
assert cmds.file(q=True,sn=True)==data['scene']
cmds.file(modified=data['modified'])
(OUT/'revision_baseline.json').write_text(json.dumps(data,indent=2))
result=dict(backup=str(backup),meshes=len(data['meshes']))
