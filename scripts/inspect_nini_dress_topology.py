import json
import os
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
root=Path(__file__).resolve().parents[1]
cmds.file(str(root/'maya_tools/assets/Nini/review/loop_rigger/Nini_ManualLoops_v001.ma'),open=True,force=True)
out={}
for mesh in ('c_tunic_GEO','c_body_GEO','c_pants_GEO'):
    sl=om.MSelectionList();sl.add(mesh);path=sl.getDagPath(0);path.extendToShape()
    fn=om.MFnMesh(path);points=fn.getPoints(om.MSpace.kWorld)
    slabs=[]
    for y in (46,50,55,60,65,70,75,80,83,88):
        pts=[p for p in points if abs(p.y-y)<2]
        if pts: slabs.append({'y':y,'count':len(pts),'x':[min(p.x for p in pts),max(p.x for p in pts)],
                             'z':[min(p.z for p in pts),max(p.z for p in pts)]})
    out[mesh]={'slabs':slabs}
    if mesh=='c_tunic_GEO':
        candidates={i for i,p in enumerate(points) if p.y<=83}
        seeds={i for i in candidates if points[i].y<50}
        adjacency=[set() for _ in points]
        it=om.MItMeshVertex(path)
        while not it.isDone(): adjacency[it.index()]=set(it.getConnectedVertices());it.next()
        selected=set(seeds);queue=list(seeds)
        while queue:
            for n in adjacency[queue.pop()].intersection(candidates)-selected: selected.add(n);queue.append(n)
        skin='skinCluster__c_tunic_GEO';sl=om.MSelectionList();sl.add(skin);sf=oma.MFnSkinCluster(sl.getDependNode(0))
        out[mesh].update({'skirt_vertices':len(selected),'skirt_bounds':[min(points[i].x for i in selected),
                          max(points[i].x for i in selected),min(points[i].y for i in selected),max(points[i].y for i in selected),
                          min(points[i].z for i in selected),max(points[i].z for i in selected)],
                         'influence_count':len(sf.influenceObjects())})
directory=root/'maya_tools/assets/Nini/experiments/dress_keepout'
(directory/'topology_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('TOPOLOGY='+json.dumps(out),flush=True)
maya.standalone.uninitialize()
