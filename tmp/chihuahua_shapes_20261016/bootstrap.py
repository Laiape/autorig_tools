import json, os, sys
from pathlib import Path
sys.path[:0] = ['C:/proyectos/auto-rig/autorig_tools', 'C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts']
import maya.cmds as cmds
import maya.api.OpenMaya as om
base = Path('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016')
cmds.commandPort(name='127.0.0.1:7102', sourceType='python', echoOutput=False)
def capture():
    out = {}
    for n in cmds.ls('*_CTL',type='transform') or []:
        shapes = cmds.listRelatives(n,s=True,ni=True,type='nurbsCurve',f=True) or []
        curves = []
        for s in shapes:
            sel=om.MSelectionList();sel.add(s);fn=om.MFnNurbsCurve(sel.getDagPath(0))
            curves.append({'name':s.rsplit('|',1)[-1], 'cvs':[(p.x,p.y,p.z) for p in fn.cvPositions(om.MSpace.kObject)],'world_cvs':[(p.x,p.y,p.z) for p in fn.cvPositions(om.MSpace.kWorld)]})
        out[n]={'matrix':cmds.xform(n,q=True,ws=True,m=True),'shapes':curves}
    return out
cmds.file('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua/scenes/chihuahua_controls_v002.mb',open=True,force=True,prompt=False,executeScriptNodes=False)
(base/'old_controls.json').write_text(json.dumps(capture()))
cmds.file('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua/scenes/chihuahua_oriented_v001.mb',open=True,force=True,prompt=False,executeScriptNodes=False)
(base/'oriented_controls.json').write_text(json.dumps(capture()))
(base/'ready.json').write_text(json.dumps({'pid':os.getpid(),'port':7102}))
