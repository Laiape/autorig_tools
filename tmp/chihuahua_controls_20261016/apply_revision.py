"""Apply the artist's second controller drawing pass without posing the rig."""
import hashlib
import json
import math
import re
import struct
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import controller_display

OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
ROOT=Path('C:/proyectos/auto-rig/autorig_tools')
BASE=json.loads((OUT/'revision_baseline.json').read_text())
OLD=json.loads((OUT/'baseline.json').read_text())
assert cmds.file(q=True,sn=True)==BASE['scene']
assert cmds.objExists('chihuahua')
ctl_nodes=cmds.ls('*_CTL',type='transform',l=True)
controls={n.rsplit('|',1)[-1]:n for n in ctl_nodes}
restored=[];rings_done=[];copied=[];settings=[];reference=[]

def shapes(n):
    return cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []

def curve_fn(s):
    sl=om.MSelectionList();sl.add(s)
    return om.MFnNurbsCurve(sl.getDagPath(0))

def points(s,pp,world=True):
    fn=curve_fn(s)
    count=fn.numCVs-fn.degree if fn.form==om.MFnNurbsCurve.kPeriodic else fn.numCVs
    for i,p in enumerate(pp[:count]):
        cmds.xform(s+'.cv[%s]'%i,ws=world,os=not world,t=p)

def circle(n,center,radius,axes):
    for i,s in enumerate(shapes(n)):
        assert curve_fn(s).numCVs==11
        u,v=axes
        pp=[]
        for j in range(11):
            a=(j%8)*math.pi/4
            pp.append(list(om.MVector(center)+(u*math.cos(a)+v*math.sin(a))*(radius*1.1082)))
        points(s,pp)
    rings_done.append(n.rsplit('|',1)[-1])

def replace(n,source,center,width):
    old_shapes=shapes(n)
    for s in old_shapes:
        assert not cmds.listConnections(s+'.worldSpace',s=False,d=True)
        assert not cmds.listConnections(s+'.local',s=False,d=True)
    pp=[p for s in source for p in s['cvs']]
    lo=[min(p[i] for p in pp) for i in range(3)]
    hi=[max(p[i] for p in pp) for i in range(3)]
    mid=[(lo[i]+hi[i])*.5 for i in range(3)]
    factor=width/(hi[0]-lo[0])
    inv=om.MMatrix(cmds.xform(n,q=True,ws=True,m=True)).inverse()
    names=[s.rsplit('|',1)[-1] for s in old_shapes]
    cmds.delete(old_shapes)
    for i,s in enumerate(source):
        target=[[center[j]+(p[j]-mid[j])*factor for j in range(3)] for p in s['cvs']]
        local=[list(om.MPoint(*p)*inv)[:3] for p in target]
        temp=cmds.curve(p=local,k=s['knots'],d=s['degree'],per=s['form']==3)
        shp=cmds.listRelatives(temp,s=True,f=True)[0]
        shp=cmds.parent(shp,n,shape=True,relative=True)[0]
        cmds.rename(shp,names[i] if i<len(names) else n.rsplit('|',1)[-1]+'Shape%s'%(i+1))
        cmds.delete(temp)
    copied.append(n.rsplit('|',1)[-1])

def has_settings(n):
    for a in cmds.listAttr(n,ud=True) or []:
        if (cmds.getAttr(n+'.'+a,k=True) or cmds.getAttr(n+'.'+a,cb=True)) and not cmds.getAttr(n+'.'+a,l=True):
            if cmds.getAttr(n+'.'+a,type=True) in ('bool','float','double','long','enum'):
                return True
    return False

