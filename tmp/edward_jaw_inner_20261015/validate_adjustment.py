import json,hashlib,numpy as np
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools import bifrost_wrinkles
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015/latest')
manifest=json.loads((WORK/'neutral_manifest.json').read_text());pose=json.loads((WORK/'original_pose.json').read_text())
def dag(mesh):
    s=om.MSelectionList();s.add(mesh);p=s.getDagPath(0)
    if p.node().hasFn(om.MFn.kTransform):p.extendToShape()
    return p
def points(mesh):return np.asarray(om.MFnMesh(dag(mesh)).getPoints(om.MSpace.kWorld))[:,:3].copy()
def setpose(values):
    for p in pose:cmds.setAttr(p,values.get(p,0))
rows=[]
try:
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        setpose({})
        for rec in manifest:
            mesh=rec['mesh'];skin=rec['skin'];src=np.load(str(WORK/(mesh+'_neutral.npz')));plan=np.load(str(WORK/(mesh+'_weight_plan.npz')))
            base=points(mesh);neutral_error=np.linalg.norm(base-src['points'],axis=1)
            s=om.MSelectionList();s.add(skin);fn=oma.MFnSkinCluster(s.getDependNode(0));cf=om.MFnSingleIndexedComponent();comp=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(len(base));raw,n=fn.getWeights(dag(mesh),comp);w=np.asarray(raw).reshape(-1,n).copy()
            if not np.isfinite(w).all() or np.min(w)<0 or np.max(abs(w.sum(axis=1)-1))>.0002:raise RuntimeError('Invalid skin normalization '+skin)
            names=rec['names'];lc=[i for i,n in enumerate(names) if 'lip' in n.lower()];jc=[names.index('C_jaw_ENV'),names.index('C_upperJaw_ENV')]
            core=plan['ownership']>.99
            report={'mesh':mesh,'neutral_max_change_cm':float(neutral_error.max()),'outside_weight_max_change':float(abs(w[~plan['edited']]-src['weights'][~plan['edited']]).max()),'core_jaw_weight_max':float(w[core][:,jc].sum(axis=1).max()) if core.any() else None,'normalization_max_error':float(abs(w.sum(axis=1)-1).max()),'pose_checks':[]}
            if report['neutral_max_change_cm']>.001:raise RuntimeError('Unexpected neutral change '+str(report))
            if report['outside_weight_max_change']>1e-7:raise RuntimeError('Weights escaped region '+mesh)
            ids=np.flatnonzero((w[:,lc].sum(axis=1)>.025)&(plan['paired'][plan['paired']]==np.arange(len(base))))
            for jaw in (0,15,30,44.41942630875321):
                for label,x,y in [('neutral',0,0),('wide',5,0),('smile',0,3),('frown',0,-4),('wide_smile',4.5669333,2.8215159)]:
                    p={'C_jaw_CTL.rotateX':jaw}
                    for side in ('L','R'):p[side+'_lipCorner_CTL.translateX']=x;p[side+'_lipCorner_CTL.translateY']=y
                    setpose(p);pts=points(mesh)
                    if not np.isfinite(pts).all():raise RuntimeError('Nonfinite geometry')
                    delta=pts-base;reflected=delta[plan['paired']].copy();reflected[:,0]*=-1;e=np.linalg.norm(delta-reflected,axis=1)[ids]
                    report['pose_checks'].append({'jaw':jaw,'pose':label,'asym_max_cm':float(e.max()),'asym_rms_cm':float(np.sqrt((e**2).mean()))})
            setpose({})
            rows.append(report)
    # Confirm the previous three bakes still exist and retain their weights.
    snapshot=json.loads(Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/skin_clusters/Edward_v069.skc').read_text())
    baked=[]
    for mesh,skins in snapshot.items():
        if mesh.startswith('__'):continue
        for entry in skins:
            if '_wrapBake_SKC' not in entry['name']:continue
            s=om.MSelectionList();s.add(entry['name']);fn=oma.MFnSkinCluster(s.getDependNode(0));path=dag(mesh);cf=om.MFnSingleIndexedComponent();co=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(entry['vertex_count']);raw,n=fn.getWeights(path,co);w=np.asarray(raw).reshape(-1,n).copy();names=[p.partialPathName() for p in fn.influenceObjects()]
            stored=np.zeros_like(w)
            for name,v in entry['sparse_weights'].items():stored[np.array(v['ix']),names.index(name)]=v['vw']
            err=float(abs(w-stored).max());baked.append({'skin':entry['name'],'max_weight_change':err})
            if err>1e-10:raise RuntimeError('Baked weights changed')
    if len(baked)!=3 or len(cmds.ls(type='proximityWrap') or [])!=20:raise RuntimeError('Bake count changed')
finally:setpose(pose)
result={'mesh_checks':rows,'bakes':baked,'wrap_count':20,'pose_restored':True}
(WORK/'adjustment_validation.json').write_text(json.dumps(result,indent=2,allow_nan=False))
result={'meshes':[{k:v for k,v in row.items() if k!='pose_checks'} for row in rows],'bakes':baked,'wrap_count':20}
