import json,numpy as np
from pathlib import Path
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015/latest')
manifest=json.loads((WORK/'neutral_manifest.json').read_text())
def smoothstep(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def nearest_curve(points,curve):
    start=curve[:-1];edge=curve[1:]-start
    dif=points[:,None,:]-start[None,:,:]
    t=np.clip(np.einsum('vsi,si->vs',dif,edge)/np.maximum((edge**2).sum(axis=1)[None,:],1e-12),0,1)
    hits=start[None,:,:]+t[:,:,None]*edge[None,:,:]
    d=((points[:,None,:]-hits)**2).sum(axis=2);index=d.argmin(axis=1)
    return np.sqrt(d[np.arange(len(points)),index]),hits[np.arange(len(points)),index]
summary=[]
for rec in manifest:
    mesh=rec['mesh'];data=np.load(str(WORK/(mesh+'_neutral.npz')));points=data['rest'];weights=data['weights'];names=rec['names']
    curves=[]
    for part in ('upper','lower'):
        curve=np.array([p for n,p in rec['joints'].items() if part+'Lip' in n and 'NonRot' not in n])
        curve=curve[np.argsort(curve[:,0])];curves.append(curve)
    distances=[];hits=[]
    for curve in curves:
        d,h=nearest_curve(points,curve);distances.append(d);hits.append(h)
    which=np.argmin(distances,axis=0)
    distance=np.choose(which,distances);closest=np.stack(hits)[which,np.arange(len(points))]
    # Fade over the cavity-facing side of the lip, following the actual lip row.
    depth=closest[:,2]-points[:,2]
    inside=smoothstep(-.15,.35,depth)
    band=1-smoothstep(.65,2.25,distance)
    lipcols=np.array([i for i,n in enumerate(names) if 'lip' in n.lower()])
    jawcols=np.array([names.index('C_jaw_ENV'),names.index('C_upperJaw_ENV')])
    lips=weights[:,lipcols].sum(axis=1)
    support=smoothstep(.015,.18,lips)
    ownership=inside*band*support
    ownership[ownership<.001]=0
    # Reflect the geometric falloff through reciprocal rest-vertex pairs.
    reflect=points.copy();reflect[:,0]*=-1
    paired=[]
    for st in range(0,len(points),128):
        d=((reflect[st:st+128,None,:]-points[None,:,:])**2).sum(axis=2);paired.extend(d.argmin(axis=1))
    paired=np.array(paired);valid=(paired[paired]==np.arange(len(points)))&(np.linalg.norm(points[paired]-reflect,axis=1)<.04)
    ownership[valid]=.5*(ownership[valid]+ownership[paired[valid]])
    # Weighted topological neighbors do not cross the upper/lower mouth seam.
    adjacency=[set() for _ in points];offset=0
    for count in data['counts']:
        face=data['vertices'][offset:offset+count];offset+=count
        for a,b in zip(face,np.roll(face,-1)):
            adjacency[int(a)].add(int(b));adjacency[int(b)].add(int(a))
    edge_a=np.array([i for i,near in enumerate(adjacency) for _ in near]);edge_b=np.array([j for near in adjacency for j in near])
    edgeweights=1/np.maximum(np.linalg.norm(points[edge_a]-points[edge_b],axis=1),.02)
    totals=np.bincount(edge_a,weights=edgeweights,minlength=len(points))
    originaljaw=weights[:,jawcols];jaw=originaljaw.copy()
    # Smooth the scalar jaw transition, then hand the inner lip to its own joints.
    for _ in range(8):
        near=np.column_stack([np.bincount(edge_a,weights=edgeweights*jaw[edge_b,j],minlength=len(points))/np.maximum(totals,1e-12) for j in range(2)])
        jaw=jaw*(1-.35*ownership[:,None])+near*(.35*ownership[:,None])
    jaw*=1-ownership[:,None]
    # Retain the existing shape along the lip: redistribute only the scalar jaw
    # contribution, preserving the normalized ratios of the lip influences.
    distribution=weights[:,lipcols]/np.maximum(lips[:,None],1e-12)
    removed=(originaljaw-jaw).sum(axis=1)
    edited=ownership>1e-6
    result=weights.copy()
    result[:,jawcols]=jaw
    result[:,lipcols]+=removed[:,None]*distribution
    result[~edited]=weights[~edited]
    if (result< -1e-8).any():raise RuntimeError('Negative weights')
    result=np.maximum(result,0)
    # Match both sides only within this localized edit, preserving all other rows.
    nameix={n:i for i,n in enumerate(names)}
    mirrored=np.array([nameix.get('R_'+n[2:] if n.startswith('L_') else 'L_'+n[2:] if n.startswith('R_') else n,i) for i,n in enumerate(names)])
    symmetric=valid&edited
    result[symmetric]=.5*(result[symmetric]+result[paired[symmetric]][:,mirrored])
    changed=np.max(abs(result-weights),axis=1)>1e-8
    if np.max(abs(result.sum(axis=1)-weights.sum(axis=1)))>.0002:raise RuntimeError('Row sum changed')
    group_mask=1-ownership
    np.savez_compressed(str(WORK/(mesh+'_weight_plan.npz')),weights=result,ownership=ownership,jaw_target_mask=group_mask,edited=edited,changed=changed,paired=paired)
    report={'mesh':mesh,'skin':rec['skin'],'changed_vertices':int(changed.sum()),'inner_core_vertices':int((ownership>.9).sum()),'jaw_weight_before_mean':float(originaljaw[edited].sum(axis=1).mean()),'jaw_weight_after_mean':float(result[edited][:,jawcols].sum(axis=1).mean()),'maximum_weight_change':float(np.max(abs(result-weights))),'edit_bounds':[points[edited].min(axis=0).tolist(),points[edited].max(axis=0).tolist()],'unchanged_outside':bool(np.array_equal(result[~edited],weights[~edited]))}
    summary.append(report)
(WORK/'weight_plan_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
