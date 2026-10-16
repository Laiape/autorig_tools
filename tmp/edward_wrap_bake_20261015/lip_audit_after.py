import numpy as np
from tools import pose_blendshapes as posebs
def dag(node):
    sel=om.MSelectionList();sel.add(node);return sel.getDagPath(0)
def meshpoints(node):
    return np.asarray(om.MFnMesh(dag(node)).getPoints(om.MSpace.kWorld))[:,:3].copy()
def meshweights(skin):
    sel=om.MSelectionList();sel.add(skin);fn=oma.MFnSkinCluster(sel.getDependNode(0))
    geometries=[g for g in cmds.deformer(skin,q=True,g=True) or [] if cmds.nodeType(g)=='mesh']
    path=dag(geometries[-1]) if geometries else fn.getPathAtIndex(0)
    compfn=om.MFnSingleIndexedComponent();comp=compfn.create(om.MFn.kMeshVertComponent);compfn.setCompleteData(om.MFnMesh(path).numVertices)
    w,n=fn.getWeights(path,comp)
    return fn,path,comp,np.asarray(w).reshape(-1,n).copy(),[p.partialPathName() for p in fn.influenceObjects()]
head='cabeza_high'; low='cabeza_low'
headhist=cmds.listHistory(head) or []
headskins=[n for n in headhist if cmds.nodeType(n)=='skinCluster' and any(cmds.nodeType(g)=='mesh' for g in cmds.deformer(n,q=True,g=True) or [])]
headinfo=[]
for s in headskins:
    fn,path,comp,w,names=meshweights(s)
    headinfo.append({'skin':s,'geo':path.fullPathName(),'verts':len(w),'infs':names,'envelope':cmds.getAttr(s+'.envelope')})
lipjoints=[j for j in cmds.ls(type='joint') if 'lip' in j.lower()]
bs='cabeza_high_poseCorrectives_BLS'
envelopes={bs:cmds.getAttr(bs+'.envelope')}
cmds.setAttr(bs+'.envelope',0)
base=meshpoints(head)
# Pair vertices on the neutral undeformed sculpt, with a reciprocal map.
reflect=base.copy();reflect[:,0]*=-1
try:
    from scipy.spatial import cKDTree
    dist,pairs=cKDTree(base).query(reflect)
except ImportError:
    ds=[];ix=[]
    for start in range(0,len(base),256):
        d=np.sum((reflect[start:start+256,None,:]-base[None,:,:])**2,axis=2);ii=d.argmin(axis=1)
        ds.extend(np.sqrt(d[np.arange(len(ii)),ii]));ix.extend(ii)
    dist=np.array(ds);pairs=np.array(ix)
skin_audit=[]; lipmask=np.zeros(len(base),dtype=bool)
for s in headskins:
    fn,path,comp,w,names=meshweights(s)
    if len(w)!=len(base): continue
    cols=[i for i,n in enumerate(names) if 'lip' in n.lower()]
    if not cols: continue
    lipmask|=w[:,cols].sum(axis=1)>.025
    index={n:i for i,n in enumerate(names)}
    mirrored=[index.get(('R_'+n[2:]) if n.startswith('L_') else ('L_'+n[2:]) if n.startswith('R_') else n,-1) for n in names]
    good=np.array([i for i,k in enumerate(mirrored) if k>=0])
    wd=np.abs(w[:,good]-w[pairs][:,np.array(mirrored)[good]])
    skin_audit.append({'skin':s,'influences':names,'weight_max_asym':float(wd.max()),'weight_rms_asym':float(np.sqrt((wd**2).mean())),'asymmetric_vertices_gt_001':int((wd.max(axis=1)>.01).sum()),'lip_columns':cols})
lipids=np.flatnonzero(lipmask)
def asym(points,ids=lipids):
    delta=points-base
    mirrored=delta[pairs].copy();mirrored[:,0]*=-1
    e=np.linalg.norm(delta-mirrored,axis=1)[ids]
    return {'rms':float(np.sqrt((e**2).mean())),'max':float(e.max()),'p95':float(np.quantile(e,.95))}
channels=['C_jaw_CTL.rotateX','L_lipCorner_CTL.translateX','R_lipCorner_CTL.translateX','L_lipCorner_CTL.translateY','R_lipCorner_CTL.translateY']
values={p:cmds.getAttr(p) for p in channels}
cases=[('jaw15',{'C_jaw_CTL.rotateX':15}),('jaw30',{'C_jaw_CTL.rotateX':30}),('wide',{'L_lipCorner_CTL.translateX':5,'R_lipCorner_CTL.translateX':5}),('narrow',{'L_lipCorner_CTL.translateX':-2,'R_lipCorner_CTL.translateX':-2}),('smile',{'L_lipCorner_CTL.translateY':3,'R_lipCorner_CTL.translateY':3}),('frown',{'L_lipCorner_CTL.translateY':-4,'R_lipCorner_CTL.translateY':-4})]
evaluations=[]
try:
    for label,vals in cases:
        for p,v in values.items():cmds.setAttr(p,v)
        for p,v in vals.items():cmds.setAttr(p,v)
        cmds.setAttr(bs+'.envelope',0);without=meshpoints(head)
        cmds.setAttr(bs+'.envelope',1);withbs=meshpoints(head)
        corr=withbs-without
        mirrored=corr[pairs].copy();mirrored[:,0]*=-1
        e=np.linalg.norm(corr-mirrored,axis=1)[lipids]
        evaluations.append({'case':label,'skin_only':asym(without),'with_correctives':asym(withbs),'corrective_asym':{'rms':float(np.sqrt(np.mean(e**2))),'max':float(e.max())},'active_targets':[(a,cmds.getAttr(bs+'.'+a)) for a in (cmds.aliasAttr(bs,q=True) or [])[::2] if abs(cmds.getAttr(bs+'.'+a))>1e-6]})
finally:
    for p,v in values.items():cmds.setAttr(p,v)
    cmds.setAttr(bs+'.envelope',envelopes[bs])
attrs={a:safe(lambda a=a:cmds.getAttr(bs+'.'+a)) for a in ['origin','deformationOrder','supportNegativeWeights','tangentSpace','localVertexFrame','postDeformersMode'] if cmds.attributeQuery(a,node=bs,exists=True)}
result={'head_skins':headinfo,'skin_audit':skin_audit,'lip_vertices':len(lipids),'lip_bounds':[base[lipids].min(axis=0).tolist(),base[lipids].max(axis=0).tolist()],'mirror_rest_error':{'max':float(dist[lipids].max()),'rms':float(np.sqrt((dist[lipids]**2).mean())),'reciprocal_pairs':int((pairs[pairs[lipids]]==lipids).sum())},'cases':evaluations,'blendshape_attrs':attrs,'lip_joints':lipjoints,'head_history':headhist}
(WORK/'lip_audit_after.json').write_text(json.dumps(result,indent=2,default=str))
np.savez_compressed(str(WORK/'lip_mirror_map_after.npz'),base=base,pairs=pairs,lipids=lipids,dist=dist)
result={k:v for k,v in result.items() if k not in ('head_history','lip_joints','head_skins')}
