for p in lip_channels:cmds.setAttr(p,0)
rr=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,b,sk in [('cabeza_high','cabeza_high_poseCorrectives_BLS','C_mouth_local_SKC'),('cabeza_low','cabeza_low_poseCorrectives_BLS','skinCluster41')]:
        fn,path,comp,w,names=meshweights(sk)
        old=np.load(str(WORK/(sk+'_backup.npz')))
        prior=np.load(str(WORK/(mesh+'_before_lip_fix.npz')))
        cmds.setAttr(b+'.envelope',0)
        bp=meshpoints(mesh)
        info={'skin':sk,'weight_diff_backup':float(np.max(np.abs(w-old['weights']))),'sum_min':float(w.sum(axis=1).min()),'sum_max':float(w.sum(axis=1).max()),'support':int((w>1e-8).sum(axis=1).max()),'rest_before_diff':float(np.linalg.norm(bp-prior['rest'],axis=1).max()),'blend_backup_minmax':[float(old['blend'].min()),float(old['blend'].max())]}
        # A round trip with unchanged weights must preserve neutral geometry.
        fn.setWeights(path,comp,om.MIntArray(range(len(names))),om.MDoubleArray(w.ravel().tolist()),False)
        info['same_weight_write_rest_change']=float(np.linalg.norm(meshpoints(mesh)-bp,axis=1).max())
        cmds.setAttr(b+'.envelope',1)
        rr.append(info)
result=rr
