"""Fit Chihuahua controller drawing only; keep all rig transforms intact."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import maya.cmds as cmds
import maya.api.OpenMaya as om

OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
BASE=json.loads((OUT/'baseline.json').read_text())
current_scene=cmds.file(q=True,sn=True)
assert Path(current_scene).with_suffix('')==Path(BASE['scene']).with_suffix('')
cmds.file(type=BASE['file_type'])
cmds.file(rename=BASE['scene'])
assert cmds.file(q=True,sn=True)==BASE['scene']
assert cmds.objExists('chihuahua')
controls=cmds.ls('*_CTL',type='transform',long=True)
assert len(controls)==290
changed=[]

def shapes(n):
    return cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []

def set_points(s,pts):
    assert not cmds.listConnections(s+'.create',s=True,d=False)
    assert len(pts)==cmds.getAttr(s+'.controlPoints',size=True)
    sl=om.MSelectionList();sl.add(s)
    fn=om.MFnNurbsCurve(sl.getDagPath(0))
    count=fn.numCVs-fn.degree if fn.form==om.MFnNurbsCurve.kPeriodic else fn.numCVs
    for i,p in enumerate(pts[:count]):
        cmds.xform('%s.cv[%s]'%(s,i),ws=True,t=p)

def ring(s,center,rx,ry,plane='xy'):
    assert cmds.getAttr(s+'.controlPoints',size=True)==11
    axes={'xy':((1,0,0),(0,1,0)),'xz':((1,0,0),(0,0,1)),
        'yz':((0,1,0),(0,0,1)),'tail':((1,0,0),(0,.4,.9165))}
    u,v=axes[plane] if isinstance(plane,str) else plane
    pts=[]
    for i in range(11):
        a=2*math.pi*(i%8)/8
        pts.append([center[j]+1.1082*(rx*math.cos(a)*u[j]+ry*math.sin(a)*v[j]) for j in range(3)])
    set_points(s,pts)

def rings(n,center,rx,ry=None,plane='xy',sphere=False):
    for i,s in enumerate(shapes(n)):
        ring(s,center,rx,ry if ry is not None else rx,('xy','xz','yz')[i%3] if sphere else plane)
    changed.append(n.rsplit('|',1)[-1])

def refit(n,center,scale=1.0,dimensions=None):
    ss=shapes(n)
    points=[]
    for s in ss:
        raw=cmds.xform(s+'.cv[*]',q=True,ws=True,t=True)
        points.extend([raw[i:i+3] for i in range(0,len(raw),3)])
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    mid=[(a+b)*.5 for a,b in zip(lo,hi)]
    for s in ss:
        raw=cmds.xform(s+'.cv[*]',q=True,ws=True,t=True)
        pts=[raw[i:i+3] for i in range(0,len(raw),3)]
        set_points(s,[[center[j]+(p[j]-mid[j])*(dimensions[j]/max(hi[j]-lo[j],1e-5) if dimensions else scale) for j in range(3)] for p in pts])
    changed.append(n.rsplit('|',1)[-1])

def mesh_hashes():
    result={}
    for n in BASE['meshes']:
        sl=om.MSelectionList();sl.add(n)
        pp=om.MFnMesh(sl.getDagPath(0)).getPoints(om.MSpace.kWorld)
        result[n]=hashlib.sha256(b''.join(struct.pack('ddd',p.x,p.y,p.z) for p in pp)).hexdigest()
    return result

def verify():
    bad=[n for n,m in BASE['transforms'].items() if max(abs(a-b) for a,b in zip(m,cmds.xform(n,q=True,ws=True,m=True)))>1e-10]
    assert not bad, 'Rig matrices changed: '+repr(bad[:5])
    assert mesh_hashes()==BASE['meshes'], 'Mesh geometry changed'
    assert sorted(cmds.ls(l=True))==BASE['nodes'], 'Scene node identities changed'
    assert cmds.currentTime(q=True)==BASE['frame']
    assert cmds.ls(sl=True,l=True)==BASE['selection']

cmds.undoInfo(openChunk=True,chunkName='Fit Chihuahua Controller Shapes')
try:
    cmds.refresh(suspend=True)
    for s,data in BASE['shapes'].items():
        raw=data['cvs']
        for i in range(len(raw)//3):
            cmds.xform('%s.cv[%s]'%(s,i),os=True,t=raw[i*3:i*3+3])
    for n in controls:
        name=n.rsplit('|',1)[-1]
        side=1 if name.startswith('L_') else -1 if name.startswith('R_') else 0
        p=cmds.xform(n,q=True,ws=True,t=True)
        secondary=bool(re.search(r'Bendy|Bank|Sole|Heel|Toe|Digit|eyelid(?:In|Out)(?:Up|Down)|(?:upper|lower)Lip\d|(?:upper|down)Eyelid',name))
        color=(18 if secondary else 6) if side==1 else (4 if secondary else 13) if side==-1 else 24 if 'Bendy' in name or 'Attatched' in name else 17
        if name in ('C_character_CTL','C_settings_CTL'):
            color=14
        cmds.setAttr(n+'.overrideEnabled',True)
        cmds.setAttr(n+'.overrideRGBColors',False)
        cmds.setAttr(n+'.overrideColor',color)
        for s in shapes(n):
            cmds.setAttr(s+'.overrideEnabled',False)
            cmds.setAttr(s+'.lineWidth',1.5 if secondary else 2.0)
        if 'AttatchedFk' in name:
            rings(n,p,.45,.45,'xz')
        elif name=='C_body_CTL':
            refit(n,(0,18.3,8.5),1.25)
        elif name=='C_pelvis_CTL':
            for i,s in enumerate(shapes(n)):
                ring(s,(0,11.1,5.5),*( ((5.2,4.2),(5.2,2.6),(4.2,2.6))[i]),plane=('xy','xz','yz')[i])
            changed.append(name)
        elif name=='C_localChest_CTL':
            rings(n,(0,12.3,12.3),5.6,4.9)
        elif re.match(r'C_spine\d+_CTL',name):
            i=int(re.search(r'spine(\d+)',name)[1])
            rings(n,(0,15.5+i*.35,p[2]),1.25,.45,'xz')
        elif name=='C_neck00_CTL':
            rings(n,(0,16.4,15.6),5.2,4.7,'xz')
        elif name=='C_neck01_CTL':
            rings(n,(0,19.0,17.0),5.6,4.8,'xz')
        elif name=='C_head_CTL':
            rings(n,(0,25.3,18.4),7.1,5.9,'xz')
        elif name=='C_face_CTL':
            rings(n,(0,28.3,23.5),.65,.65)
        elif name=='C_jaw_CTL':
            rings(n,(0,16.8,23.3),2.9,2.2,'xz')
        elif name=='C_upperJaw_CTL':
            rings(n,(0,19.8,24.4),2.8,.55)
        elif name=='C_mainMouth_CTL':
            rings(n,(0,18.3,27.5),3.1,1.0)
        elif name in ('C_upperLip_CTL','C_lowerLip_CTL'):
            rings(n,(0,19.25 if 'upper' in name else 17.25,26.4),.25,sphere=True)
        elif re.search(r'(?:upper|lower)Lip\d+',name):
            rings(n,(p[0]+side*.1,p[1]+(.35 if 'upper' in name else -.35),p[2]+.45),.11)
        elif 'lipCorner' in name:
            rings(n,(side*2.7,18.3,23.6),.23,sphere=True)
        elif name=='C_eyeMain_CTL':
            rings(n,(0,23,35),6.5,2.6)
        elif name in ('L_eye_CTL','R_eye_CTL'):
            rings(n,(side*3.5,23,35),1.6,1.6)
        elif 'eyeDirect' in name:
            rings(n,(side*3.65,21.85,22.5),2.45,2.6,((.9165,0,-side*.4),(0,1,0)))
        elif re.search(r'(?:upper|down)Eyelid\d+',name):
            rings(n,(p[0],p[1],p[2]+.18),.055)
        elif 'eyelid' in name:
            radius=.14 if secondary else .22
            rings(n,(p[0],p[1],p[2]+.45),radius,sphere=True)
        elif re.search(r'ear\d+',name):
            i=int(re.search(r'ear(\d+)',name)[1])
            rings(n,(p[0],p[1],p[2]+.65),*( ((1.5,1.45),(1.4,2.3),(.5,.65))[min(i,2)]))
        elif 'tailFk' in name:
            i=int(re.search(r'Fk(\d+)',name)[1]);r=.7-i*.085
            rings(n,p,r,r,'tail')
        elif 'tailBendy' in name:
            rings(n,p,.23,.23,'tail')
        elif 'DigitsAttributes' in name:
            rings(n,(side*7.8,2.6,15.5 if 'front' in name else 3.3),.45)
        elif 'Digit' in name:
            i=int(re.search(r'Digit[IV]+(\d+)',name)[1])
            radius=max(.09,.20-i*.04)
            rings(n,(p[0],p[1]+.3+i*.2,p[2]),radius,radius*1.25,'xz')
        elif name.endswith('Foot_CTL'):
            rings(n,(p[0],.1,p[2]+.65),1.3,1.7,'xz')
        elif name.endswith('Sole_CTL'):
            rings(n,(side*(abs(p[0])+2),.4,p[2]-.7),.32,.32,'xz')
        elif re.search(r'(?:BankIn|BankOut|Heel|Toe)_CTL',name):
            zoffset=-.45 if 'Heel' in name else .45 if 'Toe' in name else 0
            rings(n,(p[0],.4,p[2]+zoffset),.22,sphere=True)
        elif re.search(r'Leg.*Fk_CTL',name):
            r=1.3 if 'Shoulder' in name or 'Hip' in name else 1 if 'Elbow' in name or 'Stifle' in name else .7 if 'Hock' in name or 'Carpus' in name else .48
            rings(n,p,r,r,'xz')
        elif re.search(r'(?:Shoulder|Hip)Ik_CTL',name):
            rings(n,(side*(abs(p[0])+1.2),p[1],p[2]),.7,.7,'yz')
        elif 'Leg' in name and 'Bendy' in name:
            r=1.15 if 'Upper' in name else .8 if 'Middle' in name else .5
            rings(n,p,r,r,'xz')
        elif name.endswith('Pv_CTL'):
            rings(n,p,.38,sphere=True)
        elif 'LegSettings' in name:
            refit(n,(side*6.8,2.5,p[2]),1.35)
        elif 'scapulaMaster' in name:
            refit(n,(side*5.3,11.7,15),dimensions=(1.6,3.2,2.1))
        elif name.endswith('scapula_CTL'):
            rings(n,(side*5.2,14.4,14),.65,.85,'yz')
    verify()
except BaseException:
    cmds.refresh(suspend=False)
    cmds.undoInfo(closeChunk=True)
    cmds.undo()
    raise
else:
    cmds.refresh(suspend=False)
    cmds.undoInfo(closeChunk=True)

cmds.viewPlace('persp',eye=(55,33,74),lookAt=(0,16,14))
cmds.setAttr('perspShape.centerOfInterest',65)
cmds.refresh(force=True)
report=dict(controls_colored=len(controls),controls_refitted=len(set(changed)),
    transform_matrices_unchanged=True,mesh_points_exact=True,node_identities_unchanged=True,
    backup=BASE['backup'],changed=changed)
(OUT/'fit_report.json').write_text(json.dumps(report,indent=2))
result={k:v for k,v in report.items() if k!='changed'}
