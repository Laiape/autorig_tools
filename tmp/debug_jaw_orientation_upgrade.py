import sys
from pathlib import Path
import numpy as np
sys.path[:0]=[r'C:/proyectos/auto-rig/autorig_tools',r'C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/tools/tests']
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from fixtures.jaw_scene import build
from maya_tools.scripts.tools import jaw_graph_optimizer as opt
build(Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015/baseline.py'))
names=sorted(cmds.ls(type='joint'))
def read():return np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in names])
initial=read()
original_connect,original_delete,original_dirty=cmds.connectAttr,cmds.delete,cmds.dgdirty
def wrap(fn):
 def call(*args,**kwargs):
  before=read()
  detail={}
  if fn==original_connect and 'Frame_MMX' in str(args):
   old=cmds.connectionInfo(args[1],sourceFromDestination=True)
   detail={'old':old,'old_value':cmds.getAttr(old),'new_value':cmds.getAttr(args[0]),'input':cmds.getAttr(args[1].split('.')[0]+'.inputMatrix')}
  answer=fn(*args,**kwargs);after=read();error=float(np.max(np.abs(before-after)))
  if error>1e-5:
   print('DETAIL',detail,flush=True)
   original_dirty(allPlugs=True)
   print('AFTER_DIRTY',float(np.max(np.abs(read()-before))),flush=True)
   print('DRIFT',fn.__name__,args,kwargs,error,'worst',names[np.unravel_index(np.argmax(np.abs(before-after)),before.shape)[0]],flush=True)
   raise RuntimeError('Unexpected drift')
  return answer
 return call
cmds.connectAttr=wrap(original_connect);cmds.delete=wrap(original_delete);cmds.dgdirty=wrap(original_dirty)
print(opt.optimize(),flush=True)
print('ERROR',float(np.max(np.abs(read()-initial))),flush=True)
