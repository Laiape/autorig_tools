import sys,json
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
sys.path[:]=[p for p in sys.path if 'proyectos/auto-rig' not in p.replace('\\','/').lower() and p]
scene='C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/Nini/scenes/Nini_dress_chains_v005.ma'
cmds.file(scene,open=True,force=True)
def points():
    sl=om.MSelectionList();sl.add('c_tunic_GEO');path=sl.getDagPath(0);path.extendToShape()
    return [tuple(p)[:3] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]
neutral=points();ctl='L_ankleIk_CTL';rest=cmds.xform(ctl,q=True,ws=True,t=True)
cmds.xform(ctl,ws=True,t=[rest[0],rest[1]+15,rest[2]+18])
cmds.evaluationManager(mode='off');dg=points()
cmds.evaluationManager(mode='parallel');parallel=points()
result={'scene':scene,'project_modules':[n for n in sys.modules if n.startswith(('maya_tools','autorig_tools'))],
        'unknown_nodes':cmds.ls(type='unknown') or [],
        'moved_vertices':sum(max(abs(a-b) for a,b in zip(p,q))>1e-4 for p,q in zip(neutral,parallel)),
        'evaluation_error_cm':max(abs(a-b) for p,q in zip(dg,parallel) for a,b in zip(p,q))}
result['passed']=not result['project_modules'] and not result['unknown_nodes'] and result['moved_vertices']>0 and result['evaluation_error_cm']<1e-5
Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/Nini/review/dress_keepout/portability_v005.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PORTABILITY='+json.dumps(result),flush=True)
assert result['passed']
