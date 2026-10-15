"""Check native posed triangulation, including contact in extreme U poses."""
import os,json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1';os.environ['QT_QPA_PLATFORM']='offscreen'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
from mesh_intersections import crossings
root=Path.cwd();work=root/'.git/edward_u_revision'
out=root/'maya_tools/docs/validation/edward_distributed_u_20261015'
cmds.file(str(work/'distributed_final.mb'),open=True,force=True);cmds.evaluationManager(mode='off')
reference=np.load(work/'restored_reference.npz');rows=[]
for name,angle,x,y in (('U0',0,5.2,2),('U20',20,5.2,2),('U30',30,5.2,2),('grid_0_2.6_1',0,2.6,1)):
    cmds.setAttr('C_jaw_CTL.rx',angle)
    for side in ('L','R'):cmds.setAttr(side+'_lipCorner_CTL.translate',x,y,0)
    for mesh in ('cabeza_high','cabeza_low'):
        shape=cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True)[0]
        fn=om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))
        a=reference[name+'__'+mesh]
        b=np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)])
        counts,connects=fn.getVertices();data=om.MFnMeshData().create()
        old=om.MFnMesh();old.create([om.MPoint(*p) for p in a],counts,connects,parent=data)
        old_tri=np.array(old.getTriangles()[1],dtype=int).reshape(-1,3)
        new_tri=np.array(fn.getTriangles()[1],dtype=int).reshape(-1,3)
        moved=np.linalg.norm(b-a,axis=1)>1e-7
        before=len(crossings(a,old_tri,np.flatnonzero(moved[old_tri].any(axis=1))))
        after=len(crossings(b,new_tri,np.flatnonzero(moved[new_tri].any(axis=1))))
        def degenerates(p,tri):
            return int(np.sum(np.linalg.norm(np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]]),axis=1)<1e-10))
        row=dict(pose=name,mesh=mesh,strict_crossings_before=before,strict_crossings_after=after,
                 degenerate_before=degenerates(a,old_tri),degenerate_after=degenerates(b,new_tri),
                 triangulation_changed=not np.array_equal(old_tri,new_tri))
        rows.append(row);print(json.dumps(row),flush=True)
report=dict(success=all(r['strict_crossings_after']<=r['strict_crossings_before'] and r['degenerate_after']<=r['degenerate_before'] for r in rows),
            method='Maya native triangulation is recomputed at each posed mesh; fixed neutral diagonals are not valid for nonplanar posed quads. Strict noncoplanar non-adjacent crossings exclude shared-vertex contact. Existing intersections are reported, not claimed absent.',cases=rows)
(out/'posed_contacts.json').write_text(json.dumps(report,indent=2))
assert report['success'],rows
