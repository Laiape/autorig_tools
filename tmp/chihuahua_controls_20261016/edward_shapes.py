import json
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
assert cmds.objExists('Edward')
data={}
for n in ('C_head_CTL','L_eyeDirect_CTL','R_eyeDirect_CTL'):
    ss=[]
    for s in cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []:
        sl=om.MSelectionList();sl.add(s);fn=om.MFnNurbsCurve(sl.getDagPath(0))
        ss.append(dict(cvs=[list(p)[:3] for p in fn.cvPositions(om.MSpace.kWorld)],degree=fn.degree,form=fn.form,knots=list(fn.knots())))
    data[n]=ss
Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016/edward_world_shapes.json').write_text(json.dumps(data,indent=2))
result=dict(scene=cmds.file(q=True,sn=True),shapes={k:len(v) for k,v in data.items()})
