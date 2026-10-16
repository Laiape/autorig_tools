import json,hashlib,numpy as np
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools import bifrost_wrinkles
from maya_tools.scripts.tools.skin_manager_api import SkinManager
ROOT=Path(r'C:/proyectos/auto-rig');WORK=ROOT/'tmp/edward_jaw_inner_20261015/latest'
asset=ROOT/'maya_tools/assets/Edward'
outskc=asset/'skin_clusters/Edward_v070.skc';outscene=asset/'scenes/Edward_working_v004.mb';reportpath=asset/'validation/Edward_v070_jaw_inner_lips.json'
if any(p.exists() for p in (outskc,outscene,reportpath)):raise RuntimeError('Output version already exists')
pose=json.loads((WORK/'original_pose.json').read_text());manifest=json.loads((WORK/'neutral_manifest.json').read_text())
source=json.loads((asset/'skin_clusters/Edward_v069.skc').read_text())
manager=SkinManager.__new__(SkinManager);manager.tolerance=1e-5;manager.k_skin_attrs=['skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution']
try:
    for p in pose:cmds.setAttr(p,0)
    cmds.select(clear=True);manager.export_skins(str(WORK/'snapshot_export.skc'))
    snapshot=json.loads((WORK/'snapshot_export.skc').read_text())
    # Preserve the exact serialized weights and existing validation of the three
    # earlier bakes, including the precision accepted for brazaletes1.
    originals={e['name']:e for k,v in source.items() if not k.startswith('__') for e in v if '_wrapBake_SKC' in e['name']}
    changed={rec['skin'] for rec in manifest}
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for mesh,entries in snapshot.items():
            if mesh.startswith('__'):continue
            for i,entry in enumerate(entries):
                if entry['name'] in originals:entries[i]=originals[entry['name']];continue
                if entry['name'] not in changed:continue
                sl=om.MSelectionList();sl.add(entry['name']);fn=oma.MFnSkinCluster(sl.getDependNode(0));sl=om.MSelectionList();sl.add(mesh);path=sl.getDagPath(0)
                if path.node().hasFn(om.MFn.kTransform):path.extendToShape()
                cf=om.MFnSingleIndexedComponent();co=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(entry['vertex_count']);raw,n=fn.getWeights(path,co);w=np.asarray(raw).reshape(-1,n).copy();names=[p.partialPathName() for p in fn.influenceObjects()]
                entry['sparse_weights']={}
                for j,name in enumerate(names):
                    ids=np.flatnonzero(w[:,j]>1e-8)
                    if len(ids):entry['sparse_weights'][name]={'ix':ids.tolist(),'vw':np.round(w[ids,j],8).tolist()}
    oldnodes={n['name']:n for n in source['__scene_deformers__']['nodes']};newnodes={n['name']:n for n in snapshot['__scene_deformers__']['nodes']}
    sculpt_checks=[]
    for b in ['cabeza_high_poseCorrectives_BLS','cabeza_low_poseCorrectives_BLS']:
        for attr,value in oldnodes[b]['attributes'].items():
            if attr.endswith('.inputPointsTarget') or attr.endswith('.inputComponentsTarget'):
                if newnodes[b]['attributes'].get(attr,{}).get('value')!=value['value']:raise RuntimeError('Sculpt arrays changed: '+b+'.'+attr)
        sculpt_checks.append({'blendshape':b,'all_original_sculpt_arrays_preserved':True})
    for key in ['bake_validation','lip_symmetry_validation']:
        if key in source['__scene_deformers__']:snapshot['__scene_deformers__'][key]=source['__scene_deformers__'][key]
    validation=json.loads((WORK/'adjustment_validation.json').read_text())
    snapshot['__scene_deformers__']['jaw_inner_lip_adjustment']={'source_version':'Edward_v069.skc','scope':'Cavity-facing inner lip band. Smooth jaw contribution and transfer its weight to the original lip influences; fade jaw corrective masks in the same region.','weight_plan':json.loads((WORK/'weight_plan_summary.json').read_text()),'validation':validation,'original_sculpts':sculpt_checks}
    with outskc.open('x',encoding='utf-8') as stream:json.dump(snapshot,stream,separators=(',',':'),allow_nan=False)
finally:
    for p,v in pose.items():cmds.setAttr(p,v)
cmds.select(clear=True);cmds.file(rename=str(outscene));cmds.file(save=True,type='mayaBinary',force=True)
report={'scene':str(outscene),'skc':str(outskc),'source_scene':str(asset/'scenes/Edward_working_v003.mb'),'pose_restored':pose,'plan':json.loads((WORK/'weight_plan_summary.json').read_text()),'validation':validation,'original_sculpt_checks':sculpt_checks,'preserved_bake_skins':list(originals),'skc_sha256':hashlib.sha256(outskc.read_bytes()).hexdigest(),'scene_sha256':hashlib.sha256(outscene.read_bytes()).hexdigest()}
reportpath.parent.mkdir(parents=True,exist_ok=True)
with reportpath.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
result={'scene':str(outscene),'skc':str(outskc),'report':str(reportpath),'preserved_bakes':len(originals),'remaining_wraps':len(cmds.ls(type='proximityWrap') or [])}
(WORK/'output_paths.json').write_text(json.dumps(result,indent=2))
