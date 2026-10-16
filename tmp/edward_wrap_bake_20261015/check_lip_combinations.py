validation=[]
with bifrost_wrinkles.primary_inputs_for_skin_export():
    for mesh,b,sk in [('cabeza_high','cabeza_high_poseCorrectives_BLS','C_mouth_local_SKC'),('cabeza_low','cabeza_low_poseCorrectives_BLS','skinCluster41')]:
        lip_pose({});reference=meshpoints(mesh)
        old=np.load(str(WORK/(mesh+'_before_lip_fix.npz')));mapping=old['mapping'];valid=old['valid']
        fn,path,comp,w,names=meshweights(sk)
        cols=[i for i,n in enumerate(names) if 'lip' in n.lower()]
        ids=np.flatnonzero((w[:,cols].sum(axis=1)>.025)&valid)
        rows=[]
        for jaw in (0,7.5,15,22.5,30):
            for label,x,y in [('neutral',0,0),('wide',5,0),('narrow',-2,0),('smile',0,3),('frown',0,-4),('half_smile_wide',2.5,1.5)]:
                pose={'C_jaw_CTL.rotateX':jaw}
                for side in ('L','R'):
                    pose[side+'_lipCorner_CTL.translateX']=x;pose[side+'_lipCorner_CTL.translateY']=y
                lip_pose(pose)
                displacement=meshpoints(mesh)-reference
                e=np.linalg.norm(displacement-reflected_field(displacement,mapping),axis=1)[ids]
                rows.append({'jaw':jaw,'gesture':label,'max_cm':float(e.max()),'rms_cm':float(np.sqrt((e**2).mean()))})
        lip_pose({})
        validation.append({'mesh':mesh,'cases':rows,'worst_max_cm':max(r['max_cm'] for r in rows),'worst_rms_cm':max(r['rms_cm'] for r in rows)})
result=validation
(WORK/'lip_combination_validation.json').write_text(json.dumps(result,indent=2))
result=[{k:v for k,v in r.items() if k!='cases'} for r in validation]
