import json,numpy as np
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015')
def path(n):
    sl=om.MSelectionList();sl.add(n);p=sl.getDagPath(0)
    if p.node().hasFn(om.MFn.kTransform):p.extendToShape()
    return p
controls=sorted(set(cmds.ls('*lip*CTL','*Lip*CTL','*jaw*CTL','*Jaw*CTL',type='transform') or []))
saved={}
for c in controls:
    for a in ['translateX','translateY','translateZ','rotateX','rotateY','rotateZ','Roll']:
        p=c+'.'+a
        if cmds.objExists(p) and cmds.getAttr(p,settable=True):saved[p]=cmds.getAttr(p)
(WORK/'original_pose.json').write_text(json.dumps(saved,indent=2))
meshes=[]
try:
    for p in saved:cmds.setAttr(p,0)
    for mesh,skin in [('cabeza_high','C_mouth_local_SKC'),('cabeza_low','skinCluster41')]:
        dag=path(mesh);mf=om.MFnMesh(dag)
        points=np.asarray(mf.getPoints(om.MSpace.kWorld))[:,:3].copy()
        orig=next(s for s in cmds.listRelatives(mesh,s=True,f=True) if cmds.getAttr(s+'.intermediateObject'))
        rest=np.asarray(om.MFnMesh(path(orig)).getPoints(om.MSpace.kWorld))[:,:3].copy()
        normals=np.asarray(mf.getVertexNormals(True,om.MSpace.kWorld))[:,:3].copy()
        counts,verts=mf.getVertices();_,triangles=mf.getTriangles()
        sel=om.MSelectionList();sel.add(skin);sf=oma.MFnSkinCluster(sel.getDependNode(0))
        compfn=om.MFnSingleIndexedComponent();comp=compfn.create(om.MFn.kMeshVertComponent);compfn.setCompleteData(mf.numVertices)
        raw,n=sf.getWeights(dag,comp);weights=np.asarray(raw).reshape(-1,n).copy();names=[i.partialPathName() for i in sf.influenceObjects()]
        np.savez_compressed(str(WORK/(mesh+'_neutral.npz')),points=points,rest=rest,normals=normals,counts=np.asarray(counts).copy(),vertices=np.asarray(verts).copy(),triangles=np.asarray(triangles).reshape(-1,3).copy(),weights=weights)
        meshes.append({'mesh':mesh,'skin':skin,'names':names,'joints':{name:cmds.xform(name,q=True,ws=True,t=True) for name in names if 'lip' in name.lower()},'skin_attrs':{a:cmds.getAttr(skin+'.'+a) for a in ['normalizeWeights','maintainMaxInfluences','maxInfluences','skinningMethod']}})
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
(WORK/'neutral_manifest.json').write_text(json.dumps(meshes,indent=2))
result=[{'mesh':m['mesh'],'skin':m['skin'],'skin_attrs':m['skin_attrs']} for m in meshes]
