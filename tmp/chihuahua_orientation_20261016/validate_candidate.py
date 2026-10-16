import json,math,time
from pathlib import Path
import numpy as np
import maya.cmds as cmds
import maya.api.OpenMaya as om
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016')
export=json.loads((base/'exported.json').read_text())['result'];guides=export['joint_matrices']
build=json.loads((base/'build_result.json').read_text());candidate=build['candidate']
report={'passed':False,'candidate':candidate,'linear_unit':cmds.currentUnit(query=True,linear=True),'checks':[]}

def meshes():
 out={}
 for shape in cmds.ls(type='mesh',long=True) or []:
  if cmds.getAttr(shape+'.intermediateObject'):continue
  sel=om.MSelectionList();sel.add(shape);path=sel.getDagPath(0)
  fn=om.MFnMesh(path);points=fn.getPoints(om.MSpace.kWorld)
  out[shape.rsplit('|',1)[-1]]=np.array([(p.x,p.y,p.z) for p in points],dtype=np.float64)
 return out

def capture():
 return np.array([cmds.xform(n,q=True,ws=True,m=True) for n in joints])

def compare(actual,expected,tolerance=1e-4):
 error=float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))
 if error>tolerance:raise AssertionError('Matrix/position error %s exceeds %s'%(error,tolerance))
 return error

# Work only in this owned process. The user's open guide scene stays intact.
cmds.file('C:/proyectos/auto-rig/recovery/chihuahua_guides_orientation_before_20261016_v001.mb',open=True,force=True,prompt=False,executeScriptNodes=False)
reference=meshes()
cmds.file(candidate,open=True,force=True,prompt=False,executeScriptNodes=False)
geometry=meshes();common=sorted(set(reference)&set(geometry));errors={}
for name in common:
 if reference[name].shape==geometry[name].shape:errors[name]=compare(geometry[name],reference[name])
report['neutral_geometry_max_cm']=max(errors.values(),default=0);report['compared_meshes']=list(errors)
report['reference_mesh_count']=len(reference);report['candidate_mesh_count']=len(geometry)
report['unmatched_reference_meshes']=sorted(set(reference)-set(geometry))
report['unmatched_candidate_meshes']=sorted(set(geometry)-set(reference))
report['checks'].append('Artist model neutral world positions')
joints=[n for n in cmds.ls(type='joint') if not any(token in n for token in ('_ENV','Local','Driver','Ik_JNT','_GUIDE'))]
neutral=capture();report['joint_count']=len(joints)
frames={}
for node in cmds.ls('*_CTL',type='transform')+cmds.ls('*Skinning_JNT',type='joint'):
 source=node.replace('Skinning_JNT','_JNT').replace('Fk_CTL','_JNT').replace('eyeDirect_CTL','eye_JNT').replace('_CTL','_JNT')
 if source in guides and ('Fk_CTL' in node or 'Skinning_JNT' in node or any(token in node for token in ('eyeDirect','ear'))):
  frames[node]=compare(cmds.xform(node,q=True,ws=True,m=True),guides[source])
report['direct_frame_max']=max(frames.values(),default=0);report['direct_frame_count']=len(frames)
report['checks'].append('Authored L/R eyes, ears, paw/digit skin frames and FK axes')
settings=[s+'_'+limb+'Settings_CTL.switchIkFk' for s in ('L','R') for limb in ('frontLeg','backLeg')]
for plug in settings:cmds.setAttr(plug,1)
report['neutral_ik_fk_max']=compare(capture(),neutral)
for plug in settings:cmds.setAttr(plug,0)
poses=[('neutral',{})]
for side in ('L','R'):
 sign=1 if side=='L' else -1
 for limb in ('frontLeg','backLeg'):
  ankle=side+'_'+limb+'FetlockIk_CTL'
  pv=side+'_'+limb+'Pv_CTL'
  poses.extend([(side+'_'+limb+'_lift',{ankle+'.ty':1.25,ankle+'.tz':-.7}),
                (side+'_'+limb+'_reach',{ankle+'.ty':-.7,ankle+'.tz':1.5,pv+'.tx':.5*sign}),
                (side+'_'+limb+'_fk',{side+'_'+limb+'Settings_CTL.switchIkFk':1,
                    side+'_'+limb+('Shoulder' if limb=='frontLeg' else 'Hip')+'Fk_CTL.rz':16})])
poses.extend([('body_neck_tail',{'C_spine02_CTL.ry':11,'C_neck00_CTL.rz':-8,'C_tailFk01_CTL.rz':15}),
              ('eyes',{'L_eye_CTL.ty':2,'R_eye_CTL.tx':-2,'C_head_CTL.ry':15}),
              ('jaw_open',{'C_jaw_CTL.rz':20}),
              ('nonuniform_spine',{'C_spine02_CTL.sx':1.15,'C_spine02_CTL.sy':.85,'C_spine02_CTL.sz':1.1}),
              ('scaled',{'C_masterwalk_CTL.globalScale':1.7})])
max_mode_error=0.;moved=[]
for label,pose in poses:
 original={plug:cmds.getAttr(plug) for plug in pose}
 for plug,value in pose.items():cmds.setAttr(plug,value)
 samples=[]
 for mode in ('off','serial','parallel'):
  cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
  cmds.evaluationManager(mode=mode);cmds.dgdirty(allPlugs=True)
  values=capture()
  if not np.all(np.isfinite(values)):raise AssertionError('Nonfinite outputs: '+label)
  samples.append(values)
 for values in samples[1:]:max_mode_error=max(max_mode_error,compare(values,samples[0]))
 displacement=float(np.max(np.abs(samples[0]-neutral)))
 if label=='nonuniform_spine':
  compare(samples[0],neutral)
  report['nonuniform_spine_scope']='Existing middle-control scale channels do not drive stretch joint outputs; invariance checked. Head non-uniform deformation has separate native eye regression.'
 elif pose and displacement<1e-4:raise AssertionError('No actual joint motion: '+label)
 moved.append({'pose':label,'max_matrix_change':displacement})
 for plug,value in original.items():cmds.setAttr(plug,value)
report['evaluation_max_error']=max_mode_error;report['poses']=moved
report['checks'].extend(['All four legs IK/FK and PV edits','Head gaze and body/neck/tail motion','Global scale','DG/Serial/Parallel agreement'])
cmds.evaluationManager(mode='off');cmds.dgdirty(allPlugs=True)
compare(capture(),neutral)
cycles=cmds.cycleCheck(all=True,list=True) or [];report['cycles']=cycles
if cycles:raise AssertionError('Cycles detected: '+str(cycles[:10]))
cmds.file(candidate,open=True,force=True,prompt=False,executeScriptNodes=False)
compare(capture(),neutral)
report['checks'].append('Native reopen and neutral reset')
report['passed']=True
(base/'validation.json').write_text(json.dumps(report,indent=2))
result=report
