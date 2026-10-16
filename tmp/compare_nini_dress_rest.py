import json, math
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om

root=Path('C:/proyectos/auto-rig')
assets=root/'autorig_tools/maya_tools/assets/Nini'
live=json.loads((root/'tmp/nini_dress_live.json').read_text(encoding='utf-8'))
def points(name):
    selection=om.MSelectionList(); selection.add(name)
    path=selection.getDagPath(0); path.extendToShape()
    return [tuple(p)[:3] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]
def diff(a,b):
    distances=[math.dist(p,q) for p,q in zip(a,b)]
    moved=[i for i,d in enumerate(distances) if d>1e-5]
    return {'vertices':len(a),'moved_vertices':len(moved),'max_cm':max(distances),'rms_cm':math.sqrt(sum(d*d for d in distances)/len(distances)),
            'max_vertex':distances.index(max(distances))}
cmds.file(str(assets/'review/loop_rigger/Nini_ManualLoops_v001.ma'),open=True,force=True)
cmds.currentTime(live['frame'])
original={n:points(n) for n in live['points']}
result={'live':{k:v for k,v in live.items() if k!='points'},'live_vs_original':{n:diff(live['points'][n],original[n]) for n in original}}
print('ORIGINAL_COMPARED='+json.dumps(result),flush=True)
cmds.file(live['scene'],open=True,force=True)
cmds.evaluationManager(mode='off')
cmds.currentTime(live['frame'])
enabled={n:points(n) for n in original}
result['saved_vs_live']={n:diff(enabled[n],live['points'][n]) for n in original}
data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
cmds.setAttr('C_dressSettings_CTL.collisionEnable',False)
cmds.dgdirty(allPlugs=True)
disabled={n:points(n) for n in original}
result['collision_displacement']={n:diff(enabled[n],disabled[n]) for n in original}
result['collision_disabled_vs_original']={n:diff(disabled[n],original[n]) for n in original}
for garment in data['garments']:
    n=garment['mesh']; upper=[i for i,a in enumerate(garment['alpha']) if a==0]
    result.setdefault('upper_vs_original',{})[n]=diff([enabled[n][i] for i in upper],[original[n][i] for i in upper])
    bottom=[i for i,a in enumerate(garment['alpha']) if a>0]
    result.setdefault('lower_vs_original',{})[n]=diff([enabled[n][i] for i in bottom],[original[n][i] for i in bottom])
(root/'tmp/nini_dress_rest_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('REST_COMPARISON='+json.dumps(result),flush=True)
