import sys
from pathlib import Path
import numpy as np
sys.path[:0]=[r'C:/proyectos/auto-rig/autorig_tools',r'C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/tools/tests']
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from fixtures.jaw_scene import build,SOURCE
before={}
for kind,source in [('before',Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015/baseline.py')),('after',SOURCE)]:
 build(source)
 for axis in 'XYZ':cmds.setAttr('C_upperLip_NURB.scale'+axis,lock=False)
 for scale in (1.,1e-9,0.):
  cmds.setAttr('C_upperLip_NURB.scale',scale,scale,scale)
  pin=np.array(cmds.getAttr('C_upperLipAimVector_UVP.outputMatrix[6]')).reshape(4,4)
  m=np.array(cmds.getAttr('R_upperLip06_JNT.worldMatrix[0]')).reshape(4,4)
  assert np.isfinite(m).all(),(kind,scale)
  print(kind,scale,'pin_lengths',np.linalg.norm(pin[:3,:3],axis=1),'frame_lengths',np.linalg.norm(m[:3,:3],axis=1),flush=True)
  if kind=='before':before[scale]=m
  else:print('ERROR',scale,float(np.abs(m-before[scale]).max()),flush=True)
