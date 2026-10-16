import sys,json,math
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
root=Path('C:/proyectos/auto-rig/autorig_tools')
sys.path.insert(0,str(root))
from maya_tools.scripts.tools import dress_keepout_chains as tool
directory=root/'maya_tools/assets/Nini'
cmds.file(str(directory/'review/loop_rigger/Nini_ManualLoops_v001.ma'),open=True,force=True)
original={n:tool.mesh_points(n) for n in ('c_tunic_GEO','c_embroider_GEO','c_body_GEO')}
cmds.file(str(directory/'scenes/Nini_dress_chains_v004.ma'),open=True,force=True)
cmds.evaluationManager(mode='off')
data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
result={'original_settings':{a:cmds.getAttr(data['settings']+'.'+a) for a in ('collisionEnable','collisionMargin')}}
tool.compensate_rest_contacts(data)
def error(a,b): return max(math.dist(p,q) for p,q in zip(a,b))
result['neutral_error_cm']={n:error(original[n],tool.mesh_points(n)) for n in original}
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
poses=[((0,0,0),(0,0,0)),((0,15,18),(0,0,0)),((0,0,0),(0,15,18)),((0,14,15),(0,14,15)),((14,4,0),(-14,4,0))]
result['poses']=[]
for i,pose in enumerate(poses):
    for s,delta in zip(('L','R'),pose): cmds.xform(s+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[s],delta)])
    contact=tool.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],'c_body_GEO',surface_samples=True)
    result['poses'].append({'pose':i,'contact':contact,'max_tunic_movement_cm':error(original['c_tunic_GEO'],tool.mesh_points('c_tunic_GEO'))})
    print('POSE='+json.dumps(result['poses'][-1]),flush=True)
Path('C:/proyectos/auto-rig/tmp/nini_rest_compensation_trial.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('RESULT='+json.dumps(result),flush=True)
