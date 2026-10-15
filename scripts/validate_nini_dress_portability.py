"""Load and pose the saved native dress rig without importing project modules."""
import os,sys,json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/'maya_tools/assets/Nini/experiments/dress_keepout'
sys.path[:]=[p for p in sys.path if 'proyectos/auto-rig' not in p.replace('\\','/').lower() and p]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
scene=directory/'Nini_dress_chains_v004.ma'
cmds.file(str(scene),open=True,force=True)
data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
selection=om.MSelectionList();selection.add('c_tunic_GEO')
path=selection.getDagPath(0);path.extendToShape()
def points(): return [tuple(p)[:3] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]
before=points()
ctl='L_ankleIk_CTL';position=cmds.xform(ctl,q=True,ws=True,t=True)
cmds.xform(ctl,ws=True,t=[position[0],position[1]+15,position[2]+18])
cmds.evaluationManager(mode='off');dg=points()
cmds.evaluationManager(mode='parallel');parallel=points()
project_modules=[name for name in sys.modules if name.startswith(('maya_tools','autorig_tools'))]
result={'scene':str(scene),'project_modules_loaded':project_modules,
        'dress_joint_count':len(data['joints']),
        'dress_vertex_count':len(dg),
        'moved_vertex_count':sum(max(abs(a-b) for a,b in zip(p,q))>1e-4 for p,q in zip(before,parallel)),
        'dg_parallel_error':max(abs(a-b) for p,q in zip(dg,parallel) for a,b in zip(p,q)),
        'unknown_nodes':cmds.ls(type='unknown') or [],
        'new_module_node_types':sorted(set(cmds.nodeType(n) for n in cmds.ls('NiniDress_*')))}
result['passed']=not project_modules and not result['unknown_nodes'] and result['dg_parallel_error']<1e-5 and result['moved_vertex_count']>0
(directory/'portability_v004.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
maya.standalone.uninitialize()
if not result['passed']: raise SystemExit(2)
