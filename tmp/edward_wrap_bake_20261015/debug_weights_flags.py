cmds.file(str(ROOT/'autorig_tools/maya_tools/assets/Edward/scenes/Edward_working_v002.mb'),open=True,force=True,prompt=False,executeScriptNodes=False)
rr=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,b,sk in [('cabeza_high','cabeza_high_poseCorrectives_BLS','C_mouth_local_SKC'),('cabeza_low','cabeza_low_poseCorrectives_BLS','skinCluster41')]:
        cmds.setAttr(b+'.envelope',0);before=meshpoints(mesh)
        fn,path,comp,w,names=meshweights(sk)
        attrs={a:cmds.getAttr(sk+'.'+a) for a in ('maintainMaxInfluences','normalizeWeights')}
        cmds.setAttr(sk+'.maintainMaxInfluences',False);cmds.setAttr(sk+'.normalizeWeights',0)
        fn.setWeights(path,comp,om.MIntArray(range(len(names))),om.MDoubleArray(w.ravel().tolist()),False)
        after=meshpoints(mesh)
        info={'skin':sk,'error_flags_off':float(np.linalg.norm(after-before,axis=1).max()),'finite':bool(np.isfinite(after).all())}
        for a,v in attrs.items():cmds.setAttr(sk+'.'+a,v)
        info['error_flags_restored']=float(np.linalg.norm(meshpoints(mesh)-before,axis=1).max())
        cmds.setAttr(b+'.envelope',1);rr.append(info)
result=rr
