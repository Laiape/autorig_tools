"""Native single-surface jaw: regulated narrow, pose bank and binary reopen.

Controller drawing and cache writes are isolated; deformation uses real Maya nodes.
An optional BASELINE_SOURCE global compares a previous module across all 49 cases.
"""
import os,ast,math,json,tempfile,runpy
from pathlib import Path
from types import SimpleNamespace
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import maya.api.OpenMaya as om
import numpy as np
temp=tempfile.TemporaryDirectory(prefix='jaw_lips_test_');work=Path(temp.name);scripts=Path(__file__).resolve().parents[2]
fixture=json.loads((Path(__file__).parent/'fixtures/edward_lip_guides.json').read_text())
def create_controller(name,offset=None,parent=None,**unused):
 grp=cmds.createNode('transform',name=name+'_GRP',parent=parent) if parent else cmds.createNode('transform',name=name+'_GRP')
 off=cmds.createNode('transform',name=name+'_OFF',parent=grp)
 ctl=cmds.createNode('transform',name=name+'_CTL',parent=off)
 return [grp,off],ctl
def lock_attributes(node,attrs):
 for a in attrs:cmds.setAttr(node+'.'+a,lock=True,keyable=False)
def guides(name,parent=None):
 if name=='C_jaw_JNT':
  n=cmds.createNode('joint',name=name);cmds.xform(n,ws=True,t=fixture['jaw_position']);return [n]
 key=name.removesuffix('Shape');d=fixture['geometry'][key];p=om.MPointArray([om.MPoint(*v) for v in d['cvs']])
 if d['type']=='curve':obj=om.MFnNurbsCurve().create(p,om.MDoubleArray(d['knots']),d['degree'],d['form'],False,True)
 else:obj=om.MFnNurbsSurface().create(p,om.MDoubleArray(d['knotsU']),om.MDoubleArray(d['knotsV']),d['degreeU'],d['degreeV'],d['formU'],d['formV'],True)
 n=cmds.rename(om.MFnDagNode(obj).fullPathName(),key)
 if parent:cmds.parent(n,parent)
 return n
scope={'cmds':cmds,'om':om,'math':math,'os':os,'curve_tool':SimpleNamespace(create_controller=create_controller,lock_attributes=lock_attributes),'guides_manager':SimpleNamespace(get_guides=guides),'data_manager':SimpleNamespace(DataExportBiped=lambda:SimpleNamespace(append_data=lambda *a:None))}
scope['organize_module_nurbs']=runpy.run_path(str(scripts/'utils/module_nurbs.py'))['organize_module_nurbs']
mt=ast.parse((scripts/'utils/matrix_manager.py').read_text(encoding='utf-8'))
f=[n for n in mt.body if isinstance(n,ast.FunctionDef) and n.name=='getClosestParamsToPositionSurface'];ms={'cmds':cmds,'om':om};exec(compile(ast.Module(body=f,type_ignores=[]),'<matrix>','exec'),ms);scope['matrix_manager']=SimpleNamespace(getClosestParamsToPositionSurface=ms['getClosestParamsToPositionSurface'])
tree=ast.parse((scripts/'biped/autorig/jaw_module_nurbs.py').read_text(encoding='utf-8'));cl=next(n for n in tree.body if isinstance(n,ast.ClassDef));exec(compile(ast.Module(body=[cl],type_ignores=[]),'<jaw>','exec'),scope)
cmds.loadPlugin('matrixNodes',quiet=True);cmds.loadPlugin('lookdevKit',quiet=True)
cases=[('neutral',{})]
for angle in (5,20,30):cases.append(('jaw_'+str(angle),{'C_jaw_CTL.rx':angle}))
for side in ('L','R'):
 for angle in (0,20,30):
  for value in (.25,.5,1):cases.append((side+'_narrow_'+str(angle)+'_'+str(value),{'C_jaw_CTL.rx':angle,side+'_lipCorner_CTL.autoNarrow':value}))
 for axis in ('tx','ty','tz','rx','ry','rz'):
  for sign in (-1,1):cases.append((side+'_'+axis+str(sign),{'C_jaw_CTL.rx':20,side+'_lipCorner_CTL.'+axis:sign*(1 if axis.startswith('t') else 20)}))
for value in (0,.5,1):cases.append(('sticky_'+str(value),{'C_jaw_CTL.rx':30,'C_jaw_CTL.stickyLips':value,'L_lipCorner_CTL.autoNarrow':.5,'R_lipCorner_CTL.autoNarrow':.5}))
plugs=set(p for _,values in cases for p in values)

def build(source):
 cmds.file(new=True,force=True);cmds.evaluationManager(mode='off')
 tree=ast.parse(Path(source).read_text(encoding='utf-8'));cl=next(n for n in tree.body if isinstance(n,ast.ClassDef));exec(compile(ast.Module(body=[cl],type_ignores=[]),str(source),'exec'),scope)
 obj=scope['JawModule'].__new__(scope['JawModule'])
 for field in ['modules','skel_grp','masterwalk_ctl','face_ctl','head_ctl']:setattr(obj,field,cmds.createNode('transform',name=field))
 obj.face_controls_parent=obj.face_ctl;obj.make('C');return obj

def samples():
 joints=sorted(set(cmds.ls('*upperLip*_JNT','*lowerLip*_JNT',type='joint')))
 rest={p:cmds.getAttr(p) for p in plugs};data={}
 for name,values in cases:
  for p,v in values.items():cmds.setAttr(p,v)
  points=np.asarray([cmds.xform(j,q=True,ws=True,matrix=True) for j in joints])
  assert np.isfinite(points).all(),name
  data[name]=points
  for p in values:cmds.setAttr(p,rest[p])
 return data

try:
 original=globals().get('BASELINE_SOURCE')
 baseline=None
 if original:
  build(original);baseline=samples()
 current=scripts/'biped/autorig/jaw_module_nurbs.py'
 obj=build(current)
 assert not cmds.objExists('C_jawStatic_NURB')
 assert not cmds.ls('*Static_CPS',type='closestPointOnSurface')
 projectors=('C_upperLipLocal_CPS','C_lowerLipLocal_CPS','L_lowerLipLocal_CPS','R_lowerLipLocal_CPS')
 sources={cmds.connectionInfo(n+'.inputSurface',sourceFromDestination=True) for n in projectors}
 assert len(sources)==1,sources
 for side in ('L','R'):
  attr=side+'_lipCorner_CTL.autoNarrow'
  assert cmds.getAttr(attr)==0 and cmds.getAttr(attr,keyable=True)
  assert not cmds.getAttr(attr,lock=True)
 actual=samples();maximum=0.
 if baseline:
  maximum=max(float(np.max(np.abs(actual[k]-baseline[k]))) for k in actual)
  assert maximum<1e-4,maximum
 path=work/'single_surface.mb';cmds.file(rename=str(path));cmds.file(save=True,type='mayaBinary')
 cmds.file(new=True,force=True);cmds.file(str(path),open=True,force=True)
 reopened=samples();reopen_error=max(float(np.max(np.abs(actual[k]-reopened[k]))) for k in actual)
 assert reopen_error<1e-6,reopen_error
 assert not cmds.objExists('C_jawStatic_NURB')
 print('PASS single jaw projection surface; regulated narrow, opening, independent corner transforms and sticky lips')
 print(json.dumps({'cases':len(cases),'projectors':len(projectors),'baseline_max_matrix_error':maximum if baseline else None,'reopen_max_matrix_error':reopen_error}),flush=True)
finally:
 maya.standalone.uninitialize();temp.cleanup()
