"""Inspect native multi-collision as an isolated final-surface candidate."""
import os,sys,json,math
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import skirt_contact as skirt,dress_keepout_chains as dress
cmds.file(str(ROOT/'maya_tools/assets/Nini/experiments/skirt_contact/candidate_v006.ma'),open=True,force=True)
cmds.evaluationManager(mode='off');data=skirt._data()
before={m:dress.mesh_points(m) for m in (data['mesh'],'c_body_GEO')}
node=cmds.deformer(['c_body_GEO',data['mesh']],type='cMuscleMultiCollide',name='SkirtSurfaceTest')[0]
print('MULTI_ATTRIBUTES='+json.dumps(cmds.listAttr(node)),flush=True)
print('MULTI_GEOMETRY='+json.dumps({'geometry':cmds.deformer(node,q=True,geometry=True),'indices':cmds.deformer(node,q=True,geometryIndices=True)}),flush=True)
for mesh,index in zip(cmds.deformer(node,q=True,geometry=True),cmds.deformer(node,q=True,geometryIndices=True)):
 if 'body' in mesh:
  count=om.MFnMesh(dress.mesh_path(mesh)).numVertices
  cmds.setAttr(node+'.weightList[{}].weights[0:{}]'.format(index,count-1),*([0.0]*count),size=count)
for attr in ('volumize','blurIterations','relaxStrength','smoothStrength','selfCollision'):
 if cmds.objExists(node+'.'+attr):cmds.setAttr(node+'.'+attr,0)
print('MULTI_NEUTRAL_ERROR='+json.dumps({m:max(math.dist(a,b) for a,b in zip(before[m],dress.mesh_points(m))) for m in before}),flush=True)
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
for name,pose in {'left':((0,15,18),(0,0,0)),'right':((0,0,0),(0,15,18)),'both':((0,14,15),(0,14,15)),'held':((0,9,12),(0,0,0))}.items():
 for s,delta in zip(('L','R'),pose):cmds.xform(s+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[s],delta)])
 stats=dress.signed_mesh_clearance(data['mesh'],data['garments'][0]['region'],'c_body_GEO',surface_samples=True,penetration_tolerance=.01)
 print('MULTI_POSE='+json.dumps({'name':name,'inside':len(stats['penetrating_vertices']),'minimum':stats['minimum_signed_clearance_cm']}),flush=True)
