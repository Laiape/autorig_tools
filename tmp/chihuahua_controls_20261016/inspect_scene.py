import json
import sys
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om

out = Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
controls = []
for n in cmds.ls('*_CTL', type='transform', long=True):
    shapes = cmds.listRelatives(n, s=True, ni=True, f=True, type='nurbsCurve') or []
    controls.append(dict(name=n, position=cmds.xform(n,q=True,ws=True,t=True),
        matrix=cmds.xform(n,q=True,ws=True,m=True), bbox=cmds.exactWorldBoundingBox(n,ignoreInvisible=False),
        visible=cmds.ls(n,visible=True)!=[], color=cmds.getAttr(n+'.overrideColor'),
        override=cmds.getAttr(n+'.overrideEnabled'), shapes=[dict(name=s,
        cvs=cmds.getAttr(s+'.controlPoints',size=True), bbox=cmds.exactWorldBoundingBox(s),
        color=cmds.getAttr(s+'.overrideColor'),override=cmds.getAttr(s+'.overrideEnabled'),
        incoming=cmds.listConnections(s+'.create',s=True,d=False,p=True) or []) for s in shapes]))
data = dict(scene=cmds.file(q=True,sn=True),modified=cmds.file(q=True,modified=True),
    frame=cmds.currentTime(q=True),selection=cmds.ls(sl=True,l=True),
    modules={k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith(('curve_tool','create_rig','rig_manager'))},
    controls=controls, meshes=[dict(name=n,bbox=cmds.exactWorldBoundingBox(n)) for n in cmds.ls(type='mesh',long=True) if not cmds.getAttr(n+'.intermediateObject')],
    panels=cmds.getPanel(type='modelPanel'), cameras=cmds.ls(type='camera'), roots=cmds.ls(assemblies=True))
(out/'inspection.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
result = dict(scene=data['scene'],modified=data['modified'],controls=len(controls),modules=data['modules'],panels=data['panels'],roots=data['roots'])
