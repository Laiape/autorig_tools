import time
lipfix_start=time.time()
lip_channels=['C_jaw_CTL.rotateX']+[s+'_lipCorner_CTL.translate'+a for s in ('L','R') for a in ('X','Y')]
lip_saved={p:0.0 for p in lip_channels}
def lip_pose(pose):
    for p in lip_channels:cmds.setAttr(p,pose.get(p,0))
def reflected_field(field,mapping):
    out=field[mapping].copy();out[:,0]*=-1;return out
def make_pairs(points):
    reflected=points.copy();reflected[:,0]*=-1
    indices=[];distance=[]
    for start in range(0,len(points),128):
        pp=reflected[start:start+128]
        d=np.sum((pp[:,None,:]-points[None,:,:])**2,axis=2)
        ii=d.argmin(axis=1);indices.extend(ii);distance.extend(np.sqrt(d[np.arange(len(ii)),ii]))
    return np.asarray(indices),np.asarray(distance)
fix_reports=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,bshape in [('cabeza_high','cabeza_high_poseCorrectives_BLS'),('cabeza_low','cabeza_low_poseCorrectives_BLS')]:
        lip_pose({})
        cmds.setAttr(bshape+'.envelope',0);rest=meshpoints(mesh);cmds.setAttr(bshape+'.envelope',1)
        mapping,matchdist=make_pairs(rest)
        valid=(mapping[mapping]==np.arange(len(rest)))&(matchdist<.03)
        targets=dict(posebs.targets(bshape));oldend={};poses={};backups={}
        for idx,alias in targets.items():
            rec=posebs.pose_record(bshape,idx)
            ctl=posebs.linked(rec,'controller')
            channels=json.loads(cmds.getAttr(rec+'.channels'))
            cp={ctl+'.'+c['channel']:c['pose'] for c in channels}
            poses[idx]=cp;lip_pose(cp)
            # Isolate the target while retaining its exact captured rig pose.
            with posebs._temporary_values({bshape+'.weight[%d]'%i:float(i==idx) for i in targets}):
                oldend[idx]=meshpoints(mesh)
            path=bshape+'.inputTarget[0].inputTargetGroup[%d].inputTargetItem[6000]'%idx
            backups[idx]={'points':cmds.getAttr(path+'.inputPointsTarget') or [],'components':cmds.getAttr(path+'.inputComponentsTarget') or []}
        lip_pose({})
        np.savez_compressed(str(WORK/(mesh+'_before_lip_fix.npz')),rest=rest,mapping=mapping,valid=valid,**{'target_'+str(i):a for i,a in oldend.items()})
        (WORK/(mesh+'_target_backup.json')).write_text(json.dumps({'targets':backups,'poses':poses,'aliases':targets},default=str))
        skin_reports=[]
        for sk in dict.fromkeys(cmds.ls(cmds.listHistory(mesh),type='skinCluster') or []):
            geos=[g for g in cmds.deformer(sk,q=True,g=True) or [] if cmds.nodeType(g)=='mesh']
            if not geos:continue
            fn,path,component,weights,names=meshweights(sk)
            if len(weights)!=len(rest) or not any('lip' in n.lower() for n in names):continue
            nameix={n:i for i,n in enumerate(names)}
            mirrorcols=np.asarray([nameix.get(('R_'+n[2:]) if n.startswith('L_') else ('L_'+n[2:]) if n.startswith('R_') else n,-1) for n in names])
            if (mirrorcols<0).any():raise RuntimeError('Missing mirrored skin influence '+sk)
            before=np.abs(weights-weights[mapping][:,mirrorcols])
            corrected=weights.copy();corrected[valid]=.5*(weights[valid]+weights[mapping[valid]][:,mirrorcols])
            corrected/=corrected.sum(axis=1)[:,None]
            np.savez_compressed(str(WORK/(sk+'_backup.npz')),weights=weights,blend=np.asarray(fn.getBlendWeights(path,component)).copy())
            actual_max=int((corrected>1e-8).sum(axis=1).max())
            # Preserve the authored maximum; report the actual support instead of pruning.
            old_flags={a:cmds.getAttr(sk+'.'+a) for a in ('maintainMaxInfluences','normalizeWeights')}
            cmds.setAttr(sk+'.maintainMaxInfluences',False);cmds.setAttr(sk+'.normalizeWeights',0)
            fn.setWeights(path,component,om.MIntArray(range(len(names))),om.MDoubleArray(corrected.ravel().tolist()),False)
            blend=np.asarray(fn.getBlendWeights(path,component)).copy();blend[valid]=.5*(blend[valid]+blend[mapping[valid]])
            fn.setBlendWeights(path,component,om.MDoubleArray(blend.tolist()))
            for a,v in old_flags.items():cmds.setAttr(sk+'.'+a,v)
            got=np.asarray(fn.getWeights(path,component)[0]).reshape(corrected.shape)
            if np.max(np.abs(got-corrected))>1e-8:raise RuntimeError('Skin write changed weights '+sk)
            skin_reports.append({'skin':sk,'changed_vertices':int((np.abs(weights-corrected).max(axis=1)>1e-8).sum()),'weight_asym_before':float(before[valid].max()),'weight_asym_after':float(np.abs(got-got[mapping][:,mirrorcols])[valid].max()),'actual_max_influences':actual_max})
        endpoints=[]
        # Rebase every existing sculpt on the corrected skin. Average counterpart
        # endpoint displacements, keeping both original expressions equally.
        for idx,alias in targets.items():
            partner_alias=('R_'+alias[2:]) if alias.startswith('L_') else ('L_'+alias[2:]) if alias.startswith('R_') else alias
            partner=next((i for i,a in targets.items() if a==partner_alias),idx)
            displacement=oldend[idx]-rest
            desired=oldend[idx].copy()
            desired[valid]=rest[valid]+.5*(displacement[valid]+reflected_field(oldend[partner]-rest,mapping)[valid])
            lip_pose(poses[idx])
            with posebs._temporary_values({bshape+'.weight[%d]'%i:float(i==idx) for i in targets}):
                current=meshpoints(mesh)
                delta=desired-current
                ids=np.flatnonzero(np.linalg.norm(delta,axis=1)>2e-6)
                cmds.sculptTarget(bshape,edit=True,target=idx)
                try:
                    for v in ids:
                        d=delta[v];cmds.move(float(d[0]),float(d[1]),float(d[2]),mesh+'.vtx[%d]'%v,relative=True,worldSpace=True)
                finally:cmds.sculptTarget(bshape,edit=True,target=-1)
                after=meshpoints(mesh)
                error=float(np.linalg.norm(after-desired,axis=1).max())
                if error>2e-4:raise RuntimeError('Endpoint rebase failed '+alias+' '+str(error))
            endpoints.append({'index':idx,'alias':alias,'changed_vertices':len(ids),'endpoint_error_cm':error})
            (WORK/'lip_fix_progress.json').write_text(json.dumps({'mesh':mesh,'target':alias,'completed':len(endpoints),'total':len(targets),'seconds':time.time()-lipfix_start}))
            print('LIP_FIX',mesh,alias,'vertices',len(ids),'error',error,flush=True)
        lip_pose({})
        fix_reports.append({'mesh':mesh,'valid_mirror_vertices':int(valid.sum()),'unmatched_vertices':int((~valid).sum()),'skins':skin_reports,'targets':endpoints})
    lip_pose(lip_saved)
result={'reports':fix_reports,'seconds':time.time()-lipfix_start}
(WORK/'lip_fix_results.json').write_text(json.dumps(result,indent=2))
