import json,numpy as np
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015')
def dag(n):
    s=om.MSelectionList();s.add(n);p=s.getDagPath(0)
    if p.node().hasFn(om.MFn.kTransform):p.extendToShape()
    return p
result={'geometry':[],'jaw_controls':[]}
for name in ('cabeza_high','cabeza_low'):
    p=dag(name);fn=om.MFnMesh(p)
    parents=[name]+(cmds.listRelatives(name,allParents=True,fullPath=True) or [])
    result['geometry'].append({'mesh':name,'path':p.fullPathName(),'vertices':fn.numVertices,'visible':cmds.getAttr(name+'.visibility'),'override':cmds.getAttr(name+'.overrideEnabled'),'parents_visibility':[(n,cmds.getAttr(n+'.visibility')) for n in parents],'smooth':cmds.getAttr(p.fullPathName()+'.displaySmoothMesh')})
    shapes=cmds.listRelatives(name,s=True,fullPath=True) or []
    result['geometry'][-1]['shapes']=shapes
for c in ('C_jaw_CTL','C_upperLip_CTL','C_lowerLip_CTL','C_upperJaw_CTL'):
    result['jaw_controls'].append({'node':c,'attrs':{a:cmds.getAttr(c+'.'+a) for a in cmds.listAttr(c,k=True) or []}})
def weights(sk,mesh):
    s=om.MSelectionList();s.add(sk);fn=oma.MFnSkinCluster(s.getDependNode(0))
    path=dag(mesh);cf=om.MFnSingleIndexedComponent();co=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(om.MFnMesh(path).numVertices)
    w,n=fn.getWeights(path,co);return np.asarray(w).reshape(-1,n).copy(),[p.partialPathName() for p in fn.influenceObjects()]
w,names=weights('skinCluster41','cabeza_low')
fn=om.MFnMesh(dag('cabeza_low'));pts=np.asarray(fn.getPoints(om.MSpace.kObject))[:,:3].copy();counts,verts=fn.getVertices();tri_counts,tri_verts=fn.getTriangles()
normals=np.asarray(fn.getVertexNormals(True,om.MSpace.kObject))[:,:3].copy()
lipcols=[i for i,n in enumerate(names) if 'lip' in n.lower()]
jawcols=[i for i,n in enumerate(names) if 'jaw' in n.lower()]
result['low_skin']={'names':names,'lip_influence_vertices':int((w[:,lipcols].sum(axis=1)>.1).sum()),'jaw_cols':[(i,names[i]) for i in jawcols]}
np.savez_compressed(str(WORK/'live_low_geometry.npz'),points=pts,weights=w,normals=normals,counts=np.asarray(counts).copy(),vertices=np.asarray(verts).copy(),triangles=np.asarray(tri_verts).reshape(-1,3).copy())
(WORK/'geometry_info.json').write_text(json.dumps(result,indent=2,default=str))
