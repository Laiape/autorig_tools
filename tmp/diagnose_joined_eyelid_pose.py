import sys,json
from pathlib import Path
sys.path.insert(0,'C:/proyectos/auto-rig/autorig_tools')
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
cmds.file('C:/proyectos/auto-rig/recovery/eyelids_large_roll_before_20261016_v001.mb',open=True,force=True,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
from maya_tools.scripts.tools import eyelid_rotation
for prefix in ('L','R'):eyelid_rotation.install(prefix)
result={'cases':{}}
nodes=sorted(cmds.ls('L_*Eyelid*Skinning_JNT',type='joint'))
ups=sorted([n for n in nodes if '_upper' in n],key=lambda n:int(n.split('Eyelid0')[1].split('Skinning')[0]))
downs=sorted([n for n in nodes if '_down' in n],key=lambda n:int(n.split('Eyelid0')[1].split('Skinning')[0]))
def point(n):return np.array(cmds.xform(n,q=True,ws=True,t=True))
for angle,ty in ((0,0),(-25.2410641506,-.2103800141),(-45,0),(-75,0),(75,0)):
 cmds.setAttr('L_eyelidDown_CTL.rz',angle);cmds.setAttr('L_eyelidDown_CTL.ty',ty)
 rows=[]
 for i in (0,len(ups)-1):
  a,b=point(ups[i]),point(downs[i])
  rows.append({'index':i,'upper':a.tolist(),'lower':b.tolist(),'gap':float(np.linalg.norm(a-b))})
 result['cases'][str(angle)]={'corners':rows}
 print('CASE',angle,ty,rows,flush=True)
path=Path('C:/proyectos/auto-rig/tmp/large_eyelid_joined_diagnosis.json')
path.write_text(json.dumps(result,indent=2))
