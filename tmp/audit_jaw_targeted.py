"""Disposable second-pass jaw audit. Does not touch the artist scene or source."""
import sys, json, time, statistics, hashlib, importlib.util
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(r'C:/proyectos/auto-rig/autorig_tools')
OUT=Path(r'C:/proyectos/auto-rig/tmp/jaw_second_audit_20261015')
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
KINDS={'multiply','sum','subtract','divide','multiplyDivide','plusMinusAverage','composeMatrix','multMatrix','pickMatrix','inverseMatrix','blendMatrix','translationFromMatrix','vectorProduct','remapValue','condition','clamp','distanceBetween','blendColors','wtAddMatrix','unitConversion'}
SKIP={'message','caching','frozen','isHistoricallyInteresting','binMembership'}
def freeze(v):
 if isinstance(v,(list,tuple)): return tuple(freeze(i) for i in v)
 return v

def value(p):
 if p.isDestination:return ('source',p.source().name())
 if p.isArray:return ('array',tuple((p.elementByPhysicalIndex(i).logicalIndex(),value(p.elementByPhysicalIndex(i))) for i in range(p.evaluateNumElements())))
 if p.isCompound:return ('children',tuple(value(p.child(i)) for i in range(p.numChildren())))
 return ('value',freeze(cmds.getAttr(p.name())))

def key(n):
 obj=om.MSelectionList().add(n).getDependNode(0);fn=om.MFnDependencyNode(obj)
 inputs=[]
 for i in range(fn.attributeCount()):
  a=fn.attribute(i);fa=om.MFnAttribute(a)
  if not fa.writable or fa.parent!=om.MObject.kNullObj or fa.name in SKIP or a.hasFn(om.MFn.kMessageAttribute): continue
  try: inputs.append((fa.name,value(om.MPlug(obj,a))))
  except (RuntimeError,TypeError): return None
 return (cmds.nodeType(n),tuple(inputs))

def reduce_graph():
 merges=[]
 debug_names,debug_read=readers()
 debug_rest=debug_read()
 for step in range(6):
  cache={};found=0
  for n in cmds.ls():
   if cmds.nodeType(n) not in KINDS:continue
   k=key(n)
   if k is None:continue
   if k not in cache:cache[k]=n;continue
   keep=cache[k]
   pairs=cmds.listConnections(n,s=False,d=True,c=True,p=True,skipConversionNodes=False) or []
   for src,dst in zip(pairs[::2],pairs[1::2]):
    replacement=keep+src[len(n):]
    cmds.connectAttr(replacement,dst,force=True)
   merges.append({'removed':n,'kept':keep,'type':cmds.nodeType(n)})
   cmds.delete(n);found+=1
   error=float(np.max(np.abs(debug_read()-debug_rest)))
   if error>1e-8:
    print('BAD_MERGE',n,keep,'error',error,'key',repr(k),flush=True)
    raise RuntimeError('bad merge '+n)
  if not found:break
 return merges

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


source=SOURCE.read_text(encoding='utf-8')
variant=source.replace('key = (corner_side, k)','key = corner_side')
variant=variant.replace('                    key = corner_side','                    if w <= 1e-12:\n                        continue\n                    key = corner_side')
variant=variant.replace('        for part in ["upper", "lower"]:', '        shared_roll = {}\n        for part in ["upper", "lower"]:')
start=variant.index('                roll_mul = cmds.createNode("multiply", name=f"{out_joint}_Roll_MUL"')
end=variant.index('        # ------ Conditions to control visibility',start)
variant=variant[:start]+'                if roll_factor == 0.0:\n                    cmds.setAttr(out_joint + ".rotateX", 0)\n                else:\n                    key = (part, roll_factor)\n                    if key not in shared_roll:\n                        roll_mul = cmds.createNode("multiply", name=f"{out_joint}_Roll_MUL", ss=True)\n                        cmds.connectAttr(roll_drive + ".output1D", roll_mul + ".input[0]")\n                        cmds.setAttr(roll_mul + ".input[1]", roll_factor)\n                        shared_roll[key] = roll_mul + ".output"\n                    cmds.connectAttr(shared_roll[key], out_joint + ".rotateX", force=True)\n\n'+variant[end:]
variant_path=OUT/'jaw_candidate.py';variant_path.write_text(variant,encoding='utf-8')
report={'purpose':'Targeted source candidate in disposable jaw fixture, DG all joint/control-group matrix queries; no mesh or viewport timings. Share corner frames and mirrored Roll; remove zero-weight corner blends.','samples':[],'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
try:
 build(SOURCE);report['before_nodes']=len(cmds.ls());names,before=capture()
 build(variant_path);report['after_nodes']=len(cmds.ls());new_names,after=capture();assert names==new_names
 error=np.abs(before-after);worst=np.unravel_index(np.argmax(error),error.shape)
 report.update(poses=len(cases),unique_poses=len(set(tuple(sorted(v.items())) for _,v in cases)),matrices_per_pose=len(names),maximum_matrix_error=float(error.max()),worst={'pose':cases[worst[0]][0],'node':names[worst[1]]})
 assert error.max()<1e-8,report
 print('COMPATIBILITY',json.dumps(report),flush=True)
 for kind in ('before','after','after','before')*2:
  build(SOURCE if kind=='before' else variant_path)
  sample={'kind':kind,'ms':measure()};report['samples'].append(sample);print('SAMPLE',json.dumps(sample),flush=True)
 for kind in ('before','after'):
  report[kind+'_median_ms']={s:statistics.median(r['ms'][s] for r in report['samples'] if r['kind']==kind) for s in ('jaw','corner','fine','mixed')}
 report['cycles']=cmds.cycleCheck(all=True,list=True) or []
 report['success']=True
finally:
 (OUT/'targeted_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('RESULT',json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)