cmds.undoInfo(openChunk=True,chunkName='Chihuahua Controller Revision')
try:
    cmds.refresh(suspend=True)
    for name,n in controls.items():
        if (re.match(r'[LR]_(?:front|back)Leg',name) and 'Digit' not in name) or 'scapula' in name.lower():
            for s in shapes(n):
                raw=OLD['shapes'][s]['cvs']
                points(s,[raw[i:i+3] for i in range(0,len(raw),3)],world=False)
            restored.append(name)
        if re.search(r'Digit[IV]+\d+Fk_CTL$',name) or re.match(r'C_(?:spine\d+|tail(?:Fk|Bendy)\d+|neck\d+)_CTL$',name):
            p=cmds.xform(n,q=True,ws=True,t=True)
            joint=None
            if 'Digit' in name:
                candidate=name.replace('Fk_CTL','Skinning_JNT')
                if cmds.objExists(candidate):joint=candidate
                index=int(re.search(r'(\d+)Fk',name)[1]);radius=max(.14,.27-index*.055)
            else:
                prefix='C_spine' if 'spine' in name else 'C_tail' if 'tail' in name else 'C_neck'
                candidates=[j for j in cmds.ls(prefix+'*_JNT',type='joint') if 'Iris' not in j]
                if 'neck' in name:candidates+=cmds.ls('C_headSkinning_JNT')
                if candidates:
                    joint=min(candidates,key=lambda j:(om.MVector(cmds.xform(j,q=True,ws=True,t=True))-om.MVector(p)).length())
                radius=5.0 if 'spine' in name else (4.6 if name=='C_neck00_CTL' else 5.2) if 'neck' in name else .23 if 'Bendy' in name else max(.28,.65-int(re.search(r'Fk(\d+)',name)[1])*.09)
            matrix=cmds.xform(joint or n,q=True,ws=True,m=True)
            center=matrix[12:15] if 'Bendy' not in name else p
            u=om.MVector(matrix[4:7]).normal();v=om.MVector(matrix[8:11]).normal()
            circle(n,center,radius,(u,v))
    edward=json.loads((OUT/'edward_world_shapes.json').read_text())
    replace(controls['C_head_CTL'],edward['C_head_CTL'],(0,23.2,15.3),14.5)
    for side,sign in (('L',1),('R',-1)):
        replace(controls[side+'_eyeDirect_CTL'],edward[side+'_eyeDirect_CTL'],(sign*3.55,21.85,21.3),4.8)
    freya=json.loads((ROOT/'maya_tools/assets/freya/curves/freya_v001.curves').read_text())
    for name,center,width in (('C_jaw_CTL',(0,16.9,25.3),5.3),('C_upperJaw_CTL',(0,20.0,25.3),5.0)):
        source=next(v for k,v in freya.items() if k.rsplit('|',1)[-1]==name)
        source=[dict(cvs=s['curve']['cvs'],knots=s['curve']['knots'],degree=s['curve']['degree'],form=3 if s['curve']['form']=='periodic' else 1) for s in source['shapes']]
        replace(controls[name],source,center,width)
    for side in ('L','R'):
        for limb in ('frontLeg','backLeg'):
            prefix=side+'_'+limb
            ctl=controls[prefix+'DigitsAttributes_CTL']
            chains=[]
            for roman in ('I','II','III','IV','V'):
                found=[n for name,n in controls.items() if re.match(re.escape(prefix+'Digit'+roman)+r'\d+Fk_CTL$',name)]
                if found:chains.append(sorted(found))
            container=prefix+'DigitFk_GRP'
            follow=cmds.listConnections(container+'.offsetParentMatrix',s=True,d=False,p=True)[0]
            controller_display.configure_digit_settings(ctl,chains,follow_matrix=follow)
            # Export neutral local drawing so future builds do not double-offset it.
            center=cmds.xform(ctl,q=True,ws=True,t=True)
            circle(ctl,center,.38,(om.MVector(1,0,0),om.MVector(0,0,1)))
            settings.append(prefix)
    for n in cmds.ls('*Pv_CRV','*_eyeAim_CRV',type='transform'):
        if not cmds.ls(n,l=True)[0].startswith('|chihuahua|'):continue
        cmds.setAttr(n+'.overrideEnabled',True)
        cmds.setAttr(n+'.overrideDisplayType',2)
        cmds.setAttr(n+'.overrideColor',6 if n.startswith('L_') else 13 if n.startswith('R_') else 17)
        for s in shapes(n):
            cmds.setAttr(s+'.overrideEnabled',False)
            cmds.setAttr(s+'.lineWidth',-1)
        reference.append(n)
    thick=[]
    for name,n in controls.items():
        width=1.3 if has_settings(n) else -1
        if width==1.3:thick.append(name)
        for s in shapes(n):
            cmds.setAttr(s+'.lineWidth',width)
    for n,m in BASE['transforms'].items():
        if 'DigitsAttributes' not in n:
            assert max(abs(a-b) for a,b in zip(m,cmds.xform(n,q=True,ws=True,m=True)))<1e-10,n
    for s,h in BASE['meshes'].items():
        sl=om.MSelectionList();sl.add(s);fn=om.MFnMesh(sl.getDagPath(0))
        current=hashlib.sha256(b''.join(struct.pack('ddd',p.x,p.y,p.z) for p in fn.getPoints(om.MSpace.kWorld))).hexdigest()
        assert current==h,s
    assert cmds.currentTime(q=True)==BASE['frame']
    cmds.select(BASE['selection'],r=True) if BASE['selection'] else cmds.select(clear=True)
except BaseException:
    cmds.refresh(suspend=False);cmds.undoInfo(closeChunk=True);cmds.undo()
    raise
else:
    cmds.refresh(suspend=False);cmds.undoInfo(closeChunk=True)
cmds.refresh(force=True)
report=dict(restored=restored,rings=rings_done,copied=copied,settings=settings,reference=reference,thick=thick,geometry_exact=True,rig_matrices_unchanged=True)
(OUT/'revision_report.json').write_text(json.dumps(report,indent=2))
result={k:len(v) if isinstance(v,list) else v for k,v in report.items()}
