"""Save Nini v005 with neutral KeepOut compensation; validate in standalone Maya.

Run via scripts/run_maya_test.py to isolate Maya's process lifecycle.
The previous v004 and the interactive working scene are never overwritten.
"""
import hashlib
import json
import math
import sys
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maya_tools.scripts.tools import dress_keepout_chains as tool

ASSETS=ROOT/'maya_tools/assets/Nini'
SOURCE=ASSETS/'scenes/Nini_dress_chains_v004.ma'
DESTINATION=ASSETS/'scenes/Nini_dress_chains_v005.ma'
REPORT=ASSETS/'review/dress_keepout/rest_compensation_v005.json'
MESHES=('c_tunic_GEO','c_embroider_GEO','c_body_GEO')
POSES={'neutral':((0,0,0),(0,0,0)), 'left_step':((0,15,18),(0,0,0)),
       'right_step':((0,0,0),(0,15,18)), 'both_up':((0,14,15),(0,14,15)),
       'spread':((14,4,0),(-14,4,0)), 'left_up':((0,14,0),(0,0,0))}

def maximum_error(a,b):
    return max(math.dist(p,q) for p,q in zip(a,b))

def skin_digest(skin,mesh):
    selection=om.MSelectionList();selection.add(skin)
    fn=oma.MFnSkinCluster(selection.getDependNode(0))
    component=om.MFnSingleIndexedComponent();obj=component.create(om.MFn.kMeshVertComponent)
    component.addElements(range(om.MFnMesh(tool.mesh_path(mesh)).numVertices))
    weights,count=fn.getWeights(tool.mesh_path(mesh),obj)
    return hashlib.sha256(repr(list(weights)).encode()).hexdigest()

if DESTINATION.exists():
    raise FileExistsError('Refusing to overwrite '+str(DESTINATION))
cmds.file(str(ASSETS/'review/loop_rigger/Nini_ManualLoops_v001.ma'),open=True,force=True)
cmds.evaluationManager(mode='off')
original={n:tool.mesh_points(n) for n in MESHES}
cmds.file(str(SOURCE),open=True,force=True)
cmds.evaluationManager(mode='off')
data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
cycles=set(cmds.cycleCheck(all=True,list=True) or [])
weights={g['skin']:skin_digest(g['skin'],g['mesh']) for g in data['garments']}
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
tool.compensate_rest_contacts(data)
cmds.setAttr(data['settings']+'.showChains',True)
neutral={n:tool.mesh_points(n) for n in MESHES}
report={'source':str(SOURCE),'scene':str(DESTINATION),
        'method':'Clamp each station contact minus neutral contact before spatial maxima; retain waist-relative rest orientations.',
        'rest_contact_stations':len(data['rest_contacts']),
        'neutral_max_error_cm':{n:maximum_error(neutral[n],original[n]) for n in MESHES},
        'poses':{},'modes':{}}
report['skin_weights_unchanged']=all(weights[g['skin']]==skin_digest(g['skin'],g['mesh']) for g in data['garments'])
snapshots={}
for mode in ('off','serial','parallel'):
    cmds.evaluationManager(mode=mode)
    snapshots[mode]={}
    for name,pose in POSES.items():
        for side,delta in zip(('L','R'),pose):
            cmds.xform(side+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[side],delta)])
        snapshots[mode][name]=tool.mesh_points('c_tunic_GEO')
        if mode=='off':
            contact=tool.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],
                                              'c_body_GEO',surface_samples=True)
            report['poses'][name]={'contact':contact,
                                  'movement_cm':maximum_error(neutral['c_tunic_GEO'],snapshots[mode][name])}
            print('POSE_CHECKED='+json.dumps({'pose':name,'minimum_cm':contact['minimum_signed_clearance_cm'],
                                             'inside':len(contact['penetrating_vertices'])}),flush=True)
    report['modes'][mode]={'dg_max_error_cm':max(maximum_error(snapshots['off'][name],snapshots[mode][name]) for name in POSES),
                           'fallback':cmds.evaluationManager(q=True,fallbackTriggered=True) if mode!='off' else False}
for side in ('L','R'):cmds.xform(side+'_ankleIk_CTL',ws=True,t=rest[side])
cmds.currentTime(1)
report['return_to_neutral_cm']=maximum_error(neutral['c_tunic_GEO'],tool.mesh_points('c_tunic_GEO'))
cmds.setAttr(data['settings']+'.collisionEnable',False)
report['neutral_toggle_error_cm']=maximum_error(neutral['c_tunic_GEO'],tool.mesh_points('c_tunic_GEO'))
cmds.setAttr(data['settings']+'.collisionEnable',True)
report['new_cycles']=sorted(set(cmds.cycleCheck(all=True,list=True) or [])-cycles)
report['hierarchy_valid']=all(cmds.listRelatives(chain[i],parent=True)[0]==chain[i-1]
                              for chain in data['chains'] for i in range(1,len(chain)))
report['passed']=(max(report['neutral_max_error_cm'].values())<.005
                  and report['skin_weights_unchanged'] and report['hierarchy_valid']
                  and not report['new_cycles'] and report['return_to_neutral_cm']<1e-5
                  and report['neutral_toggle_error_cm']<1e-5
                  and all(p['movement_cm']>1 for name,p in report['poses'].items() if name!='neutral')
                  and all(not p['contact']['penetrating_vertices'] and not p['contact']['uncertain_vertices'] for p in report['poses'].values())
                  and all(m['dg_max_error_cm']<1e-5 and not m['fallback'] for m in report['modes'].values()))
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']:raise AssertionError('Rest compensation validation failed; see '+str(REPORT))
cmds.select(data['settings'])
cmds.file(rename=str(DESTINATION));cmds.file(save=True,type='mayaAscii')
# Reload the actual saved native graph to catch persistence/evaluation issues.
cmds.file(str(DESTINATION),open=True,force=True)
report['reload_error_cm']=maximum_error(neutral['c_tunic_GEO'],tool.mesh_points('c_tunic_GEO'))
assert report['reload_error_cm']<1e-5
REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('REST_COMPENSATION_RESULT='+json.dumps({k:v for k,v in report.items() if k!='poses'}),flush=True)
