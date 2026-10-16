import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(r'C:/proyectos/auto-rig/autorig_tools')
sys.path[:0]=[str(ROOT),str(ROOT/'maya_tools/scripts')]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import jaw_graph_optimizer
folder=Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015')
source=folder/'artist_before_orientation.mb'
output=ROOT/'maya_tools/assets/Edward/scenes/Edward_working_v003.mb'
if output.exists():raise RuntimeError('Output scene already exists; refusing overwrite')
cmds.file(str(source),open=True,force=True,prompt=False,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
for evaluator in ('cache','gpuOverride'):
 if evaluator in (cmds.evaluator(q=True) or []):cmds.evaluator(name=evaluator,enable=False)
nodes=sorted(cmds.listRelatives('C_lipsSkinning_GRP',ad=True,type='joint'))
def read():
 meshes={}
 for name in ('cabeza_low','cabeza_high','cuerpo_base'):
  shape=cmds.listRelatives(name,shapes=True,noIntermediate=True,fullPath=True)[0]
  fn=om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))
  meshes[name]=np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)])
 return meshes,np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in nodes])
before,matrix_before=read()
change=jaw_graph_optimizer.optimize()
after,matrix_after=read()
errors={n:float(np.abs(before[n]-after[n]).max()) for n in before}
assert max(errors.values())<2e-5,errors
assert float(np.abs(matrix_before-matrix_after).max())<2e-5
cmds.evaluationManager(mode='parallel')
# Restore the original snapshot's interactive evaluator settings for delivery.
for evaluator in ('gpuOverride',):
 if evaluator in (cmds.evaluator(q=True) or []):cmds.evaluator(name=evaluator,enable=True)
cmds.file(rename=str(output))
cmds.file(save=True,type='mayaBinary',force=False)
cmds.file(new=True,force=True)
cmds.file(str(output),open=True,force=True,prompt=False,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
for evaluator in ('cache','gpuOverride'):
 if evaluator in (cmds.evaluator(q=True) or []):cmds.evaluator(name=evaluator,enable=False)
reopened,matrix_reopened=read()
reopen_errors={n:float(np.abs(after[n]-reopened[n]).max()) for n in after}
assert max(reopen_errors.values())<2e-5,reopen_errors
result={'success':True,'scene':str(output),'removed_nodes':len(change['removed']),'geometry_errors':errors,'reopen_errors':reopen_errors,'matrix_reopen_error':float(np.abs(matrix_after-matrix_reopened).max()),'original_snapshot':str(source),'active_artist_scene_changed':False}
(folder/'delivery_scene.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS optimized native scene saved and reopened',json.dumps(result),flush=True)
