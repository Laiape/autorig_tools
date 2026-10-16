import sys,json,math,tempfile
from pathlib import Path
sys.path.insert(0,'C:/proyectos/auto-rig/autorig_tools')
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
from maya_tools.scripts.tools import eyelid_rotation,eyelid_contact
cmds.file('C:/proyectos/auto-rig/recovery/eyelids_large_roll_before_20261016_v001.mb',open=True,force=True,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
joint_names=sorted(cmds.ls('*Eyelid*Skinning_JNT',type='joint'))
pose={n+'.'+a:cmds.getAttr(n+'.'+a) for n in cmds.ls('*_eyelid*CTL') for a in ('tx','ty','tz','rx','ry','rz') if cmds.getAttr(n+'.'+a,settable=True)}
for a in pose:cmds.setAttr(a,0)
before=np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joint_names])
for a,v in pose.items():cmds.setAttr(a,v)
eyelid_contact.upgrade(['L_eyeDirect_CTL','R_eyeDirect_CTL'])
for a in pose:cmds.setAttr(a,0)
after=np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joint_names])
neutral=float(np.max(abs(before-after)))
assert neutral<1e-5,neutral
assert joint_names==sorted(cmds.ls('*Eyelid*Skinning_JNT',type='joint'))
assert not eyelid_contact.upgrade(['L_eyeDirect_CTL','R_eyeDirect_CTL'])
cases=[]
def crosses(a,b,c,d):
    def orient(p,q,r):return float(np.cross(q-p,r-p))
    return orient(a,b,c)*orient(a,b,d)<-1e-9 and orient(c,d,a)*orient(c,d,b)<-1e-9
for mode in ('off','serial','parallel'):
 cmds.evaluationManager(mode=mode)
 for side in ('L','R'):
  inverse=om.MMatrix(cmds.getAttr(side+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')).inverse()
  for lid in ('Up','Down'):
   for angle in (-90,-60,-25.241064,0,25.241064,60,90):
    cmds.setAttr(side+'_eyelid'+lid+'_CTL.rz',angle)
    for blink in (0,.5,1):
     for attr in ('Upper_Blink','Lower_Blink'):cmds.setAttr(side+'_eyeDirect_CTL.'+attr,blink)
     matrices=[np.array([cmds.getAttr(side+'_'+label+'Eyelid0%dSkinning_JNT.worldMatrix[0]'%i) for i in range(21)]) for label in ('upper','down')]
     assert np.isfinite(matrices).all()
     gaps=np.linalg.norm(matrices[0][:,12:15]-matrices[1][:,12:15],axis=1)
     assert max(gaps[0],gaps[-1])<1e-4
     if blink==1:assert np.max(abs(matrices[0]-matrices[1]))<1e-4
     intersections=[]
     if blink==0:
      polygon=[]
      for mat in list(matrices[0])+list(matrices[1][-2:0:-1]):
       p=om.MPoint(*mat[12:15])*inverse;polygon.append(np.array([p.x,p.y]))
      for i in range(len(polygon)):
       for j in range(i+2,len(polygon)):
        if i==0 and j==len(polygon)-1:continue
        if crosses(polygon[i],polygon[(i+1)%len(polygon)],polygon[j],polygon[(j+1)%len(polygon)]):intersections.append([i,j])
      assert not intersections,(side,lid,angle,intersections)
     cases.append(dict(mode=mode,side=side,lid=lid,angle=angle,blink=blink,max_corner_gap=float(max(gaps[0],gaps[-1]))))
    for attr in ('Upper_Blink','Lower_Blink'):cmds.setAttr(side+'_eyeDirect_CTL.'+attr,0)
    cmds.setAttr(side+'_eyelid'+lid+'_CTL.rz',0)
for a,v in pose.items():cmds.setAttr(a,v)
expected=np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joint_names])
with tempfile.TemporaryDirectory() as folder:
 path=str(Path(folder)/'large_roll.mb');cmds.file(rename=path);cmds.file(save=True,type='mayaBinary',force=True)
 cmds.file(path,open=True,force=True,executeScriptNodes=False)
 actual=np.array([cmds.getAttr(n+'.worldMatrix[0]') for n in joint_names])
 assert np.max(abs(actual-expected))<1e-5
result=dict(neutral_matrix_error=neutral,cases=cases,reopen_max_matrix_error=float(np.max(abs(actual-expected))))
Path('C:/proyectos/auto-rig/tmp/eyelid_orbit_scene_validation.json').write_text(json.dumps(result,indent=2))
print('PASS REAL SCENE: unchanged bind, existing joints, idempotent upgrade, no border self intersections, -90..90 Up/Down L/R, DG/Serial/Parallel, native reopen',flush=True)
