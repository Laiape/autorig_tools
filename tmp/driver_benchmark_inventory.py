import json
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import bifrost_wrinkles as bw, rig_performance as rp, rig_validation as qa
folder=Path('C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/driver_routing_20261015_v001')
folder.mkdir(parents=True,exist_ok=True)
def src(plug): return cmds.connectionInfo(plug,sourceFromDestination=True)
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'selection':cmds.ls(sl=True,long=True),'frame':cmds.currentTime(q=True)}
result['detail']=rp.export_detail_modes()
result['wrinkles']=bw.export_setups()
result['prx']={}
for n in cmds.ls(type='proximityWrap'):
    result['prx'][n]={'drivers':{i:{a:src('%s.drivers[%d].%s'%(n,i,a)) for a in ('driverGeometry','driverBindGeometry')} for i in cmds.getAttr(n+'.drivers',multiIndices=True) or []},'geometry':cmds.deformer(n,q=True,g=True),'envelope':cmds.getAttr(n+'.envelope')}
result['mesh']={}
for n in ('cuerpo_base','cuerpo_base_poseCorrectives_BLS_driver','cabeza_high','cabeza_low'):
    shapes=cmds.listRelatives(n,shapes=True,fullPath=True) or []
    result['mesh'][n]={'history':cmds.listHistory(n,pruneDagObjects=True),'shapes':{s:{'intermediate':cmds.getAttr(s+'.intermediateObject'),'input':src(s+'.inMesh'),'out':cmds.listConnections(s+'.outMesh',s=False,d=True,p=True),'world':cmds.listConnections(s+'.worldMesh[0]',s=False,d=True,p=True),'smooth':cmds.getAttr(s+'.displaySmoothMesh')} for s in shapes},'visible':om.MSelectionList().add(n).getDagPath(0).isVisible(),'verts':cmds.polyEvaluate(n,vertex=True)}
result['blendShape']={n:{'geometry':cmds.deformer(n,q=True,g=True),'aliases':cmds.aliasAttr(n,q=True),'input':cmds.listConnections(n+'.input',s=True,d=False,p=True),'output':cmds.listConnections(n+'.outputGeometry',s=False,d=True,p=True)} for n in cmds.ls(type='blendShape')}
result['cases']=qa.COMBINATION_POSES
result['controls']=[n for n in cmds.ls('*_CTL') if any(s in n.lower() for s in ('hip','spine','chest','neck','head','jaw','corner','brow','eyelid','clavicle','arm','leg','global'))]
path=folder/'Edward_baseline.mb'
if path.exists(): raise RuntimeError('Baseline already exists')
original=result['scene']
try:
    cmds.file(rename=path.as_posix()); cmds.file(save=True,type='mayaBinary',force=True)
finally:
    cmds.file(rename=original);cmds.file(modified=result['modified'])
(folder/'inventory.json').write_text(json.dumps(result,indent=2,default=str))
result={'baseline':str(path),'inventory':str(folder/'inventory.json')}
