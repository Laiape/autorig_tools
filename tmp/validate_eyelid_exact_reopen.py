import sys,json
from pathlib import Path
sys.path[:0]=['C:/proyectos/auto-rig/autorig_tools','C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/tools/tests']
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from test_eyelid_blink import build
from maya_tools.scripts.tools import eyelid_deboor_exact
for plugin in ('matrixNodes','lookdevKit'):cmds.loadPlugin(plugin,quiet=True)
eye=build('L',True)
for frame in range(1,17):
 for label in ('Up','Down'):
  for attr in ('rx','ry','rz','tx','ty'):
   value=np.sin(frame*.6+(0 if label=='Up' else 1))*(12 if attr.startswith('r') else .1)
   cmds.setKeyframe('L_eyelid'+label+'_CTL.'+attr,time=frame,value=float(value))
 for attr in ('Upper_Blink','Lower_Blink'):cmds.setKeyframe(eye.eye_direct_ctl+'.'+attr,time=frame,value=frame/16.)
joints=sorted(cmds.ls('L_*Eyelid*Skinning_JNT',type='joint'))
def sample():return np.array([cmds.getAttr(j+'.worldMatrix[0]') for j in joints])
cmds.evaluationManager(mode='off')
reference={}
for frame in range(1,17):cmds.currentTime(frame);reference[frame]=sample()
eyelid_deboor_exact.install('L')
folder=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/docs/validation/eyelid_variants_20261016/exact_native_reopen')
folder.mkdir(exist_ok=True)
path=folder/'prototype.ma'
cmds.file(rename=str(path));cmds.file(save=True,type='mayaAscii',force=True)
cmds.file(str(path),open=True,force=True)
result={'cycles':cmds.cycleCheck(all=True,list=True) or [],'modes':{}}
for mode in ('off','serial','parallel'):
 cmds.evaluationManager(mode=mode)
 errors=[]
 for frame in list(range(1,17))+[16,12,7,1]:
  cmds.currentTime(frame)
  value=sample();errors.append(float(np.max(abs(value-reference[frame]))))
 result['modes'][mode]={'maximum':max(errors),'all_errors':errors,'finite':all(np.isfinite(errors))}
 print(mode,result['modes'][mode],flush=True)
(folder/'validation.json').write_text(json.dumps(result,indent=2))
