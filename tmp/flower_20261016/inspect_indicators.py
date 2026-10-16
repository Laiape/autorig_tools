import json
from pathlib import Path
from maya import cmds
from maya_tools.scripts.utils import module_nurbs
def detail(node):
    path=cmds.ls(node,long=True)[0];anc=[];current=path
    while current:
        anc.append({'node':current,'visibility':cmds.getAttr(current+'.visibility') if cmds.objExists(current+'.visibility') else None})
        current=current.rsplit('|',1)[0] if '|' in current[1:] else ''
    return {'node':path,'ancestors':anc,'shapes':cmds.listRelatives(path,shapes=True,fullPath=True)}
result={'scene':cmds.file(query=True,sceneName=True),'modified':cmds.file(query=True,modified=True),
        'runtime':module_nurbs.__file__,
        'indicators':[detail(n) for pattern in ('*Pv_CRV','*eye*CRV','*Eye*CRV') for n in cmds.ls(pattern,type='transform',long=True) or []],
        'curve_controls':[n for n in cmds.ls('*eye*CTL','*Pv_CTL',type='transform')],
        'modules_visibility':cmds.getAttr('modules_GRP.visibility') if cmds.objExists('modules_GRP') else None}
Path('C:/proyectos/auto-rig/tmp/indicator_inspection.json').write_text(json.dumps(result,indent=2))
