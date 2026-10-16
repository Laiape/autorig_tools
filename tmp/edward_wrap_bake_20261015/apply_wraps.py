import time
operation_start=time.time()
bakeplan=json.loads((WORK/'wrap_sample_plan.json').read_text())
bakeresults=json.loads((WORK/'refined_results.json').read_text())
bakeweights=np.load(str(WORK/'refined_weights.npz'))
expected=np.load(str(WORK/'wrap_samples.npz'))
def bake_pose(channels):
    for p in bakeplan['original_pose']:cmds.setAttr(p,channels.get(p,0))
def set_skin_weights(skin,shape,weights,joints):
    sel=om.MSelectionList();sel.add(skin);fn=oma.MFnSkinCluster(sel.getDependNode(0))
    path=dag(shape);cf=om.MFnSingleIndexedComponent();comp=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(len(weights))
    cols=[joints.index(inf.fullPathName()) for inf in fn.influenceObjects()]
    flags={a:cmds.getAttr(skin+'.'+a) for a in ('normalizeWeights','maintainMaxInfluences')}
    cmds.setAttr(skin+'.normalizeWeights',0);cmds.setAttr(skin+'.maintainMaxInfluences',False)
    # Match the SKC's five-decimal weight precision before accepting the bake.
    quantized=np.round(weights[:,cols],5);quantized[quantized<=1e-5]=0
    quantized/=quantized.sum(axis=1)[:,None]
    quantized=np.round(quantized,5)
    fn.setWeights(path,comp,om.MIntArray(range(len(cols))),om.MDoubleArray(quantized.ravel().tolist()),False)
    for a,v in flags.items():cmds.setAttr(skin+'.'+a,v)
    return quantized
def compare_target(shape,w):
    rows=[]
    for i,case in enumerate(bakeplan['fit']+bakeplan['held_out']):
        bake_pose(case['channels'])
        error=np.linalg.norm(pb.points(shape)-expected[w][i],axis=1)
        rows.append({'pose':case['name'],'set':'fit' if i<len(bakeplan['fit']) else 'held_out','rms_cm':float(np.sqrt((error**2).mean())),'max_cm':float(error.max())})
    return rows
def summarize(rows):
    return {'worst_max_cm':max(r['max_cm'] for r in rows),'worst_rms_cm':max(r['rms_cm'] for r in rows),'held_out_max_cm':max(r['max_cm'] for r in rows if r['set']=='held_out')}
applied=[]
cmds.undoInfo(state=True)
for p in bakeplan['original_switch']:cmds.setAttr(p,1)
try:
    for rec in bakeresults:
        if not rec['accepted_offline']:continue
        w=rec['wrap'];shape=rec['shape'];transform=cmds.listRelatives(shape,parent=True,fullPath=True)[0]
        joints=rec['joints'];weights=bakeweights[w]
        bake_pose({})
        duplicate,sk=pb.bind_copy(shape,joints,weights,max(8,rec['max_influences']))
        set_skin_weights(sk,pw.mesh_shape(duplicate),weights,joints)
        rows=compare_target(pw.mesh_shape(duplicate),w);metrics=summarize(rows)
        bake_pose({});cmds.delete(duplicate)
        if metrics['worst_max_cm']>.1 or metrics['worst_rms_cm']>.025:
            applied.append({'wrap':w,'accepted':False,'reason':'Native Maya quantized candidate exceeded threshold',**metrics});continue
        cmds.undoInfo(openChunk=True,chunkName='EdwardWrapBake_'+w)
        problem=None
        try:
            cmds.delete(w)
            newshape=pw.mesh_shape(transform)
            skin=cmds.skinCluster(joints,transform,toSelectedBones=True,skinMethod=0,maximumInfluences=max(8,rec['max_influences']),normalizeWeights=1,name=transform.rsplit('|',1)[-1]+'_wrapBake_SKC')[0]
            set_skin_weights(skin,newshape,weights,joints)
            rows=compare_target(newshape,w);metrics=summarize(rows)
            if metrics['worst_max_cm']>.1 or metrics['worst_rms_cm']>.025:raise RuntimeError('Original replacement exceeded threshold '+str(metrics))
        except Exception as exc:problem=str(exc)
        finally:
            bake_pose({});cmds.undoInfo(closeChunk=True)
        if problem:
            cmds.undo();applied.append({'wrap':w,'accepted':False,'reason':problem})
        else:
            applied.append({'wrap':w,'accepted':True,'shape':newshape,'skin':skin,**metrics,'validation':rows})
        (WORK/'wrap_apply_progress.json').write_text(json.dumps({'completed':len(applied),'last':{k:v for k,v in applied[-1].items() if k!='validation'},'seconds':time.time()-operation_start}))
finally:
    bake_pose(bakeplan['original_pose'])
    for p,v in bakeplan['original_switch'].items():cmds.setAttr(p,v)
    cmds.select(clear=True)
result=applied
(WORK/'wrap_applied_results.json').write_text(json.dumps(applied,indent=2))
result=[{k:v for k,v in r.items() if k!='validation'} for r in applied]
