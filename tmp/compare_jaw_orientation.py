"""Disposable second-pass jaw audit. Does not touch the artist scene or source."""
import sys, json, time, statistics, hashlib, importlib.util
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(r'C:/proyectos/auto-rig/autorig_tools')
OUT=Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015')
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'maya_tools/scripts/tools/tests'))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds, mel
from maya.api import OpenMaya as om
from fixtures.jaw_scene import build,SOURCE
spec=importlib.util.spec_from_file_location('jaw_bench',ROOT/'scripts/benchmark_jaw_graph.py')
bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
cases=[(name,{k:v for k,v in values.items() if not k.endswith('.autoWideDepth')}) for name,values in bench.pose_bank()]
def readers():
 names=sorted(set((cmds.ls(type='joint') or [])+(cmds.ls('*Lip*_GRP',type='transform') or [])))
 plugs=[om.MSelectionList().add(n+'.worldMatrix[0]').getPlug(0) for n in names]
 return names,lambda:np.array([list(om.MFnMatrixData(p.asMObject()).matrix()) for p in plugs])

def capture():
 names,read=readers();defaults={p:cmds.getAttr(p) for _,v in cases for p in v};last={};data=[]
 for name,values in cases:
  for p in last:cmds.setAttr(p,defaults[p])
  for p,v in values.items():cmds.setAttr(p,v)
  data.append(read());last=values
 for p in last:cmds.setAttr(p,defaults[p])
 return names,np.array(data)

def measure():
 _,read=readers();times={}
 for scenario in ('jaw','corner','fine','mixed'):
  for p in ('C_jaw_CTL.rx','C_jaw_CTL.stickyLips','L_lipCorner_CTL.ty','R_lipCorner_CTL.ty','L_upperLip02_CTL.tx','R_lowerLip02_CTL.tx'):
   cmds.setAttr(p,0)
  for sweep in range(2):
   start=time.perf_counter()
   for step in range(24):
    if scenario in ('jaw','mixed'):cmds.setAttr('C_jaw_CTL.rx',step%31)
    if scenario in ('corner','mixed'):
     cmds.setAttr('L_lipCorner_CTL.ty',(step%9-4)*.2)
     cmds.setAttr('L_lipCorner_CTL.tx',(step%9-4)*.15)
    if scenario in ('fine','mixed'):
     cmds.setAttr('L_upperLip02_CTL.tx',(step-12)*.03)
     cmds.setAttr('R_lowerLip02_CTL.tx',(12-step)*.03)
    if scenario=='mixed':cmds.setAttr('C_jaw_CTL.stickyLips',step%7/6.)
    read()
   times[scenario]=(time.perf_counter()-start)/24*1000
 return times



report={'samples':[],'purpose':'Native orientation candidate; exact artist snapshot baseline, current source, all joint/control matrices. No mesh/viewport timing.'}
try:
 for kind,path in [('before',OUT/'baseline.py'),('after',OUT/'candidate.py')]:
  build(path)
  names,data=capture()
  report[kind]={'nodes':len(cmds.ls()),'node_types':dict(Counter(cmds.nodeType(n) for n in cmds.ls()))}
  if kind=='before':before=data;before_names=names
  else:
   assert names==before_names
   error=np.abs(before-data)
   report['maximum_matrix_error']=float(error.max())
   worst=np.unravel_index(np.argmax(error),error.shape)
   report['worst']={'pose':cases[worst[0]][0],'node':names[worst[1]]}
   assert error.max()<1e-5,report
 report['unique_poses']=len(set(tuple(sorted(v.items())) for _,v in cases))
 print('COMPATIBILITY',json.dumps(report),flush=True)
 for kind in ('before','after','after','before')*2:
  build(OUT/('baseline.py' if kind=='before' else 'candidate.py'))
  sample={'kind':kind,'ms':measure()};report['samples'].append(sample)
  print('SAMPLE',json.dumps(sample),flush=True)
 for kind in ('before','after'):
  report[kind]['median_ms']={s:statistics.median(r['ms'][s] for r in report['samples'] if r['kind']==kind) for s in ('jaw','corner','fine','mixed')}
 report['cycles']=cmds.cycleCheck(all=True,list=True) or []
 report['success']=True
finally:
 (OUT/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('RESULT',json.dumps(report),flush=True)
