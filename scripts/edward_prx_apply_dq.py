"""Switch the 23 owned fitted garment skins to DQ, preserving native weights."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
ROOT=Path(r'C:/proyectos/auto-rig')
BASE=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001'
FOLDER=BASE/'dq_20261016_v001';FOLDER.mkdir(parents=True,exist_ok=True)
owned=json.loads((FOLDER/'owned_launch.json').read_text())['pid'] if (FOLDER/'owned_launch.json').exists() else None
assert os.getpid() in (55092,owned) and os.getpid()!=23404
assert Path(cmds.file(q=True,sn=True)).resolve()==(BASE/'Edward_all_PRX_SKIN_COMPARE_v001.ma').resolve()
manifest=json.loads((BASE/'manifest.json').read_text())
before=FOLDER/'Edward_all_PRX_SKIN_before_DQ_v001.ma'
destination=FOLDER/'Edward_all_PRX_SKIN_DQ_COMPARE_v001.ma'
assert not before.exists() and not destination.exists()
cmds.file(str(before),exportAll=True,type='mayaAscii',force=False,preserveReferences=True,options='v=0;')


def skin_data(skin,mesh):
    selection=om.MSelectionList();selection.add(skin);fn=oma.MFnSkinCluster(selection.getDependNode(0))
    shapes=cmds.listRelatives(mesh,s=True,ni=True,f=True) or []
    shape=next(s for s in shapes if cmds.nodeType(s)=='mesh')
    selection=om.MSelectionList();selection.add(shape);path=selection.getDagPath(0)
    cf=om.MFnSingleIndexedComponent();component=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(om.MFnMesh(path).numVertices)
    weights=np.asarray(fn.getWeights(path,component)[0],dtype='<f8')
    blend=np.asarray(fn.getBlendWeights(path,component),dtype='<f8')
    return {'weights_sha256':hashlib.sha256(weights.tobytes()).hexdigest(),
            'blend_weights_sha256':hashlib.sha256(blend.tobytes()).hexdigest(),
            'influences':[p.fullPathName() for p in fn.influenceObjects()]}


all_methods={s:cmds.getAttr(s+'.skinningMethod') for s in cmds.ls(type='skinCluster')}
records={}
for wrap,record in manifest['skin'].items():
    skin=record['skin'];records[wrap]={'skin':skin,'mesh':record['mesh'],'before_method':all_methods[skin],
                                     'before':skin_data(skin,record['mesh'])}
cmds.undoInfo(openChunk=True,chunkName='SetAllBakedGarmentSkinsDQ')
try:
    for record in records.values():cmds.setAttr(record['skin']+'.skinningMethod',1)
finally:cmds.undoInfo(closeChunk=True)
for record in records.values():
    record['after']=skin_data(record['skin'],record['mesh'])
    record['after_method']=cmds.getAttr(record['skin']+'.skinningMethod')
    assert record['after']==record['before'] and record['after_method']==1
changed={r['skin'] for r in records.values()}
assert all(cmds.getAttr(s+'.skinningMethod')==v for s,v in all_methods.items() if s not in changed)
cmds.file(rename=str(destination));cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
result={'scene':str(destination),'before_scene':str(before),'skins_changed':len(records),'method':'Dual Quaternion',
        'weights_and_blend_weights_unchanged':True,'other_skin_methods_unchanged':True,
        'records':records,'frame':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True)}
(FOLDER/'apply_dq.json').write_text(json.dumps(result,indent=2))
result={k:v for k,v in result.items() if k!='records'}
