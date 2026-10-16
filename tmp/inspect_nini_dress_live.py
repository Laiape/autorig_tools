import json
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om

def points(name):
    selection=om.MSelectionList(); selection.add(name)
    path=selection.getDagPath(0); path.extendToShape()
    return [list(p)[:3] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]

result={'scene':cmds.file(q=True,sceneName=True),'frame':cmds.currentTime(q=True),
        'settings':{a:cmds.getAttr('C_dressSettings_CTL.'+a) for a in cmds.listAttr('C_dressSettings_CTL',userDefined=True) or []},
        'controls':{n:cmds.getAttr(n+'.translate')[0] for n in ('L_ankleIk_CTL','R_ankleIk_CTL')},
        'points':{n:points(n) for n in ('c_tunic_GEO','c_embroider_GEO','c_body_GEO')}}
Path('C:/proyectos/auto-rig/tmp/nini_dress_live.json').write_text(json.dumps(result),encoding='utf-8')
result={k:v for k,v in result.items() if k!='points'}
