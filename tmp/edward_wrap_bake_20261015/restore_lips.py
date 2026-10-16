for p in lip_channels:cmds.setAttr(p,0)
restore_report=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,b in [('cabeza_high','cabeza_high_poseCorrectives_BLS'),('cabeza_low','cabeza_low_poseCorrectives_BLS')]:
        old=np.load(str(WORK/(mesh+'_before_lip_fix.npz')))
        cmds.setAttr(b+'.envelope',0)
        now=meshpoints(mesh)
        err=np.linalg.norm(now-old['rest'],axis=1)
        info={'mesh':mesh,'neutral_change_cm':float(err.max()),'neutral_change_count':int((err>.001).sum())}
        sk='C_mouth_local_SKC' if mesh=='cabeza_high' else 'skinCluster41'
        fn,path,comp,w,names=meshweights(sk)
        mapping=old['mapping'];mirrorcols=np.array([names.index(('R_'+n[2:]) if n.startswith('L_') else ('L_'+n[2:]) if n.startswith('R_') else n) for n in names])
        info['stored_map_weight_asym']=float(np.abs(w-w[mapping][:,mirrorcols])[old['valid']].max())
        mats=[]
        for j,p in enumerate(fn.influenceObjects()):
            logical=fn.indexForInfluenceObject(p)
            bp=np.asarray(cmds.getAttr(sk+'.bindPreMatrix[%d]'%logical)).reshape(4,4)
            matrix=np.asarray(cmds.getAttr(sk+'.matrix[%d]'%logical)).reshape(4,4)
            mats.append({'name':names[j],'neutral_offset':float(np.max(np.abs(bp@matrix-np.eye(4))))})
        info['neutral_matrices']=sorted(mats,key=lambda m:m['neutral_offset'],reverse=True)[:10]
        saved=np.load(str(WORK/(sk+'_backup.npz')))
        fn.setWeights(path,comp,om.MIntArray(range(len(names))),om.MDoubleArray(saved['weights'].ravel().tolist()),False)
        fn.setBlendWeights(path,comp,om.MDoubleArray(saved['blend'].tolist()))
        backup=json.loads((WORK/(mesh+'_target_backup.json')).read_text())
        for i,v in backup['targets'].items():
            p=b+'.inputTarget[0].inputTargetGroup[%s].inputTargetItem[6000]'%i
            cmds.setAttr(p+'.inputPointsTarget',len(v['points']),*v['points'],type='pointArray')
            cmds.setAttr(p+'.inputComponentsTarget',len(v['components']),*v['components'],type='componentList')
        info['restore_error_cm']=float(np.linalg.norm(meshpoints(mesh)-old['rest'],axis=1).max())
        cmds.setAttr(b+'.envelope',1)
        restore_report.append(info)
result=restore_report
