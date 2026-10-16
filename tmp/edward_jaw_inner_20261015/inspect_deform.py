import json,sys
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
ROOT=Path(r'C:/proyectos/auto-rig')
WORK=ROOT/'tmp/edward_jaw_inner_20261015'
result={'wraps':cmds.ls(type='proximityWrap'),'skins':cmds.ls(type='skinCluster'),'bs':[],'lip_nodes':[],'cameras':[]}
for b in cmds.ls(type='blendShape'):
    if 'poseCorrective' not in b:continue
    info={'node':b,'geometry':cmds.deformer(b,q=True,g=True),'aliases':cmds.aliasAttr(b,q=True),'targets':[]}
    for i in cmds.getAttr(b+'.weight',mi=True) or []:
        g=b+'.inputTarget[0].inputTargetGroup[%d]'%i
        mask=cmds.getAttr(g+'.targetWeights',mi=True) or []
        info['targets'].append({'index':i,'alias':cmds.aliasAttr(b+'.weight[%d]'%i,q=True),'weight':cmds.getAttr(b+'.weight[%d]'%i),'mode':cmds.getAttr(g+'.postDeformersMode'),'delta_count':len(cmds.getAttr(g+'.inputTargetItem[6000].inputPointsTarget') or []),'mask_entries':len(mask),'mask_non_one':[(j,cmds.getAttr(g+'.targetWeights[%d]'%j)) for j in mask if abs(cmds.getAttr(g+'.targetWeights[%d]'%j)-1)>.0001][:30]})
    result['bs'].append(info)
for n in cmds.ls(type='nurbsSurface'):
    if 'lip' in n.lower():result['lip_nodes'].append(n)
for p in cmds.getPanel(type='modelPanel'):
    try:result['cameras'].append({'panel':p,'camera':cmds.modelPanel(p,q=True,camera=True),'visible':cmds.modelEditor(p,q=True,activeView=True)})
    except:pass
result['history']={m:cmds.ls(cmds.listHistory(m) or [],type='geometryFilter') for m in ('cabeza_high','cabeza_low') if cmds.objExists(m)}
backup=WORK/'Before_Edward_JawInnerLips.mb'
if not backup.exists():cmds.file(str(backup),exportAll=True,type='mayaBinary',preserveReferences=True,force=False)
result['backup']=str(backup)
(WORK/'deformer_inventory.json').write_text(json.dumps(result,indent=2))
try:
    img=str(WORK/'before_view.png')
    cmds.playblast(completeFilename=img,format='image',compression='png',frame=cmds.currentTime(q=True),viewer=False,offScreen=True,showOrnaments=False,widthHeight=(1318,748),percent=100,forceOverwrite=True)
    result['image']=img
except Exception as exc:result['image_error']=str(exc)
