paths=json.loads((WORK/'final_paths.json').read_text())
bp=json.loads((WORK/'wrap_sample_plan.json').read_text())
applied=[r for r in json.loads((WORK/'wrap_applied_results.json').read_text()) if r['accepted']]+[r for r in json.loads((WORK/'braza_applied_results.json').read_text()) if r['accepted']]
geometry=['cabeza_high','cabeza_low','brazaletes1','polySurface61','polySurface62']
reopen_cases=[{}, {'C_jaw_CTL.rotateX':15}, {'C_jaw_CTL.rotateX':30}, {'L_lipCorner_CTL.translateX':5,'R_lipCorner_CTL.translateX':5}, {'C_jaw_CTL.rotateX':30,'L_lipCorner_CTL.translateY':3,'R_lipCorner_CTL.translateY':3}, {'C_head_CTL.rotateY':20,'C_jaw_CTL.rotateX':20}, {'C_spine03_CTL.rotateZ':25,'L_shoulderFk_CTL.rotateY':35}]
def set_case(pose):
    for p in bp['original_pose']:cmds.setAttr(p,pose.get(p,0))
def capture_cases():
    captures=[]
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for case in reopen_cases:
            set_case(case)
            captures.append({g:meshpoints(pw.mesh_shape(g)) for g in geometry})
    set_case(bp['original_pose'])
    return captures
before=capture_cases()
cmds.file(paths['scene'],open=True,force=True,prompt=False,executeScriptNodes=False)
after=capture_cases()
reopen_error={g:max(float(np.linalg.norm(a[g]-b[g],axis=1).max()) for a,b in zip(before,after)) for g in geometry}
if max(reopen_error.values())>.0002:raise RuntimeError('Scene reopen changed geometry '+str(reopen_error))
snapshot=json.loads(Path(paths['skc']).read_text())
changed={'C_mouth_local_SKC','skinCluster41'}|{r['skin'] for r in applied}
weight_errors=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for meshname,entries in snapshot.items():
        if meshname.startswith('__'):continue
        for entry in entries:
            if entry['name'] not in changed:continue
            fn,path,comp,weights,names=meshweights(entry['name']);serialized=np.zeros_like(weights)
            for name,sparse in entry['sparse_weights'].items():serialized[np.asarray(sparse['ix']),names.index(name)]=sparse['vw']
            error=float(np.max(np.abs(weights-serialized)));weight_errors.append({'skin':entry['name'],'max':error})
            if error>1e-10:raise RuntimeError('SKC differs from saved scene '+entry['name'])
wrapchecks=[]
samples=np.load(str(WORK/'wrap_samples.npz'))
for p in bp['original_switch']:cmds.setAttr(p,1)
for r in applied:
    reference=samples[r['wrap']];rows=[]
    for i,case in enumerate(bp['fit']+bp['held_out']):
        set_case(case['channels'])
        error=np.linalg.norm(pb.points(r['shape'])-reference[i],axis=1)
        rows.append({'max_cm':float(error.max()),'rms_cm':float(np.sqrt((error**2).mean()))})
    check={'wrap':r['wrap'],'skin':r['skin'],'worst_max_cm':max(m['max_cm'] for m in rows),'worst_rms_cm':max(m['rms_cm'] for m in rows),'pose_count':len(rows)}
    wrapchecks.append(check)
    if check['worst_max_cm']>.1 or check['worst_rms_cm']>.025:raise RuntimeError('Saved skin failed threshold '+str(check))
set_case(bp['original_pose'])
for p,v in bp['original_switch'].items():cmds.setAttr(p,v)
exec(compile((WORK/'check_lip_combinations.py').read_text(),'check_lip_combinations.py','exec'),globals())
post_lips=validation
result={'reopen_errors_cm':reopen_error,'serialized_weight_errors':weight_errors,'wraps':wrapchecks,'lip_combinations':[{k:v for k,v in r.items() if k!='cases'} for r in post_lips],'wrap_count':len(cmds.ls(type='proximityWrap') or [])}
if result['wrap_count']!=20:raise RuntimeError('Wrong remaining wrap count after reopen')
report=json.loads(Path(paths['report']).read_text());report['final_reopen_validation']=result;report['lip_combinations']=post_lips
Path(paths['report']).write_text(json.dumps(report,indent=2,allow_nan=False))
(WORK/'final_verification.json').write_text(json.dumps(result,indent=2))
cmds.select(clear=True)
