import hashlib
import json
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om

OUT = Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
assert cmds.ls('chihuahua',assemblies=True), 'Wrong scene'
assert 'chihuahua' in cmds.file(q=True,sn=True).lower(), 'Wrong scene'
original = cmds.file(q=True,sn=True)
modified = cmds.file(q=True,modified=True)
file_type = cmds.file(q=True,type=True)[0]
backup = OUT/'chihuahua_before_controls.mb'
assert not backup.exists(), 'Backup exists'
try:
    cmds.file(rename=str(backup))
    cmds.file(save=True,type='mayaBinary',force=True)
finally:
    cmds.file(rename=original)
    cmds.file(type=file_type)
    cmds.file(modified=modified)

def points(n):
    sel=om.MSelectionList();sel.add(n)
    return om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)

meshes={}
for n in cmds.ls(type='mesh',l=True):
    if cmds.getAttr(n+'.intermediateObject'):
        continue
    meshes[n]=hashlib.sha256(b''.join(__import__('struct').pack('ddd',p.x,p.y,p.z) for p in points(n))).hexdigest()
transforms={n:cmds.xform(n,q=True,ws=True,m=True) for n in cmds.ls(dag=True,type='transform',long=True) if n.startswith('|chihuahua|')}
shapes={}
for n in cmds.ls('*_CTL',type='transform',l=True):
    for s in cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []:
        shapes[s]=dict(cvs=cmds.xform(s+'.cv[*]',q=True,os=True,t=True),
            world_cvs=cmds.xform(s+'.cv[*]',q=True,ws=True,t=True),
            incoming=cmds.listConnections(s,s=True,d=False,p=True,c=True) or [])
data=dict(scene=original,modified=modified,file_type=file_type,backup=str(backup),
    meshes=meshes,transforms=transforms,shapes=shapes,frame=cmds.currentTime(q=True),selection=cmds.ls(sl=True,l=True),
    camera_matrix=cmds.xform('persp',q=True,ws=True,m=True),
    nodes=sorted(cmds.ls(l=True)),connections=sorted(cmds.ls(type='skinCluster')))
(OUT/'baseline.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
verts=points('body_geo')
slices=[]
for z in (3,5,7,9,11,13,15,17):
    pts=[p for p in verts if abs(p.z-z)<.4 and p.y>8 and p.y<17]
    if pts:
        slices.append(dict(z=z,x=[min(p.x for p in pts),max(p.x for p in pts)],y=[min(p.y for p in pts),max(p.y for p in pts)]))
cmds.viewPlace('persp',eye=(48,30,65),lookAt=(0,16,13))
cmds.viewFit('persp',fitFactor=.82,allObjects=False)
result=dict(backup=str(backup),controls=len(cmds.ls('*_CTL',type='transform')),slices=slices)
