import os
from pathlib import Path
import json,sys,time,traceback
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016')
os.environ['AUTORIG_BUILD_CACHE_DIR']=str(base/'build_cache')
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.cmds as cmds
cmds.optionVar(sv=('currentAssetRigName','chihuahua'))
from maya_tools.scripts.utils import create_rig
start=time.time()
try:
 create_rig.AutoRig().build(leg_impl='self')
 result={'success':True,'seconds':time.time()-start,'joints':cmds.ls(type='joint'),'controls':cmds.ls('*_CTL',type='transform'),'scene':cmds.file(q=True,sn=True)}
 checks={}
 for n in cmds.ls(type='transform')+cmds.ls(type='joint'):
  if any(t in n for t in ('spine','neck','head','eye','ear','pelvis','frontLeg','backLeg')) and not any(t in n for t in ('GRP','SPC','ANM','OFF','NET','GUIDE','NURB','CRV')):
   checks[n]=cmds.xform(n,q=True,ws=True,m=True)
 result['matrices']=checks
 scene=base/'candidate.mb'
 cmds.file(rename=str(scene));cmds.file(save=True,type='mayaBinary',force=True)
 result['candidate']=str(scene)
except BaseException:
 result={'success':False,'seconds':time.time()-start,'traceback':traceback.format_exc()}
(base/'build_result.json').write_text(json.dumps(result,indent=2))
print('RESULT',result.get('success'),result.get('seconds'),result.get('traceback',''),flush=True)
if not result['success']:raise RuntimeError(result['traceback'])
