"""Inspect contact failures on the evaluated garment rather than station goals."""
import os,sys,json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import skirt_contact as skirt,dress_keepout_chains as dress
scene=ROOT/'maya_tools/assets/Nini/experiments/skirt_contact/candidate_v004.ma'
cmds.file(str(scene),open=True,force=True)
cmds.evaluationManager(mode='off');data=skirt._data()
p=cmds.xform('L_ankleIk_CTL',q=True,ws=True,t=True)
cmds.xform('L_ankleIk_CTL',ws=True,t=[p[0],p[1]+15,p[2]+18])
contact=dress.signed_mesh_clearance(data['mesh'],data['garments'][0]['region'],'c_body_GEO',penetration_tolerance=.01)
points=dress.mesh_points(data['mesh'])
print('PENETRATIONS='+json.dumps([{'id':v,'position':points[v],'alpha':data['garments'][0]['alpha'][v]} for v in contact['penetrating_vertices']]),flush=True)
for padding in (1.5,3.0):
 cmds.setAttr(data['settings']+'.contactPadding',padding)
 result=dress.signed_mesh_clearance(data['mesh'],data['garments'][0]['region'],'c_body_GEO',penetration_tolerance=.01)
 print('PADDING='+json.dumps({'padding':padding,'inside':len(result['penetrating_vertices']),'minimum':result['minimum_signed_clearance_cm']}),flush=True)
