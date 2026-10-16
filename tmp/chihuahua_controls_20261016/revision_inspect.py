import json
import sys
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
assert cmds.objExists('chihuahua')
data=dict(scene=cmds.file(q=True,sn=True),modified=cmds.file(q=True,modified=True),frame=cmds.currentTime(q=True),selection=cmds.ls(sl=True,l=True),
    modules={k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith(('curve_tool','digits_module','eye_module','eyes_module','leg_module'))},controls=[],curves=[])
for n in cmds.ls('*_CTL',type='transform',l=True):
    attrs=[]
    for a in cmds.listAttr(n,ud=True) or []:
        if cmds.getAttr(n+'.'+a,type=True) in ('bool','float','double','long','enum'):
            attrs.append(dict(name=a,keyable=cmds.getAttr(n+'.'+a,k=True),channelBox=cmds.getAttr(n+'.'+a,cb=True),locked=cmds.getAttr(n+'.'+a,l=True)))
    data['controls'].append(dict(name=n,p=cmds.xform(n,q=True,ws=True,t=True),matrix=cmds.xform(n,q=True,ws=True,m=True),attrs=attrs,
       shapes=cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []))
for s in cmds.ls(type='nurbsCurve',l=True):
    if not cmds.getAttr(s+'.intermediateObject'):
        data['curves'].append(dict(name=s,width=cmds.getAttr(s+'.lineWidth'),out=cmds.listConnections(s+'.worldSpace',s=False,d=True,p=True) or []))
data['joints']={n:cmds.xform(n,q=True,ws=True,t=True) for n in cmds.ls(type='joint',l=True) if n.startswith('|chihuahua|')}
(OUT/'revision_inspection.json').write_text(json.dumps(data,indent=2))
result=dict(scene=data['scene'],modified=data['modified'],controls=len(data['controls']),modules=data['modules'])
