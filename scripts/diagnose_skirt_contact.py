"""Compare candidate station outputs against the calibrated native reference."""
import os,sys,json,math
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import skirt_contact as skirt
source=ROOT/'maya_tools/assets/Nini/scenes/Nini_dress_chains_v005.ma'
candidate=ROOT/'maya_tools/assets/Nini/experiments/skirt_contact/candidate_v001.ma'
cmds.file(str(source),open=True,force=True)
cmds.evaluationManager(mode='off')
data=skirt._data()
old={j:cmds.xform(j,q=True,ws=True,t=True) for j in data['joints']}
oldmat={j:cmds.getAttr(j+'.worldMatrix[0]') for j in data['joints']}
cmds.file(str(candidate),open=True,force=True)
cmds.evaluationManager(mode='off')
changes=sorted([(math.dist(old[j],cmds.xform(j,q=True,ws=True,t=True)),j) for j in data['joints']],reverse=True)
print('NEUTRAL_CHANGES='+json.dumps(changes[:6]),flush=True)
for _,j in changes[:3]:
 print('MATRIX_CHANGE='+json.dumps({'joint':j,'before':oldmat[j],
   'after':cmds.getAttr(j+'.worldMatrix[0]')}),flush=True)
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
cmds.xform('L_ankleIk_CTL',ws=True,t=[rest['L'][0],rest['L'][1]+15,rest['L'][2]+18])
report=skirt.audit()
rows=sorted(report['segments'],key=lambda v:v['ratio'],reverse=True)[:6]
for row in rows:
 c,l=row['chain'],row['level'];name='NiniDress_Contact_c{:02d}_j{:02d}'.format(c,l)
 row['target']={a:cmds.getAttr(name+'Target'+a+'_PMA.output1D') for a in 'XYZ'}
 row['final']={a:cmds.getAttr(name+'Final'+a+'_PMA.output1D') for a in 'XYZ'}
 row['rest']=data['stations_local'][c][l]
print('STRETCHED='+json.dumps(rows),flush=True)
