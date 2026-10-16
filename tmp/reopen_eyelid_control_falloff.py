import json,sys
from pathlib import Path
sys.path.insert(0,'C:/proyectos/auto-rig/autorig_tools')
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from maya_tools.scripts.tools import eyelid_corners,eyelid_contact
path='C:/proyectos/auto-rig/recovery/Edward_eyelids_soft_ends_20261016_v001.mb'
cmds.file(path,open=True,force=True,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
assert all(eyelid_corners.current(side) for side in ('L','R'))
assert not eyelid_contact.upgrade(['L_eyeDirect_CTL','R_eyeDirect_CTL'])
errors={}
for side in ('L','R'):
 cmds.setAttr(side+'_eyelidDown_CTL.rz',60)
 for attr in ('Upper_Blink','Lower_Blink'):cmds.setAttr(side+'_eyeDirect_CTL.'+attr,1)
 a=np.array([cmds.getAttr(side+'_upperEyelid0%dSkinning_JNT.worldMatrix[0]'%i) for i in range(21)])
 b=np.array([cmds.getAttr(side+'_downEyelid0%dSkinning_JNT.worldMatrix[0]'%i) for i in range(21)])
 errors[side]=float(np.max(abs(a-b)))
 assert np.isfinite(a).all() and errors[side]<1e-4
result={'file':path,'closed_matrix_errors':errors,'versions':3,'idempotent':True}
Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/docs/validation/eyelid_control_falloff_20261016/final_reopen.json').write_text(json.dumps(result,indent=2))
print('PASS FINAL COPY REOPEN',result,flush=True)
