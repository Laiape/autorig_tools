import sys
sys.path[:0]=['C:/proyectos/auto-rig/autorig_tools','C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/tools/tests']
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from test_eyelid_blink import build
from maya_tools.scripts.tools import eyelid_deboor_exact as ex
from maya_tools.scripts.utils import de_boor_core as db
for plugin in ('matrixNodes','lookdevKit'):cmds.loadPlugin(plugin,quiet=True)
ctl=cmds.createNode('transform')
cmds.addAttr(ctl,ln='u',at='double')
cmds.addAttr(ctl,ln='value',at='double')
k=db.get_open_uniform_knot_vector(7,3)
c=[0,0,1,0,0,0,0]
ex.coefficient(ctl+'.value',ctl+'.u',c,3,k,'coefficient')
for u in (0,.1,.25,.4,.5,.75,.9,1):
 cmds.setAttr(ctl+'.u',u)
 print('COEFF',u,cmds.getAttr(ctl+'.value'),db.de_boor(7,3,u,k)[2],flush=True)
eye=build('L',True)
ex.install('L')
for blink in (0,.2,.7,1):
 for attr in ('Upper_Blink','Lower_Blink'):cmds.setAttr(eye.eye_direct_ctl+'.'+attr,blink)
 errors=[]
 worst=None
 for path in cmds.ls('L_*Eyelid*_MTP',type='motionPath'):
  stem=path[:-4]
  u=cmds.getAttr(stem+'ContactU_BTA.output')
  for label,curve in (('Upper','Up'),('Lower','Down')):
   a=np.array(cmds.getAttr(stem+'Exact'+label+'_PMA.output3D'))[0]
   b=np.array(cmds.pointOnCurve('L_eyelid'+curve+'Pose_CRV',pr=u,p=True))
   errors.append(float(np.max(abs(a-b))))
   if worst is None or errors[-1]>worst[0]:worst=(errors[-1],stem,label,u,a.tolist(),b.tolist())
   if blink==0 and path.endswith('00_MTP') and label=='Upper':
    print('DETAIL',path,u,a.tolist(),b.tolist(),flush=True)
    for md in cmds.ls(stem+'ExactUpperInfluence*_MD'):
     print('WEIGHT',md,cmds.getAttr(md+'.input1'),cmds.getAttr(md+'.input2'),cmds.getAttr(md+'.output'),flush=True)
 print('RAW_EXACT',blink,max(errors),flush=True)
 if blink==0:
  print('WORST',worst,flush=True)
  rawstem=worst[1]+'Exact'+worst[2]
  for pmm in cmds.ls(rawstem+'Influence*_PMM'):
   md=pmm.replace('_PMM','_MD')
   print('PART',pmm,cmds.getAttr(pmm+'.inPoint'),cmds.getAttr(pmm+'.output'),cmds.getAttr(md+'.input2'),cmds.getAttr(md+'.output'),flush=True)
