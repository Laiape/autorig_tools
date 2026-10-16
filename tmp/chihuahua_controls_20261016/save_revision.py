import hashlib
import json
import math
import struct
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import curve_tool

OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
ASSET=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua')
BASE=json.loads((OUT/'revision_baseline.json').read_text())
OLD=json.loads((OUT/'baseline.json').read_text())
REPORT=json.loads((OUT/'revision_report.json').read_text())
assert cmds.file(q=True,sn=True)==BASE['scene']

for n in REPORT['restored']:
    for s in cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []:
        previous=next(v for k,v in OLD['shapes'].items() if k==s)
        current=cmds.xform(s+'.cv[*]',q=True,os=True,t=True)
        assert len(current)==len(previous['cvs'])
        assert max(abs(a-b) for a,b in zip(current,previous['cvs']))<1e-9,n

for prefix in REPORT['settings']:
    ctl=prefix+'DigitsAttributes_CTL'
    plug=ctl+'.Controllers_Visibility'
    roots=cmds.listConnections(plug,s=False,d=True,p=True)
    assert len(roots)>=4
    for value in (True,False):
        cmds.setAttr(plug,value)
        assert all(cmds.getAttr(root)==value for root in roots)
    assert cmds.attributeQuery('Controllers_Visibility',node=ctl,listDefault=True)==[0]
    p=cmds.xform(ctl,q=True,ws=True,t=True)
    digit_ctls=[n for n in cmds.ls(prefix+'Digit*Fk_CTL',type='transform')]
    assert p[1]>max(cmds.xform(n,q=True,ws=True,t=True)[1] for n in digit_ctls)
    for s in cmds.listRelatives(ctl,s=True,f=True,type='nurbsCurve'):
        assert math.isclose(cmds.getAttr(s+'.lineWidth'),1.3,abs_tol=1e-6)
for n in REPORT['reference']:
    assert cmds.getAttr(n+'.overrideDisplayType')==2
for n in cmds.ls('*_CTL',type='transform'):
    expected=1.3 if n in REPORT['thick'] else -1
    for s in cmds.listRelatives(n,s=True,ni=True,f=True,type='nurbsCurve') or []:
        assert math.isclose(cmds.getAttr(s+'.lineWidth'),expected,abs_tol=1e-6),s
for s,h in BASE['meshes'].items():
    sl=om.MSelectionList();sl.add(s);fn=om.MFnMesh(sl.getDagPath(0))
    current=hashlib.sha256(b''.join(struct.pack('ddd',p.x,p.y,p.z) for p in fn.getPoints(om.MSpace.kWorld))).hexdigest()
    assert current==h,s
for n,m in BASE['transforms'].items():
    if 'DigitsAttributes' not in n:
        assert max(abs(a-b) for a,b in zip(m,cmds.xform(n,q=True,ws=True,m=True)))<1e-10,n

def next_version(folder,prefix,suffix):
    i=1
    while (folder/('%s_v%03d%s'%(prefix,i,suffix))).exists():i+=1
    return folder/('%s_v%03d%s'%(prefix,i,suffix))

curves=next_version(ASSET/'curves','chihuahua','.curves')
scene=next_version(ASSET/'scenes','chihuahua_controls','.mb')
curve_tool.get_all_ctl_curves_data(path=str(curves),root_filter='chihuahua')
payload=json.loads(curves.read_text())
assert len(payload)==290
for v in payload.values():
    name=v['transform']['name']
    expected=1.3 if name in REPORT['thick'] else -1
    for s in v['shapes']:
        assert math.isclose(s['lineWidth'],expected,abs_tol=1e-6)
cmds.file(rename=str(scene));cmds.file(save=True,type='mayaBinary',force=True)
assert not cmds.file(q=True,modified=True)
REPORT.update(scene=str(scene),curves=str(curves),saved=True,visibility_verified=True,
              backup=str(OUT/'chihuahua_before_revision.mb'))
(OUT/'revision_delivery.json').write_text(json.dumps(REPORT,indent=2))
result=dict(scene=str(scene),curves=str(curves),controls=len(payload),thick=len(REPORT['thick']),reference=len(REPORT['reference']),geometry_exact=True,saved=True)
