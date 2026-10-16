import sys
sys.path[:0]=['C:/proyectos/auto-rig/autorig_tools','C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/tools/tests']
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from test_eyelid_blink import build
from maya_tools.scripts.tools import eyelid_candidates
for plugin in ('matrixNodes','lookdevKit'):cmds.loadPlugin(plugin,quiet=True)
eye=build('L',True)
info=eyelid_candidates.deboor('L')
for mode in ('off','serial','parallel'):
 cmds.evaluationManager(mode=mode)
 for angle in (0,25,-30,0):
  cmds.setAttr('L_eyelidDown_CTL.rz',angle)
  errors=[]
  for sample in info['sampling']:
   a=np.array(cmds.getAttr(sample['plug']))[0]
   b=np.array(cmds.pointOnCurve('L_eyelid'+('Up' if sample['lid']=='upper' else 'Down')+'Pose_CRV',pr=sample['u'],p=True))
   errors.append(float(np.max(abs(a-b))))
  print('RAW',mode,angle,max(errors),flush=True)
