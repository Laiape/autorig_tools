import hashlib
from maya_tools.scripts.tools.skin_manager_api import SkinManager
asset=ROOT/'maya_tools/assets/Edward'
outskc=asset/'skin_clusters/Edward_v069.skc'
outscene=asset/'scenes/Edward_working_v003.mb'
outreport=asset/'validation/Edward_v069_wrap_bake_lip_validation.json'
if any(p.exists() for p in (outskc,outscene,outreport)):raise RuntimeError('Final output already exists')
lip_pose({})
bp=json.loads((WORK/'wrap_sample_plan.json').read_text())
for p,v in bp['original_pose'].items():cmds.setAttr(p,v)
for p,v in bp['original_switch'].items():cmds.setAttr(p,v)
cmds.select(clear=True)
applied=[r for r in json.loads((WORK/'wrap_applied_results.json').read_text()) if r['accepted']]
applied.extend(r for r in json.loads((WORK/'braza_applied_results.json').read_text()) if r['accepted'])
manager=SkinManager.__new__(SkinManager)
manager.k_skin_attrs=['skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution']
manager.tolerance=1e-5
staged=WORK/'final_snapshot.skc'
manager.export_skins(str(staged))
snapshot=json.loads(staged.read_text())
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for meshname,skinlist in snapshot.items():
        if meshname.startswith('__'):continue
        for entry in skinlist:
            if entry['name'] not in {r['skin'] for r in applied}:continue
            fn,path,comp,weights,names=meshweights(entry['name'])
            # The validated skin precision is stored without reducing it to the
            # general exporter's five-decimal default near the 1 mm limit.
            entry['sparse_weights']={}
            for j,name in enumerate(names):
                ids=np.flatnonzero(weights[:,j]>1e-8)
                if len(ids):entry['sparse_weights'][name]={'ix':ids.tolist(),'vw':np.round(weights[ids,j],8).tolist()}
    # Reapply changed skins from their actual serialized representation before
    # saving, so the scene and the deliverable use the same weight precision.
    changed={'C_mouth_local_SKC','skinCluster41'}|{r['skin'] for r in applied}
    serialized=[]
    for meshname,skinlist in snapshot.items():
        if meshname.startswith('__'):continue
        for entry in skinlist:
            if entry['name'] not in changed:continue
            fn,path,comp,weights,names=meshweights(entry['name'])
            reconstructed=np.zeros_like(weights)
            for name,values in entry['sparse_weights'].items():
                reconstructed[np.asarray(values['ix']),names.index(name)]=values['vw']
            flags={a:cmds.getAttr(entry['name']+'.'+a) for a in ('normalizeWeights','maintainMaxInfluences')}
            cmds.setAttr(entry['name']+'.normalizeWeights',0);cmds.setAttr(entry['name']+'.maintainMaxInfluences',False)
            fn.setWeights(path,comp,om.MIntArray(range(len(names))),om.MDoubleArray(reconstructed.ravel().tolist()),False)
            for a,v in flags.items():cmds.setAttr(entry['name']+'.'+a,v)
            serialized.append({'skin':entry['name'],'weight_precision_change':float(np.max(np.abs(reconstructed-weights)))})
remaining=cmds.ls(type='proximityWrap') or []
if len(remaining)!=20 or len(applied)!=3:raise RuntimeError('Unexpected conversion count')
deformer_names={n['name'] for n in snapshot['__scene_deformers__']['nodes']}
for r in applied:
    if r['wrap'] in deformer_names or r['skin'] not in deformer_names:raise RuntimeError('Incorrect SKC bake membership')
snapshot['__scene_deformers__']['bake_validation']={'date':'2026-10-15','source_scene':str(ROOT/'autorig_tools/maya_tools/assets/Edward/scenes/Edward_working_v002.mb'),'fit_poses':len(bp['fit']),'held_out_poses':len(bp['held_out']),'max_error_cm':.1,'max_rms_cm':.025,'records':applied,'remaining_wraps':remaining}
snapshot['__scene_deformers__']['lip_symmetry_validation']={'weight_and_sculpt_repair':json.loads((WORK/'lip_direct_results.json').read_text()),'pose_validation':json.loads((WORK/'lip_combination_validation.json').read_text()),'low_jaw_space':'head transform, preserving the jaw-open endpoint'}
with outskc.open('x',encoding='utf-8') as stream:json.dump(snapshot,stream,separators=(',',':'),allow_nan=False)
cmds.workspace(str(asset),openWorkspace=True)
try:
    import runpy
    relinker=runpy.run_path(str(ROOT/'scripts/open_edward.py'))
    relinker['relink_scene_textures'](asset)
except Exception as exc:print('Texture relink:',str(exc),flush=True)
cmds.select(clear=True)
cmds.file(rename=str(outscene));cmds.file(save=True,type='mayaBinary',force=True)
report={'source_scene':str(ROOT/'autorig_tools/maya_tools/assets/Edward/scenes/Edward_working_v002.mb'),'scene':str(outscene),'skc':str(outskc),'maya':cmds.about(version=True),'units':'cm','thresholds':{'max_cm':.1,'rms_cm':.025},'fit_poses':len(bp['fit']),'held_out_poses':len(bp['held_out']),'converted':applied,'remaining_wraps':remaining,'all_wrap_fits':json.loads((WORK/'refined_results.json').read_text()),'lip_before':json.loads((WORK/'lip_audit_before.json').read_text()),'lip_after':json.loads((WORK/'lip_audit_after.json').read_text()),'lip_combinations':json.loads((WORK/'lip_combination_validation.json').read_text()),'lip_repair':json.loads((WORK/'lip_direct_results.json').read_text()),'serialized_weights':serialized,'skc_sha256':hashlib.sha256(outskc.read_bytes()).hexdigest(),'scene_sha256':hashlib.sha256(outscene.read_bytes()).hexdigest()}
outreport.parent.mkdir(parents=True,exist_ok=True)
with outreport.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
result={'scene':str(outscene),'skc':str(outskc),'report':str(outreport),'converted':len(applied),'remaining':len(remaining),'skc_bytes':outskc.stat().st_size}
(WORK/'final_paths.json').write_text(json.dumps(result,indent=2))
