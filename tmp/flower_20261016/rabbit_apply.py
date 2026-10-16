import json
from pathlib import Path
import numpy as np
from maya import cmds,mel
from maya.api import OpenMaya as om,OpenMayaAnim as oma
base=Path('C:/proyectos/auto-rig/tmp/flower_20261016/rabbit_smooth')
before=json.loads((base/'before.json').read_text())
cmds.loadPlugin('brSmoothWeights',quiet=True)
context='flowerRabbitSmoothCtx'
if not cmds.contextInfo(context,exists=True):
    mel.eval('brSmoothWeightsContext "%s";'%context)
cmds.undoInfo(openChunk=True,chunkName='Rabbit smooth flower petal weights')
result={'tool':'brSmoothWeights','strength':0.5,'oversampling':4,'flood_passes':3,'volume':False,'keepShellsTogether':False,'meshes':{}}
try:
    for mesh in ('C_petalsA_GEO','C_petalsB_GEO'):
        cmds.setToolTo('selectSuperContext')
        cmds.select(mesh,replace=True)
        cmds.setToolTo(context)
        mel.eval('brSmoothWeightsContext -edit -volume false -keepShellsTogether false -oversampling 4 -fractionOversampling false -strength 0.5 -message false "%s";'%context)
        for iteration in range(3):
            mel.eval('brSmoothWeightsContext -edit -flood 0.5 "%s";'%context)
        cmds.setToolTo('selectSuperContext')
        skin=mesh.replace('_GEO','_SKC')
        sl=om.MSelectionList();sl.add(skin);fn=oma.MFnSkinCluster(sl.getDependNode(0))
        path=om.MDagPath.getAPathTo(fn.getOutputGeometry()[0])
        comp=om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
        count=om.MFnMesh(path).numVertices
        om.MFnSingleIndexedComponent(comp).addElements(range(count))
        weights,n=fn.getWeights(path,comp)
        current=np.array(weights).reshape(count,n)
        old=np.array(before['skins'][skin]['weights']).reshape(count,n)
        result['meshes'][mesh]={'changed_vertices':int(np.count_nonzero(np.max(np.abs(current-old),axis=1)>1e-12)),
                               'max_weight_change':float(np.max(np.abs(current-old))),
                               'normalization_error':float(np.max(np.abs(current.sum(axis=1)-1))),
                               'max_influences':int(np.max(np.count_nonzero(current,axis=1)))}
        assert result['meshes'][mesh]['changed_vertices']>0,mesh+' weights did not change'
        assert np.all(np.isfinite(current)) and np.min(current)>=0
        assert result['meshes'][mesh]['normalization_error']<1e-8
finally:
    cmds.setToolTo('selectSuperContext')
    cmds.select(before['selection'],replace=True)
    cmds.undoInfo(closeChunk=True)
(base/'apply.json').write_text(json.dumps(result,indent=2))
