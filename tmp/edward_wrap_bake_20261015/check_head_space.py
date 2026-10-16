head_checks=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,b in [('cabeza_high','cabeza_high_poseCorrectives_BLS'),('cabeza_low','cabeza_low_poseCorrectives_BLS')]:
        lip_pose({'C_jaw_CTL.rotateX':30});cmds.setAttr(b+'.envelope',0);off=meshpoints(mesh);cmds.setAttr(b+'.envelope',1);on=meshpoints(mesh)
        delta=on-off;mat0=np.asarray(cmds.xform('C_headSkinning_JNT',q=True,ws=True,m=True)).reshape(4,4)
        for axis,angle in [('X',25),('Y',-20),('Z',30)]:
            plug='C_head_CTL.rotate'+axis;cmds.setAttr(plug,angle)
            cmds.setAttr(b+'.envelope',0);off=meshpoints(mesh);cmds.setAttr(b+'.envelope',1);on=meshpoints(mesh)
            mat=np.asarray(cmds.xform('C_headSkinning_JNT',q=True,ws=True,m=True)).reshape(4,4)
            prediction=delta@(np.linalg.inv(mat0)@mat)[:3,:3]
            e=np.linalg.norm(on-off-prediction,axis=1)
            head_checks.append({'mesh':mesh,'axis':axis,'angle':angle,'max_cm':float(e.max())})
            cmds.setAttr(plug,0)
lip_pose({})
result=head_checks
(WORK/'head_space_validation.json').write_text(json.dumps(result,indent=2))
