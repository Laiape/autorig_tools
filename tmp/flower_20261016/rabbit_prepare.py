import json
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
base=Path('C:/proyectos/auto-rig/tmp/flower_20261016/rabbit_smooth')
base.mkdir(exist_ok=True)
scene=cmds.file(query=True,sceneName=True)
if not cmds.objExists('flower'):
    raise RuntimeError('Flower is not loaded.')
backup=Path('C:/proyectos/auto-rig/recovery/flower_before_rabbit_20261016_v001.mb')
index=1
while backup.exists():
    index+=1;backup=backup.with_name('flower_before_rabbit_20261016_v%03d.mb'%index)
cmds.file(rename=str(backup));cmds.file(save=True,type='mayaBinary',force=True)
cmds.file(rename=scene)
report={'backup':str(backup),'original_scene':scene,'frame':cmds.currentTime(query=True),
        'selection':cmds.ls(selection=True,long=True),'skins':{},'controls':{},'context':cmds.currentCtx()}
for ctl in cmds.ls('*_CTL',type='transform'):
    report['controls'][ctl]={attr:cmds.getAttr(ctl+'.'+attr) for attr in cmds.listAttr(ctl,keyable=True) or [] if cmds.getAttr(ctl+'.'+attr,type=True) not in ('message','string')}
for skin in cmds.ls(type='skinCluster'):
    sl=om.MSelectionList();sl.add(skin);fn=oma.MFnSkinCluster(sl.getDependNode(0))
    path=om.MDagPath.getAPathTo(fn.getOutputGeometry()[0])
    comp=om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
    om.MFnSingleIndexedComponent(comp).addElements(range(om.MFnMesh(path).numVertices))
    weights,count=fn.getWeights(path,comp)
    influences=fn.influenceObjects()
    report['skins'][skin]={'weights':list(weights),'influences':[p.partialPathName() for p in influences],
        'vertex_count':om.MFnMesh(path).numVertices,'maintainMaxInfluences':cmds.getAttr(skin+'.maintainMaxInfluences'),
        'locks':{p.partialPathName():cmds.getAttr(p.partialPathName()+'.liw') for p in influences}}
(base/'before.json').write_text(json.dumps(report,indent=2))
result={'backup':str(backup),'skin_info':{n:{k:v for k,v in row.items() if k not in ('weights','influences','locks')} for n,row in report['skins'].items()},
        'active_controls':{ctl:{a:v for a,v in attrs.items() if isinstance(v,(float,int)) and v not in (0,1)} for ctl,attrs in report['controls'].items() if any(isinstance(v,(float,int)) and v not in (0,1) for v in attrs.values())}}
