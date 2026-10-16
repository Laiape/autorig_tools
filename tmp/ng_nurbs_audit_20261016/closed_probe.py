import sys,json
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds,mel
from maya.api import OpenMaya as om
sys.path.insert(0,'C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts')
from ng_nurbs_bridge import topology
results=[]
ring=[(1,0),(0,1),(-1,0),(0,-1),(1,0)]
for order in ['u_outer','v_outer']:
 parent=cmds.createNode('transform',name='closed_'+order)
 pts=[om.MPoint(ring[u][0],v,ring[u][1]) for u,v in ([(u,v) for u in range(5) for v in range(3)] if order=='u_outer' else [(u,v) for v in range(3) for u in range(5)])]
 fn=om.MFnNurbsSurface()
 fn.create(pts,[0,1,2,3,4],[0,1,2],1,1,om.MFnNurbsSurface.kClosed,om.MFnNurbsSurface.kOpen,False,om.MSelectionList().add(parent).getDependNode(0))
 rec={'order':order,'forms_before':[fn.formInU,fn.formInV], 'dimensions':[fn.numCVsInU,fn.numCVsInV], 'endpoints':[[fn.cvPosition(u,v).x,fn.cvPosition(u,v).y,fn.cvPosition(u,v).z] for u,v in [(0,0),(4,0),(0,2),(4,2)]]}
 js=[cmds.createNode('joint') for _ in range(2)]
 skin=cmds.skinCluster(js,parent,tsb=True)[0]
 rec['forms_after']=topology.signature(topology.surface_shape(parent))
 results.append(rec)
parent=cmds.createNode('transform',name='closed_native')
shape=cmds.createNode('nurbsSurface',parent=parent)
coords=' '.join('%s %s %s'%(ring[u][0],v,ring[u][1]) for u in range(5) for v in range(3))
mel.eval('setAttr "%s.cached" -type "nurbsSurface" 1 1 1 0 no 5 0 1 2 3 4 3 0 1 2 15 %s;'%(shape,coords))
results.append({'order':'native_cached','forms_before':topology.signature(shape)})
Path(__file__).with_name('closed_probe.json').write_text(json.dumps(results,indent=2))
maya.standalone.uninitialize()
