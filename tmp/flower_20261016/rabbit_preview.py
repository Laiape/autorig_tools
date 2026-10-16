import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
base=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
before=json.loads(Path('C:/proyectos/auto-rig/tmp/flower_20261016/rabbit_smooth/before.json').read_text())
data={}
for name in ('C_petalsA_SKC','C_petalsB_SKC'):
    sl=om.MSelectionList();sl.add(name);fn=oma.MFnSkinCluster(sl.getDependNode(0))
    path=om.MDagPath.getAPathTo(fn.getOutputGeometry()[0]);vertices=om.MFnMesh(path).numVertices
    comp=om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
    om.MFnSingleIndexedComponent(comp).addElements(range(vertices))
    weights,count=fn.getWeights(path,comp)
    data[name]=(fn,path,comp,om.MIntArray(range(count)),om.MDoubleArray(weights))
def capture(suffix):
    return cmds.playblast(format='image',completeFilename=str(base/('validation/rabbit_%s_195.png'%suffix)),
        compression='png',widthHeight=(1000,1000),showOrnaments=False,viewer=False,
        frame=cmds.currentTime(query=True),offScreen=True,forceOverwrite=True,percent=100)
try:
    for name,(fn,path,comp,indices,current) in data.items():
        fn.setWeights(path,comp,indices,om.MDoubleArray(before['skins'][name]['weights']),normalize=False)
    capture('before')
finally:
    for fn,path,comp,indices,current in data.values():
        fn.setWeights(path,comp,indices,current,normalize=False)
capture('after')
cmds.select('C_flowerHead_CTL')
result={'scene':cmds.file(query=True,sceneName=True),'curl':cmds.getAttr('C_flowerHead_CTL.petalCurl')}
