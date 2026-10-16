"""Bounded spatial propagation trials, with fixed geometry tolerances."""
import os,sys,json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import skirt_contact as skirt,dress_keepout_chains as dress
cmds.file(str(ROOT/'maya_tools/assets/Nini/experiments/skirt_contact/candidate_v002.ma'),open=True,force=True)
cmds.evaluationManager(mode='off')
data=skirt._data();settings=data['settings']
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
for around,down in ((.8,.6),(1,1),(1,.8)):
 cmds.setAttr(settings+'.spreadAround',around);cmds.setAttr(settings+'.spreadDown',down)
 for label,pose in [('left',(0,15,18)),('right',(0,15,18)),('held',(0,9,12))]:
  for s in ('L','R'):cmds.xform(s+'_ankleIk_CTL',ws=True,t=rest[s])
  s='R' if label=='right' else 'L'
  cmds.xform(s+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[s],pose)])
  contact=dress.signed_mesh_clearance(data['mesh'],data['garments'][0]['region'],'c_body_GEO',penetration_tolerance=.01)
  stats=skirt.audit()
  print('TRIAL='+json.dumps({'around':around,'down':down,'pose':label,'inside':len(contact['penetrating_vertices']),'minimum':contact['minimum_signed_clearance_cm'],'stretch':stats['max_stretch_ratio']}),flush=True)
