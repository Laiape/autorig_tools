import json
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.OpenMaya as om1
OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
base=json.loads((OUT/'baseline.json').read_text())
om1.MFileIO.setCurrentFile(base['scene'])
rows=[]
for n in ('C_eyeMain_CTL','L_eye_CTL','C_head_CTL','L_ear01_CTL','C_mainMouth_CTL'):
    s=cmds.listRelatives(n,s=True,f=True)[0]
    sl=om.MSelectionList();sl.add(s);fn=om.MFnNurbsCurve(sl.getDagPath(0))
    rows.append(dict(name=n,form=fn.form,degree=fn.degree,knots=list(fn.knots()),
        world=[list(p) for p in fn.cvPositions(om.MSpace.kWorld)],
        local=cmds.xform(s+'.cv[*]',q=True,os=True,t=True)))
result=dict(scene=cmds.file(q=True,sn=True),type=cmds.file(q=True,type=True),curves=rows)
