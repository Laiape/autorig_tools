import sys,json
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
sys.path[:0]=['C:/proyectos/auto-rig/autorig_tools','C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts','C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts']
cmds.loadPlugin('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/plug-ins/2026/ngSkinTools2.mll')
from maya_tools.scripts.tools.tests.test_ng_nurbs_bridge import fixture
from ng_nurbs_bridge import core,topology
cmds.undoInfo(state=True)
surface,skin,js=fixture()
b=core.create(surface)
def dump(b):
 p=core.node_for(b.data['proxy_uuid'])
 fn=om.MFnMesh(topology.dag(p))
 points=[[a.x,a.y,a.z,a.w] for a in fn.getPoints()]
 orig=cmds.listRelatives(cmds.listRelatives(p,p=True)[0],shapes=True,type='mesh',fullPath=True)[1]
 return {'points':points,'original':[[a.x,a.y,a.z] for a in om.MFnMesh(topology.dag(orig)).getPoints()], 'weights':core.sparse_weights(b.proxy_skin), 'matrices':[cmds.getAttr(b.proxy_skin+'.bindPreMatrix[%s]'%i['logical']) for i in b.data['proxy_influences']]}
r={'before':dump(b)}
cmds.undo();cmds.redo();b=core.find(surface);r['after']=dump(b)
Path(__file__).with_name('redo_probe.json').write_text(json.dumps(r,indent=2))
maya.standalone.uninitialize()
