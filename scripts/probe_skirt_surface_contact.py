"""Test a native final-surface projection independently from station solving."""
import os,sys,json,math
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import skirt_contact as skirt,dress_keepout_chains as dress
cmds.file(str(ROOT/'maya_tools/assets/Nini/experiments/skirt_contact/candidate_v004.ma'),open=True,force=True)
cmds.evaluationManager(mode='off');data=skirt._data()
before=dress.mesh_points(data['mesh'])
vertices=data['garments'][0]['region']
node=cmds.deformer([data['mesh']+'.vtx[{}]'.format(v) for v in vertices],type='shrinkWrap',name='SkirtSurfaceTest')[0]
target=cmds.listRelatives('c_body_GEO',shapes=True,noIntermediate=True,fullPath=True)[0]
cmds.connectAttr(target+'.worldMesh[0]',node+'.targetGeom')
cmds.setAttr(node+'.projection',3)
cmds.setAttr(node+'.reverse',True)
cmds.setAttr(node+'.bidirectional',False)
cmds.setAttr(node+'.closestIfNoIntersection',False)
cmds.setAttr(node+'.offset',.1)
cmds.setAttr(node+'.shapePreservationEnable',False)
print('SURFACE_NEUTRAL_ERROR='+str(max(math.dist(a,b) for a,b in zip(before,dress.mesh_points(data['mesh'])))),flush=True)
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
for name,pose in {'left':((0,15,18),(0,0,0)),'right':((0,0,0),(0,15,18)),'both':((0,14,15),(0,14,15)),'held':((0,9,12),(0,0,0))}.items():
 for s,delta in zip(('L','R'),pose):cmds.xform(s+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[s],delta)])
 stats=dress.signed_mesh_clearance(data['mesh'],vertices,'c_body_GEO',surface_samples=True,penetration_tolerance=.01)
 print('SURFACE_POSE='+json.dumps({'name':name,'inside':len(stats['penetrating_vertices']),'minimum':stats['minimum_signed_clearance_cm']}),flush=True)
