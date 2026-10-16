exec(compile((WORK/'fix_lips.py').read_text().split('fix_reports=[]')[0],'lip_helpers','exec'),globals())
def write_delta(path,vectors):
    ids=np.flatnonzero(np.linalg.norm(vectors,axis=1)>1e-7)
    values=[(float(vectors[i,0]),float(vectors[i,1]),float(vectors[i,2]),1.) for i in ids]
    components=['vtx[%d]'%i for i in ids]
    cmds.setAttr(path+'.inputPointsTarget',len(values),*values,type='pointArray')
    cmds.setAttr(path+'.inputComponentsTarget',len(components),*components,type='componentList')
reports=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,b,sk in [('cabeza_high','cabeza_high_poseCorrectives_BLS','C_mouth_local_SKC'),('cabeza_low','cabeza_low_poseCorrectives_BLS','skinCluster41')]:
        lip_pose({})
        old=np.load(str(WORK/(mesh+'_before_lip_fix.npz')))
        rest=old['rest'];mapping=old['mapping'];valid=old['valid']
        backup=json.loads((WORK/(mesh+'_target_backup.json')).read_text())
        targets={int(i):a for i,a in backup['aliases'].items()};poses={int(i):p for i,p in backup['poses'].items()}
        fn,path,comp,W,names=meshweights(sk)
        W=np.load(str(WORK/(sk+'_backup.npz')))['weights']
        mirrorcols=np.array([names.index(('R_'+n[2:]) if n.startswith('L_') else ('L_'+n[2:]) if n.startswith('R_') else n) for n in names])
        Wnew=W.copy();Wnew[valid]=.5*(W[valid]+W[mapping[valid]][:,mirrorcols])
        flags={a:cmds.getAttr(sk+'.'+a) for a in ('maintainMaxInfluences','normalizeWeights')}
        cmds.setAttr(sk+'.maintainMaxInfluences',False);cmds.setAttr(sk+'.normalizeWeights',0)
        fn.setWeights(path,comp,om.MIntArray(range(len(names))),om.MDoubleArray(Wnew.ravel().tolist()),False)
        for a,v in flags.items():cmds.setAttr(sk+'.'+a,v)
        cmds.setAttr(b+'.envelope',0)
        neutral_error=float(np.linalg.norm(meshpoints(mesh)-rest,axis=1).max())
        if neutral_error>.01:raise RuntimeError('Neutral changed after weight update '+str(neutral_error))
        cmds.setAttr(b+'.envelope',1)
        endpoints=[]
        for idx,alias in targets.items():
            partner_alias=('R_'+alias[2:]) if alias.startswith('L_') else ('L_'+alias[2:]) if alias.startswith('R_') else alias
            partner=next((i for i,a in targets.items() if a==partner_alias),idx)
            oldend=old['target_'+str(idx)];partnerend=old['target_'+str(partner)]
            desired=oldend.copy();desired[valid]=rest[valid]+.5*((oldend-rest)[valid]+reflected_field(partnerend-rest,mapping)[valid])
            lip_pose(poses[idx])
            delta_path=b+'.inputTarget[0].inputTargetGroup[%d].inputTargetItem[6000]'%idx
            with posebs._temporary_values({b+'.weight[%d]'%i:float(i==idx) for i in targets}):
                zero=np.zeros_like(rest);write_delta(delta_path,zero);baseline=meshpoints(mesh)
                basis=[]
                for axis in range(3):
                    probe=np.zeros_like(rest);probe[:,axis]=1
                    write_delta(delta_path,probe);basis.append(meshpoints(mesh)-baseline)
                response=np.stack(basis,axis=2)
                raw=np.einsum('vij,vj->vi',np.linalg.pinv(response),desired-baseline)
                write_delta(delta_path,raw)
                error=float(np.linalg.norm(meshpoints(mesh)-desired,axis=1).max())
                if not np.isfinite(error) or error>.0002:raise RuntimeError('Direct target solve failed '+alias+' '+str(error))
            endpoints.append({'alias':alias,'index':idx,'endpoint_error_cm':error,'delta_vertices':int((np.linalg.norm(raw,axis=1)>1e-7).sum())})
            print('LIP_DIRECT',mesh,alias,error,flush=True)
        lip_pose({});cmds.setAttr(b+'.envelope',0)
        neutral_after=float(np.linalg.norm(meshpoints(mesh)-rest,axis=1).max());cmds.setAttr(b+'.envelope',1)
        if neutral_after>.01:raise RuntimeError('Sculpt edits changed neutral '+mesh+' '+str(neutral_after))
        reports.append({'mesh':mesh,'skin':sk,'neutral_error_cm':neutral_after,'changed_weight_vertices':int((np.abs(Wnew-W).max(axis=1)>1e-7).sum()),'weight_asym_after':float(np.abs(Wnew-Wnew[mapping][:,mirrorcols])[valid].max()),'targets':endpoints})
lip_pose({})
result=reports
(WORK/'lip_direct_results.json').write_text(json.dumps(result,indent=2))
