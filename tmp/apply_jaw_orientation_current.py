from pathlib import Path
import importlib
import sys
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import jaw_graph_optimizer
importlib.reload(jaw_graph_optimizer)
folder=Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015')
scene=cmds.file(q=True,sn=True)
if scene!='C:/Users/LaiaPeris/Documents/maya/projects/default/scenes/CHAR_Edward_v001.ma':
 raise RuntimeError('The artist changed scenes; the upgrade was not applied.')
selection=cmds.ls(sl=True,long=True)
mode=cmds.evaluationManager(q=True,mode=True)[0]
nodes=sorted(cmds.listRelatives('C_lipsSkinning_GRP',ad=True,type='joint'))
attrs=cmds.ls('*.wrinkleDepth','*.wrinkleValue','*.autoWide','*.autoNarrow') or []
attrs_before={p:cmds.getAttr(p) for p in attrs}
def matrices():return np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in nodes])
meshes={}
for mesh in ('cabeza_low','cabeza_high','cuerpo_base'):
 if cmds.objExists(mesh):
  shapes=cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True) or []
  if shapes and cmds.nodeType(shapes[0])=='mesh':meshes[mesh]=om.MFnMesh(om.MSelectionList().add(shapes[0]).getDagPath(0))
def points():return {n:np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)]) for n,fn in meshes.items()}
before_matrices=matrices();before_points=points();before_count=len(cmds.ls())
change=jaw_graph_optimizer.optimize()
try:
 matrix_error=float(np.abs(matrices()-before_matrices).max())
 after_points=points()
 errors={n:float(np.abs(after_points[n]-before_points[n]).max()) for n in meshes}
 assert matrix_error<2e-5,matrix_error
 assert max(errors.values())<2e-5,errors
 assert attrs_before=={p:cmds.getAttr(p) for p in attrs},'Control values changed'
 assert mode==cmds.evaluationManager(q=True,mode=True)[0]
 assert scene==cmds.file(q=True,sn=True)
 assert selection==cmds.ls(sl=True,long=True)
except BaseException:
 cmds.undo()
 raise
for name,module in list(sys.modules.items()):
 if name.endswith('jaw_module_nurbs'):importlib.reload(module)
after=folder/'artist_after_orientation.mb'
if after.exists():raise RuntimeError('Upgrade verified, but the backup destination already exists')
cmds.file(str(after),exportAll=True,type='mayaBinary',preserveReferences=True)
result={'scene':scene,'removed_nodes':before_count-len(cmds.ls()),'change':change,'matrix_error':matrix_error,'geometry_errors':errors,'backup_before':str(folder/'artist_before_orientation.mb'),'backup_after':str(after),'scene_modified':cmds.file(q=True,modified=True)}
