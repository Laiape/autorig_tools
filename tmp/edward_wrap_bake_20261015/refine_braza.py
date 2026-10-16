exec(compile(open(r'C:/proyectos/auto-rig/tmp/edward_wrap_bake_20261015/fit_wraps.py').read().split('for w,p in plan')[0],'fit_setup','exec'))
records=json.loads((WORK/'refined_results.json').read_text());weightsfile=np.load(str(WORK/'refined_weights.npz'));arrays={k:weightsfile[k] for k in weightsfile.files}
def fast_qp(H,L,W,iters=900):
    # Warm-started projected FISTA, retaining nonnegative unit-sum weights.
    W=W.copy();Y=W.copy();factor=1.;lips=np.maximum(np.linalg.eigvalsh(H)[:,-1],1e-12)
    for it in range(iters):
        gradient=np.einsum('vjk,vk->vj',H,Y)-L
        Z=pb.project_simplex(Y-gradient/lips[:,None])
        nf=(1+np.sqrt(1+4*factor*factor))/2
        Y=Z+(factor-1)/nf*(Z-W);change=np.abs(Z-W).max();W=Z;factor=nf
        if it>300 and change<2e-8:break
    return W
for record in records:
    if record['wrap']!='brazaletes1_PRX':continue
    w=record['wrap'];p=plan['targets'][w];idx=[globalj.index(j) for j in p['joints']]
    mat=allworld[:,idx].transpose(1,0,2,3);relative=np.linalg.inv(mat[:,0])[:,None]@mat-np.eye(4)[None,None]
    sample=data[w];hom=np.column_stack((sample[0],np.ones(len(sample[0]))))
    new=[]
    for start in range(0,len(hom),128):
        h=hom[start:start+128]
        A=np.einsum('vb,kfba->vfak',h,relative[:,:nfit,:,:3],optimize=True)
        B=(sample[:nfit,start:start+128]-sample[0,start:start+128]).transpose(1,0,2)
        W=arrays[w][start:start+128].copy()
        # Reweight independent fit poses to reduce their worst deviation.
        best=W.copy();bestmax=np.linalg.norm(np.einsum('vfak,vk->vfa',A,W)-B,axis=2).max(axis=1)
        poseweights=np.ones((len(h),nfit))
        for turn in range(4):
            H=np.einsum('vfak,vfal,vf->vkl',A,A,poseweights,optimize=True)
            L=np.einsum('vfak,vfa,vf->vk',A,B,poseweights,optimize=True)
            reg=np.maximum(np.max(np.diagonal(H,axis1=1,axis2=2),axis=1)*1e-10,1e-10)
            H+=reg[:,None,None]*np.eye(len(idx))[None]
            W=fast_qp(H,L,W)
            err=np.linalg.norm(np.einsum('vfak,vk->vfa',A,W)-B,axis=2)
            maxima=err.max(axis=1);improved=maxima<bestmax
            best[improved]=W[improved];bestmax[improved]=maxima[improved]
            poseweights=.1+(err/np.maximum(maxima[:,None],1e-8))**4*10
        new.append(best)
    candidate=np.concatenate(new)
    rel=np.linalg.inv(mat[:,0])[:,None]@mat
    pred=np.einsum('vk,kfab,vb->fva',candidate,rel.transpose(0,1,3,2)[:,:,:3,:],hom,optimize=True)
    err=np.linalg.norm(pred-sample,axis=2);rms=np.sqrt((err**2).mean(axis=1))
    maximum=float(err.max());worstrms=float(rms.max())
    if maximum<record['worst_max_cm']:
        record['initial_max_cm']=record['worst_max_cm'];record.update(worst_max_cm=maximum,worst_rms_cm=worstrms,fit_max_cm=float(err[:nfit].max()),held_out_max_cm=float(err[nfit:].max()),max_influences=int((candidate>1e-8).sum(axis=1).max()),accepted_offline=bool(maximum<=.1 and worstrms<=.025),refined=True)
        arrays[w]=candidate
    (WORK/'braza_results.json').write_text(json.dumps(records,indent=2));np.savez_compressed(str(WORK/'braza_weights.npz'),**arrays)
    print('REFINE',w,record['worst_max_cm'],record['worst_rms_cm'],record['accepted_offline'],flush=True)
print('REFINE_COMPLETE',flush=True)
