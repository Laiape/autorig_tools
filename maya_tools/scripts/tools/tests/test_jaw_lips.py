"""Run with mayapy. Builds the production jaw with Edward guide data and isolated controls.

Controller drawing and asset cache writes are stubbed; deformers, pins and matrices
are real Maya nodes. Checks O profile, ordered pins and independent corners.
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
try:
 cmds.loadPlugin('matrixNodes',quiet=True);cmds.loadPlugin('lookdevKit',quiet=True)
 cmds.file(new=True,force=True);cmds.evaluationManager(mode='off')
 obj=scope['JawModule'].__new__(scope['JawModule'])
 for field in ['modules','skel_grp','masterwalk_ctl','face_ctl','head_ctl']:setattr(obj,field,cmds.createNode('transform',name=field))
 obj.face_controls_parent=obj.face_ctl;obj.make('C')
 module_path=cmds.ls(obj.module_trn,long=True)[0]
 for shape in cmds.ls(type=['nurbsCurve','nurbsSurface'],long=True):
  assert shape.startswith(module_path+'|'),('Construction NURBS outside jaw module',shape)
 for values in [[0,.0166,.0083,.0523,1],[0,.2,.1,.15,.5,1],[0,0,.5,1]]:
  repaired=obj._ordered_lip_parameters(values);assert all(a<b for a,b in zip(repaired,repaired[1:])),repaired
 for c in cmds.ls('*Lip*CTL','*lip*CTL'):
  for attr in ['PushOut','StretchVolume','SurfaceDepthFollow']:assert not cmds.objExists(c+'.'+attr),(c,attr)
 for part in ['upper','lower']:
  pin='C_'+part+'LipAimVector_UVP';u=[cmds.getAttr(pin+'.coordinate[%d].coordinateU'%i) for i in range(25)];assert all(a<b for a,b in zip(u,u[1:])),u
 records=[]
 for angle in [0,5,10,20,30]:
  cmds.setAttr('C_jaw_CTL.rx',angle)
  parts=[]
  for part in ['upper','lower']:
   parts.append(np.asarray([cmds.xform(('R_' if i<12 else 'C_' if i==12 else 'L_')+part+'Lip%02d_JNT'%(i if i<12 else 0 if i==12 else 24-i),q=True,ws=True,t=True) for i in range(25)]))
  upper,lower=parts;gap=upper[:,1]-lower[:,1]
  records.append({'angle':angle,'gap':gap.tolist(),'points_upper':upper.tolist(),'points_lower':lower.tolist(),'width':float(np.ptp((upper[:,0]+lower[:,0])*.5)),'height':float(upper[:,1].max()-lower[:,1].min())})
  assert np.isfinite(parts).all()
  if angle>=10:assert gap[12]>gap[1] and gap[12]>0
 assert .8<records[-1]['width']/records[-1]['height']<1.2
 assert records[-1]['gap'][6]/records[-1]['gap'][12]>.75
 cmds.setAttr('C_jaw_CTL.rx',0)
 opposite=cmds.xform('R_upperLip00_JNT',q=True,ws=True,t=True)
 cmds.setAttr('L_lipCorner_CTL.tx',1)
 assert np.allclose(opposite,cmds.xform('R_upperLip00_JNT',q=True,ws=True,t=True),atol=1e-6)
 assert all(np.allclose(cmds.getAttr(j+'.scale')[0],[1,1,1]) for j in cmds.ls('*Lip*NonRot_JNT'))
 cmds.setAttr('L_lipCorner_CTL.tx',0)
 # Corner translation is independent from the O-opening profile: paired
 # upper/lower stations must receive the same broad, smooth displacement.
 def lip_positions(part):
  return np.asarray([cmds.xform(('R_' if i<12 else 'C_' if i==12 else 'L_')+part+'Lip%02d_JNT'%(i if i<12 else 0 if i==12 else 24-i),q=True,ws=True,t=True) for i in range(25)])
 # Auto Narrow is a calibrated inward move, sharing the existing smooth,
 # paired upper/lower corner falloff without pulling the opposite half.
 for side in ['L','R']:
  corner=side+'_lipCorner_CTL';attr=corner+'.autoNarrow'
  assert cmds.getAttr(attr)==0 and cmds.getAttr(attr,keyable=True)
  assert not cmds.getAttr(attr,lock=True)
  coefficients=np.array(cmds.getAttr(side+'_lipOutFrac_VPR.input2')[0])
  inward=-.25*coefficients/np.dot(coefficients,coefficients)
  endpoint_index=24 if side=='L' else 0
  opposite_half=slice(0,13) if side=='L' else slice(12,25)
  for angle in [0,20,30]:
   cmds.setAttr('C_jaw_CTL.rx',angle)
   rest={part:lip_positions(part) for part in ['upper','lower']}
   for value in [.25,.5,1.]:
    cmds.setAttr(attr,value)
    posed={part:lip_positions(part) for part in rest}
    delta={part:posed[part]-rest[part] for part in rest}
    assert np.allclose(delta['upper'],delta['lower'],atol=1e-5),(side,angle,value)
    assert np.allclose(delta['upper'][opposite_half],0,atol=1e-5),(side,angle,value)
    endpoint=delta['upper'][endpoint_index]
    assert endpoint[0]*(-1 if side=='L' else 1)>.001,(side,angle,value,endpoint)
    for index in range(13):
     station_index=24-index if side=='L' else index
     assert np.allclose(delta['upper'][station_index][[0,2]],obj._corner_drag_weight(index/12.)*endpoint[[0,2]],atol=1e-5)
    assert all(np.isfinite(p).all() and np.all(np.diff(p[:,0])>0) for p in posed.values()),(side,angle,value)
    cmds.setAttr(attr,0)
    cmds.setAttr(corner+'.translate',*(inward*value))
    assert all(np.allclose(lip_positions(part),posed[part],atol=1e-5) for part in rest)
    cmds.setAttr(corner+'.translate',0,0,0)
    assert all(np.allclose(lip_positions(part),rest[part],atol=1e-5) for part in rest)
 cmds.setAttr('C_jaw_CTL.rx',0)
 for angle in [0,20,30]:
  cmds.setAttr('C_jaw_CTL.rx',angle)
  rest={part:lip_positions(part) for part in ['upper','lower']}
  for axis in ['tx','ty']:
   for value in [-1.,1.,7.12]:
    cmds.setAttr('L_lipCorner_CTL.'+axis,value)
    delta={part:lip_positions(part)-rest[part] for part in rest}
    assert np.allclose(delta['upper'],delta['lower'],atol=1e-5),(angle,axis,value,delta)
    endpoint=delta['upper'][24]
    for i in range(12,25):
     weight=obj._corner_drag_weight((24-i)/12.)
     assert np.allclose(delta['upper'][i][[0,2]],weight*endpoint[[0,2]],atol=1e-5),(angle,axis,value,i)
    assert np.allclose(delta['upper'][:13],0,atol=1e-5)
    cmds.setAttr('L_lipCorner_CTL.'+axis,0)
 cmds.setAttr('C_jaw_CTL.rx',0)
 # Raised and widened corners form a rounded U: the middle slope is much
 # shallower than a V, while the endpoint and independent opening remain free.
 u_profiles=[]
 for jaw_angle in [0,10,20,30]:
  cmds.setAttr('C_jaw_CTL.rx',jaw_angle)
  for side in ['L','R']:
   cmds.setAttr(side+'_lipCorner_CTL.translate',5.2,2,0)
  middle=(lip_positions('upper')+lip_positions('lower'))*.5
  for half in [middle[:13][::-1],middle[12:]]:
   height=half[-1,1]-half[0,1]
   assert height>.1
   assert (half[2,1]-half[0,1])/height<.08,half
   near_slope=abs((half[1,1]-half[0,1])/(half[1,0]-half[0,0]))
   outer_slope=abs((half[-1,1]-half[-4,1])/(half[-1,0]-half[-4,0]))
   assert near_slope<.25*outer_slope,(near_slope,outer_slope)
   u_profiles.append({'jaw_angle':jaw_angle,'center_fraction':float((half[2,1]-half[0,1])/height),
                      'slope_ratio':float(near_slope/outer_slope)})
  # Preserve each primary's independent motion while the U correction is active.
  posed={part:lip_positions(part) for part in ['upper','lower']}
  for part,other in [('upper','lower'),('lower','upper')]:
   for value in [-1.,1.]:
    cmds.setAttr('C_'+part+'Lip_CTL.ty',value)
    assert np.allclose(lip_positions(other),posed[other],atol=1e-5),(jaw_angle,part,value)
    assert np.linalg.norm(lip_positions(part)[12]-posed[part][12])>.01
   cmds.setAttr('C_'+part+'Lip_CTL.ty',0)
   assert np.allclose(lip_positions(part),posed[part],atol=1e-5)
  for side in ['L','R']:
   cmds.setAttr(side+'_lipCorner_CTL.translate',0,0,0)
 cmds.setAttr('C_jaw_CTL.rx',0)
 # Primary vertical motion has a flat, gradual middle independently of jaw
 # opening, while the opposite lip and endpoints retain their positions.
 for part in ['upper','lower']:
  other='lower' if part=='upper' else 'upper'
  for angle in [0,20]:
   cmds.setAttr('C_jaw_CTL.rx',angle)
   rest=lip_positions(part);opposite=lip_positions(other)
   for value in [-2.5,1.,2.5]:
    cmds.setAttr('C_'+part+'Lip_CTL.ty',value)
    delta=lip_positions(part)-rest
    assert np.allclose(opposite,lip_positions(other),atol=1e-5)
    assert np.allclose(delta[[0,24]],0,atol=1e-4),(part,angle,value,delta[[0,24]])
    center=np.linalg.norm(delta[12]);assert center>.01
    assert np.linalg.norm(delta[11])/center>.999
    assert np.linalg.norm(delta[13])/center>.999
    cmds.setAttr('C_'+part+'Lip_CTL.ty',0)
 cmds.setAttr('C_jaw_CTL.rx',0)
 # Corner rotation must reshape both lip arcs, including stations well beyond
 # the endpoint orientation blend. Check both sides and jaw-follow poses.
 for corner_side in ['L','R']:
  corner=corner_side+'_lipCorner_CTL'
  affected=slice(15,23) if corner_side=='L' else slice(2,10)
  other_endpoint=0 if corner_side=='L' else 24
  own_endpoint=24-other_endpoint
  for attr in ['rx','ry','rz']:
   assert not cmds.getAttr(corner+'.'+attr,lock=True)
   assert cmds.getAttr(corner+'.'+attr,keyable=True)
  for jaw_angle in [0,20,30]:
   cmds.setAttr('C_jaw_CTL.rx',jaw_angle)
   rest={part:lip_positions(part) for part in ['upper','lower']}
   for axis in ['rx','ry','rz']:
    for angle in [-25.,25.]:
     cmds.setAttr(corner+'.'+axis,angle)
     for part in rest:
      posed=lip_positions(part)
      assert np.isfinite(posed).all()
      assert np.max(np.linalg.norm(posed[affected]-rest[part][affected],axis=1))>.01,(corner,jaw_angle,axis,part)
      assert np.allclose(posed[other_endpoint],rest[part][other_endpoint],atol=1e-5)
      assert np.allclose(posed[own_endpoint],rest[part][own_endpoint],atol=1e-5),(corner,jaw_angle,axis,part,posed[own_endpoint]-rest[part][own_endpoint])
     cmds.setAttr(corner+'.'+axis,0)
     assert all(np.allclose(lip_positions(part),rest[part],atol=1e-5) for part in rest)
 cmds.setAttr('C_jaw_CTL.rx',0)
 # Fine-control axes follow independent neighbouring base positions. Their
 # translation maps to the displayed axes without changing neutral ribbon poses.
 ctl='L_lowerLip02_CTL';grp='L_lowerLip02_GRP';driver='L_lowerLip02Driver_JNT'
 rest_orientation=np.asarray(cmds.getAttr(grp+'.worldMatrix[0]')).reshape(4,4)[:3,:3]
 cmds.setAttr('C_lowerLip_CTL.ty',2)
 orientation=np.asarray(cmds.getAttr(grp+'.worldMatrix[0]')).reshape(4,4)[:3,:3]
 assert not np.allclose(rest_orientation,orientation,atol=1e-3)
 assert np.allclose(orientation@orientation.T,np.eye(3),atol=1e-6)
 before=np.array(cmds.xform(driver,q=True,ws=True,t=True))
 cmds.setAttr(ctl+'.tx',.1)
 movement=np.array(cmds.xform(driver,q=True,ws=True,t=True))-before
 assert np.allclose(movement,.1*orientation[0],atol=1e-6),(movement,orientation[0])
 cmds.setAttr(ctl+'.tx',0);cmds.setAttr('C_lowerLip_CTL.ty',0)
 # Combined corner rotations respect rotateOrder and the displayed fine axes.
 # Translation still composes with rotation, and sticky can close rotated arcs.
 cmds.setAttr('C_jaw_CTL.rx',20)
 for order in range(6):
  cmds.setAttr('L_lipCorner_CTL.rotateOrder',order)
  cmds.setAttr('L_lipCorner_CTL.rotate',17,13,22)
  cmds.setAttr('R_lipCorner_CTL.rotate',-11,8,-19)
  cmds.setAttr('L_lipCorner_CTL.translate',.4,.3,.2)
  cmds.setAttr('C_lowerLip_CTL.ty',1)
  orientation=np.asarray(cmds.getAttr(grp+'.worldMatrix[0]')).reshape(4,4)[:3,:3]
  assert np.allclose(orientation@orientation.T,np.eye(3),atol=1e-6)
  before=np.array(cmds.xform(driver,q=True,ws=True,t=True))
  cmds.setAttr(ctl+'.tx',.1)
  movement=np.array(cmds.xform(driver,q=True,ws=True,t=True))-before
  assert np.allclose(movement,.1*orientation[0],atol=1e-6),(order,movement,orientation[0])
  cmds.setAttr(ctl+'.tx',0)
  cmds.setAttr('C_jaw_CTL.stickyLips',1)
  assert np.allclose(lip_positions('upper'),lip_positions('lower'),atol=1e-5)
  cmds.setAttr('C_jaw_CTL.stickyLips',0)
 for corner_side in ['L','R']:
  corner=corner_side+'_lipCorner_CTL'
  cmds.setAttr(corner+'.rotate',0,0,0)
  cmds.setAttr(corner+'.translate',0,0,0)
  cmds.setAttr(corner+'.rotateOrder',0)
 cmds.setAttr('C_lowerLip_CTL.ty',0);cmds.setAttr('C_jaw_CTL.rx',0)
 # Main-mouth motion must transform the rotated lips once, without changing
 # the corner pivot inside the module's deformation space.
 cmds.setAttr('L_lipCorner_CTL.rotate',17,13,22)
 cmds.setAttr('R_lipCorner_CTL.rotate',-11,8,-19)
 rest={part:lip_positions(part) for part in ['upper','lower']}
 cmds.setAttr('C_mainMouth_CTL.translate',1,.5,-.3)
 cmds.setAttr('C_mainMouth_CTL.rotate',9,-14,7)
 mouth_delta=np.asarray(cmds.getAttr('C_mainMouthDelta_MMX.matrixSum')).reshape(4,4)
 for part in rest:
  expected=np.c_[rest[part],np.ones(25)]@mouth_delta
  assert np.allclose(lip_positions(part),expected[:,:3],atol=1e-5),part
 cmds.setAttr('C_mainMouth_CTL.translate',0,0,0)
 cmds.setAttr('C_mainMouth_CTL.rotate',0,0,0)
 cmds.setAttr('L_lipCorner_CTL.rotate',0,0,0)
 cmds.setAttr('R_lipCorner_CTL.rotate',0,0,0)
 # Continuous corner rotations used to flip the fine-control and output frames
 # by 180 degrees between adjacent poses. Check the entire chain and its aim,
 # rather than just orthogonality at a few isolated poses.
 fine_aims=cmds.ls('*upperLip*Neighbor_AMX','*lowerLip*Neighbor_AMX')
 frame_plugs=[n+'.outputMatrix' for n in fine_aims]
 output_names=cmds.ls('*upperLip*_JNT','*lowerLip*_JNT')
 frame_plugs += [n+'.worldMatrix[0]' for n in output_names]
 for jaw_angle in [0,30]:
  cmds.setAttr('C_jaw_CTL.rx',jaw_angle)
  for corner_side in ['L','R']:
   corner=corner_side+'_lipCorner_CTL'
   for axis in ['rx','ry','rz']:
    previous=None
    for angle in range(-100,101):
     cmds.setAttr(corner+'.'+axis,angle)
     frames=[np.asarray(cmds.getAttr(p)).reshape(4,4)[:3,:3] for p in frame_plugs]
     assert all(np.isfinite(m).all() and np.allclose(m@m.T,np.eye(3),atol=1e-6) for m in frames)
     if previous is not None:
      assert all(np.trace(a@b.T)>2.8 for a,b in zip(frames,previous)),(jaw_angle,corner,axis,angle)
     previous=frames
     for aim,matrix in zip(fine_aims,frames):
      local=np.asarray(cmds.getAttr(aim+'.primaryInputAxis')[0])
      actual=local@matrix;actual/=np.linalg.norm(actual)
      target=np.asarray(cmds.getAttr(aim+'.primaryTargetVector')[0]);target/=np.linalg.norm(target)
      assert np.dot(actual,target)>.99999,(aim,angle,actual,target)
    cmds.setAttr(corner+'.'+axis,0)
 cmds.setAttr('C_jaw_CTL.rx',0)
 # Coincident targets and almost coincident targets keep finite frames.
 base=cmds.createNode('composeMatrix',name='neighborProbeBase')
 target=cmds.createNode('composeMatrix',name='neighborProbeTarget')
 cmds.setAttr(target+'.inputTranslateX',1)
 frame=obj._neighbor_lip_aim('neighborProbe',base+'.outputMatrix',target+'.outputMatrix')
 for distance in [1,.001,.000001,0]:
  cmds.setAttr(target+'.inputTranslateX',distance)
  matrix=np.asarray(cmds.getAttr(frame)).reshape(4,4)[:3,:3]
  assert np.isfinite(matrix).all() and np.allclose(matrix@matrix.T,np.eye(3),atol=1e-6)
 # Manual sticky matches the reference network and does not read jaw rx.
 assert not cmds.objExists('C_jaw_CTL.StickyRange')
 assert not cmds.objExists('C_jaw_CTL.StickyLips')
 assert cmds.getAttr('C_jaw_CTL.stickyLips')==0
 joint_names=[('R_' if i<12 else 'C_' if i==12 else 'L_')+'lowerLip%02d_JNT'%(i if i<12 else 0 if i==12 else 24-i) for i in range(25)]
 cmds.setAttr('C_jaw_CTL.rx',20)
 for falloff in [.001,.2,1.0]:
  cmds.setAttr('C_jaw_CTL.stickyFalloff',falloff)
  previous=None
  for driver in np.linspace(0,1,81):
   cmds.setAttr('C_jaw_CTL.stickyLips',float(driver))
   weights=np.array([cmds.getAttr(j.replace('_JNT','NonRot_JNT')+'StickyFalloff_RMV.outValue') for j in joint_names])
   expected=np.array([min(1.,driver/(min(i,24-i)/12.*.7+falloff)) for i in range(25)])
   assert np.allclose(weights,expected,atol=1e-6),(weights,expected)
   if previous is not None:assert np.all(weights>=previous-1e-8)
   previous=weights
   matrices=[np.asarray(cmds.getAttr(j+'.offsetParentMatrix')).reshape(4,4) for j in joint_names]
   assert np.isfinite(matrices).all()
   for j in joint_names:
    nr=j.replace('_JNT','NonRot_JNT');m=np.asarray(cmds.getAttr(nr+'.offsetParentMatrix')).reshape(4,4)
    assert np.allclose(m[:3,:3],np.eye(3),atol=1e-6)
    assert np.allclose(m[3,:3],np.asarray(cmds.getAttr(j+'.offsetParentMatrix')).reshape(4,4)[3,:3])
 cmds.setAttr('C_jaw_CTL.stickyFalloff',.2)
 for height in [0,.5,1]:
  cmds.setAttr('C_jaw_CTL.mouthHeight',height)
  cmds.setAttr('C_jaw_CTL.stickyLips',1)
  for low in joint_names:
   up=low.replace('lowerLip','upperLip')
   assert np.allclose(cmds.xform(low,q=True,ws=True,t=True),cmds.xform(up,q=True,ws=True,t=True),atol=1e-6)
 cmds.setAttr('C_jaw_CTL.mouthHeight',.5);cmds.setAttr('C_jaw_CTL.stickyLips',0)
 # Paired sampling and skin weights must stay identical across the ribbon/up curve.
 for part in ['upper','lower']:
  for i in range(25):
   assert np.isclose(cmds.getAttr('C_'+part+'LipAimVector_UVP.coordinate[%d].coordinateU'%i),cmds.getAttr('C_'+part+'LipUpVector_UVP.coordinate[%d].coordinateU'%i))
  skin='C_'+part+'LipOffset_SKIN'
  for i in range(9):
   weights=cmds.skinPercent(skin,'C_'+part+'LipOffset_CRV.cv[%d]'%i,q=True,value=True)
   assert np.isclose(max(weights),1) and np.count_nonzero(np.array(weights)>1e-8)==1
 # Move a corner through a continuous range with the jaw open: raw aim frames
 # must remain orthonormal, without a 180-degree jump between adjacent poses.
 cmds.setAttr('C_jaw_CTL.rx',30)
 previous=None
 for value in np.linspace(-1,1,41):
  cmds.setAttr('L_lipCorner_CTL.ty',float(value))
  frames=[np.asarray(cmds.getAttr(j.replace('_JNT','Vector_AMX')+'.outputMatrix')).reshape(4,4)[:3,:3] for j in joint_names]
  assert all(np.allclose(m@m.T,np.eye(3),atol=1e-6) and np.linalg.det(m)>.999 for m in frames)
  if previous is not None:assert all(np.trace(a@b.T)>1 for a,b in zip(frames,previous))
  previous=frames
 cmds.setAttr('L_lipCorner_CTL.ty',0)
 # Force zero-length, parallel, nearly parallel and invalid primary inputs.
 probe_pin=cmds.createNode('fourByFourMatrix',name='probePin')
 probe_up=cmds.createNode('composeMatrix',name='probeUp')
 probe_corner=cmds.createNode('transform',name='probeCorner')
 aim,frame=obj._stable_lip_aim('probeLip',probe_pin+'.output',probe_up+'.outputMatrix',probe_corner+'.worldMatrix[0]',[0,0,0])
 previous=None
 for y in np.linspace(-.4,.4,81):
  cmds.setAttr(probe_up+'.inputTranslate',0,float(y),1)
  m=np.asarray(cmds.getAttr(frame)).reshape(4,4)[:3,:3]
  assert np.isfinite(m).all() and np.allclose(m@m.T,np.eye(3),atol=1e-6)
  if previous is not None:assert np.trace(m@previous.T)>2.9
  previous=m
 cmds.setAttr(probe_up+'.inputTranslate',0,0,0)
 cmds.setAttr(probe_pin+'.in22',0)
 m=np.asarray(cmds.getAttr(frame)).reshape(4,4)[:3,:3]
 assert np.isfinite(m).all() and np.allclose(m@m.T,np.eye(3),atol=1e-6)
 for k in range(6):
  t=k/5.;expected=1-t*t*(3-2*t)
  assert np.isclose(cmds.getAttr('C_lowerLipCorner%02dBlend_BMX.target[0].rotateWeight'%k),expected)
 with open(work/'new_build_report.json','w') as f:json.dump(records,f,indent=2)
 cmds.setAttr('C_jaw_CTL.rx',0);cmds.file(rename=str(work/'new_lips_build.mb'));cmds.file(save=True,type='mayaBinary',force=True)
 print('PASS jaw/lips build: rounded U, independent primaries, corner rotation, continuous aim frames, fine axes, rotateOrder, opening and sticky closure',flush=True)
 print('U_PROFILE '+json.dumps(u_profiles),flush=True)
 print(json.dumps([{'angle':r['angle'],'width':r['width'],'height':r['height'],'quarter_gap':r['gap'][6],'center_gap':r['gap'][12]} for r in records]),flush=True)
finally:
 maya.standalone.uninitialize()
 temp.cleanup()
