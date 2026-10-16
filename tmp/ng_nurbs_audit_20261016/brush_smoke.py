import sys,traceback,json
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
sys.path.insert(0,'C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts')
sys.path.insert(0,'C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts')
cmds.loadPlugin('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/plug-ins/2026/ngSkinTools2.mll')
from ng_nurbs_bridge import core,topology,brush
result={}
try:
 cmds.undoInfo(state=True)
 srf=cmds.nurbsPlane(patchesU=2,patchesV=4,ch=False,width=4)[0]
 js=[cmds.createNode('joint') for _ in range(3)]
 skin=cmds.skinCluster(js,srf,tsb=True,skinMethod=2)[0]
 for i in range(35):cmds.setAttr(skin+'.blendWeights[%s]'%i,i/34)
 original_blend=[core.plug(skin+'.blendWeights[%s]'%i).asDouble() for i in range(35)]
 b=core.create(srf);layer=b.layers().list()[0]
 result['create_dq_error']=max(abs(core.plug(skin+'.blendWeights[%s]'%i).asDouble()-v) for i,v in enumerate(original_blend))
 before=core.layer_snapshot(b,layer.id)
 controller=brush.Controller(b,layer.id,0,intensity=1)
 controller.flood()
 after=core.layer_snapshot(b,layer.id)
 cmds.undo();result['undo_influence']=core.layer_snapshot(b,layer.id)==before
 cmds.redo();result['redo_influence']=core.layer_snapshot(b,layer.id)==after
 c=brush.Controller(b,layer.id,'mask',intensity=1,value=.3)
 before=core.layer_snapshot(b,layer.id);c.flood();cmds.undo()
 result['undo_empty_mask']=core.layer_snapshot(b,layer.id)==before
 c=brush.Controller(b,layer.id,'dq',intensity=1,value=.8);c.flood()
 result['dq_flood']=core.plug(skin+'.blendWeights[0]').asDouble()
 fn=om.MFnNurbsSurface(topology.dag(b.shape));center=fn.getPointAtParam(.5,.5,om.MSpace.kWorld);normal=fn.normal(.5,.5,om.MSpace.kWorld)
 origin,direction=center+normal*10,-normal
 hit=topology.ray_hit(b.shape,origin,direction)
 result['ray_hit']=str(hit)
 c=brush.Controller(b,layer.id,0,radius=2,intensity=.5,value=.2)
 result['dab']=c.dab(origin,direction);c.finish()
 result['samples']=len(c.display[0])
 b.detach(restore=True)
 result['restore_dq_error']=max(abs(core.plug(skin+'.blendWeights[%s]'%i).asDouble()-v) for i,v in enumerate(original_blend))
except Exception:result['traceback']=traceback.format_exc()
Path(__file__).with_name('brush_smoke.json').write_text(json.dumps(result,indent=2))
print(result,flush=True)
maya.standalone.uninitialize()
