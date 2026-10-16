import sys,traceback,json
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
sys.path.insert(0,'C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts')
sys.path.insert(0,'C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts')
cmds.loadPlugin('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/plug-ins/2026/ngSkinTools2.mll')
from ng_nurbs_bridge import core,topology
results=[]
for kind in ['open','periodic_v','periodic_uv','sparse_influences']:
 try:
  cmds.file(new=True,force=True);cmds.undoInfo(state=True)
  j=[cmds.createNode('joint') for _ in range(3)]
  srf=(cmds.nurbsPlane(patchesU=2,patchesV=4,ch=False) if kind in ['open','sparse_influences'] else cmds.cylinder(ch=False) if kind=='periodic_v' else cmds.torus(ch=False))[0]
  skin=cmds.skinCluster(j,srf,tsb=True)[0]
  if kind=='sparse_influences':cmds.skinCluster(skin,e=True,removeInfluence=j[1])
  initial=core.sparse_weights(skin)
  bridge=core.create(srf)
  meta=bridge.node
  result={'kind':kind,'create':True,'active':len(bridge.data['active']),'data':bridge.data['topology']}
  cmds.undo();result['undo']=not cmds.objExists(meta)
  cmds.redo();bridge=core.find(srf);bridge.validate();result['redo']=bridge is not None
  layer=bridge.layers().list()[0]
  layer.set_weights(bridge.data['proxy_influences'][0]['logical'],[.25]*(bridge.data['topology']['nu']*bridge.data['topology']['nv']))
  result['edit_first_row']=core.sparse_weights(skin)['0']
  path=Path(__file__).with_name('core_smoke_'+kind+'.ma')
  cmds.file(rename=str(path));cmds.file(save=True,type='mayaAscii');cmds.file(str(path),open=True,force=True)
  bridge=core.find(srf);bridge.validate();result['reopen']=True
  bridge.detach(restore=True);result['restore']=core.sparse_weights(skin)==initial
  cmds.undo();bridge=core.find(srf);bridge.validate();result['undo_detach']=True
  cmds.redo();result['redo_detach']=core.find(srf) is None
  results.append(result)
 except Exception:results.append({'kind':kind,'traceback':traceback.format_exc()})
Path(__file__).with_name('core_smoke.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results),flush=True)
maya.standalone.uninitialize()
