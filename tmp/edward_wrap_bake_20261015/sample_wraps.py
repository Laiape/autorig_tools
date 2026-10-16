import time
class cKDTree:
    def __init__(self,points):self.points=np.asarray(points)
    def query(self,points,k=1):
        ix=[];ds=[]
        for start in range(0,len(points),128):
            p=points[start:start+128]
            d=np.sum(p*p,axis=1)[:,None]+np.sum(self.points*self.points,axis=1)[None,:]-2*p@self.points.T
            ids=np.argpartition(d,k-1,axis=1)[:,:k]
            ix.append(ids);ds.append(np.sqrt(np.maximum(0,np.take_along_axis(d,ids,axis=1))))
        return np.concatenate(ds),np.concatenate(ix)
t0=time.time()
wrap_targets={w:pw.mesh_shape((cmds.deformer(w,q=True,g=True) or [])[0]) for w in cmds.ls(type='proximityWrap')}
# Explicit independent control poses, without adding animation curves.
axes={}
def add_axes(control,ranges):
    for a,limits in ranges.items():
        p=control+'.'+a
        if cmds.objExists(p) and cmds.getAttr(p,settable=True):axes[p]=limits
for s in ('L','R'):
    add_axes(s+'_shoulderFk_CTL',{'rotateX':(-45,55),'rotateY':(-45,70),'rotateZ':(-40,100)})
    add_axes(s+'_elbowFk_CTL',{'rotateY':(-100,100),'rotateX':(-60,60)})
    add_axes(s+'_wristFk_CTL',{'rotateX':(-45,45),'rotateY':(-25,25),'rotateZ':(-60,60)})
    add_axes(s+'_hipFk_CTL',{'rotateX':(-35,35),'rotateY':(-30,60),'rotateZ':(-45,95)})
    add_axes(s+'_kneeFk_CTL',{'rotateZ':(-120,120),'rotateX':(-15,15)})
    add_axes(s+'_ankleFk_CTL',{'rotateX':(-35,35),'rotateY':(-25,25),'rotateZ':(-45,45)})
    add_axes(s+'_ballFk_CTL',{'rotateZ':(-25,40)})
for c in ('C_spine03_CTL','C_spine07_CTL'):
    add_axes(c,{'rotateX':(-25,25),'rotateY':(-20,20),'rotateZ':(-20,35)})
for c in ('C_neck_CTL','C_head_CTL'):
    add_axes(c,{'rotateX':(-30,30),'rotateY':(-20,20),'rotateZ':(-25,25)})
add_axes('C_jaw_CTL',{'rotateX':(0,30)})
for s in ('L','R'):
    add_axes(s+'_lipCorner_CTL',{'translateX':(-2,5),'translateY':(-4,3)})
saved_pose={p:cmds.getAttr(p) for p in axes}
saved_switch={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk') for s in ('L','R') for limb in ('arm','leg')}
for p in saved_switch:cmds.setAttr(p,1)
def apply_pose(pose):
    for p in axes:cmds.setAttr(p,pose.get(p,0))
fitposes=[{'name':'neutral','channels':{}}]
validationposes=[]
for p,(lo,hi) in axes.items():
    for val in sorted(set((lo,hi))):
        if val:fitposes.append({'name':p+'_'+str(val),'channels':{p:val}})
    for factor in (.37,.73):
        val=(lo if factor==.37 else hi)*factor
        if val:validationposes.append({'name':'intermediate_'+p+'_'+str(factor),'channels':{p:val}})
rng=np.random.default_rng(15102026)
body=[p for p in axes if not any(s in p for s in ('lipCorner','jaw'))]
for i in range(36):
    chosen=rng.choice(body,size=6,replace=False)
    pose={p:float(rng.uniform(*axes[p]))*.65 for p in chosen}
    (fitposes if i<18 else validationposes).append({'name':'combination_%02d'%i,'channels':pose})
# Global motion and uniform scale are independently held out below, after bind.
plans={}
try:
    apply_pose({})
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for w,shape in wrap_targets.items():
            try: joints=pb.candidate_joints(shape)
            except Exception:
                joints=[]
                target=pb.points(shape)
                for skin in dict.fromkeys(cmds.ls(cmds.listHistory(w) or [],type='skinCluster') or []):
                    geos=[g for g in cmds.deformer(skin,q=True,g=True) or [] if cmds.nodeType(g)=='mesh']
                    if not geos:continue
                    fn,path,comp,weights,names=meshweights(skin)
                    pos=np.asarray(om.MFnMesh(path).getPoints(om.MSpace.kWorld))[:,:3]
                    _,nearest=cKDTree(pos).query(target,k=min(8,len(pos)))
                    active=np.flatnonzero(weights[np.unique(nearest)].max(axis=0)>1e-4)
                    inf=fn.influenceObjects()
                    joints.extend(inf[i].fullPathName() for i in active)
                joints=list(dict.fromkeys(joints))
            if not joints:raise RuntimeError('No joints for '+w)
            plans[w]={'shape':shape,'joints':joints,'samples':[]}
    alljoints=list(dict.fromkeys(j for p in plans.values() for j in p['joints']))
    allworld=[]
    for i,case in enumerate(fitposes+validationposes):
        apply_pose(case['channels'])
        allworld.append(np.asarray([cmds.xform(j,q=True,ws=True,m=True) for j in alljoints]).reshape(-1,4,4))
        for w,plan in plans.items():plan['samples'].append(pb.points(plan['shape']))
        if i%10==0:
            print('SAMPLE',i,'/',len(fitposes+validationposes),'seconds',round(time.time()-t0,1),flush=True)
            (WORK/'progress.json').write_text(json.dumps({'phase':'sample','pose':i,'total':len(fitposes+validationposes),'seconds':time.time()-t0}))
    allworld=np.asarray(allworld)
    arrays={'matrices':allworld}
    for w,plan in plans.items():
        plan['samples']=np.asarray(plan['samples'])
        arrays[w]=plan['samples']
    np.savez_compressed(str(WORK/'wrap_samples.npz'),**arrays)
    (WORK/'wrap_sample_plan.json').write_text(json.dumps({'fit':fitposes,'held_out':validationposes,'joints':alljoints,'targets':{w:{k:v for k,v in p.items() if k!='samples'} for w,p in plans.items()},'original_pose':saved_pose,'original_switch':saved_switch},indent=2))
finally:
    apply_pose(saved_pose)
    for p,v in saved_switch.items():cmds.setAttr(p,v)
result={'fit_poses':len(fitposes),'held_out_poses':len(validationposes),'targets':{w:len(p['joints']) for w,p in plans.items()},'seconds':time.time()-t0}
