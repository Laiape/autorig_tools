import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools.skin_manager_api import SkinManager
base=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
work=Path('C:/proyectos/auto-rig/tmp/flower_20261016/rabbit_smooth')
before=json.loads((work/'before.json').read_text())
config=json.loads((base/'rig_data/flower.json').read_text())
report=json.loads((work/'apply.json').read_text())

def skin_data(name):
    sl=om.MSelectionList();sl.add(name);skin=oma.MFnSkinCluster(sl.getDependNode(0))
    path=om.MDagPath.getAPathTo(skin.getOutputGeometry()[0]);mesh=om.MFnMesh(path)
    comp=om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
    om.MFnSingleIndexedComponent(comp).addElements(range(mesh.numVertices))
    weights,count=skin.getWeights(path,comp)
    return skin,path,comp,np.array(weights).reshape(mesh.numVertices,count)

for skin,old in before['skins'].items():
    fn,path,comp,weights=skin_data(skin)
    original=np.array(old['weights']).reshape(weights.shape)
    if 'petals' not in skin:
        assert np.array_equal(weights,original),skin+' changed outside petals'
        continue
    mesh='C_petalsA_GEO' if 'petalsA' in skin else 'C_petalsB_GEO'
    names=[p.partialPathName() for p in fn.influenceObjects()]
    for entry in (e for e in config['petals'] if e['mesh']==mesh):
        columns=[i for i,n in enumerate(names) if n.startswith(entry['prefix'])]
        other=[i for i in range(len(names)) if i not in columns]
        assert np.max(np.abs(weights[np.ix_(entry['vertices'],other)])) == 0,entry['prefix']+' cross-shell weights'
    edges=om.MItMeshEdge(path); pairs=[]
    while not edges.isDone():
        pairs.append((edges.vertexId(0),edges.vertexId(1)));edges.next()
    pairs=np.array(pairs)
    def roughness(values):
        return float(np.mean(np.linalg.norm(values[pairs[:,0]]-values[pairs[:,1]],axis=1)))
    row=report['meshes'][mesh]
    row['edge_weight_variation_before']=roughness(original)
    row['edge_weight_variation_after']=roughness(weights)
    row['cross_shell_weights']=0
    assert row['edge_weight_variation_after']<row['edge_weight_variation_before']

report['other_skins_unchanged']=True
report['artist_frame']=before['frame']
report['artist_petal_curl']=cmds.getAttr('C_flowerHead_CTL.petalCurl')
report['backup']=before['backup']
curl=cmds.getAttr('C_flowerHead_CTL.petalCurl')
connection=cmds.listConnections('C_flowerHead_CTL.petalCurl',source=True,destination=False,plugs=True) or []
if connection:
    cmds.disconnectAttr(connection[0],'C_flowerHead_CTL.petalCurl')
try:
    cmds.setAttr('C_flowerHead_CTL.petalCurl',0)
    original=json.loads((base/'rig_data/source_geometry.json').read_text())
    report['neutral_errors']={}
    for mesh,entry in original.items():
        sl=om.MSelectionList();sl.add(mesh);path=sl.getDagPath(0);path.extendToShape()
        pts=np.array([[p.x,p.y,p.z] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)])
        error=float(np.linalg.norm(pts-np.array(entry['points']),axis=1).max())
        assert error<1e-4,(mesh,error)
        report['neutral_errors'][mesh]=error
    cmds.optionVar(stringValue=('currentAssetRigName','flower'))
    cmds.select(clear=True)
    skin_path=base/'skin_clusters/flower_v002.skc'
    if skin_path.exists():
        raise RuntimeError('Choose a new skin version; v002 already exists.')
    SkinManager().export_skins(in_path=str(skin_path),lossless=True)
    payload=json.loads(skin_path.read_text())
    exported=[r for rows in payload.values() if isinstance(rows,list) for r in rows if isinstance(r,dict) and 'sparse_weights' in r]
    assert len(exported)==5,len(exported)
    for row in exported:
        fn,path,comp,current=skin_data(row['name'])
        names=[p.partialPathName() for p in fn.influenceObjects()]
        values=np.zeros_like(current)
        for name,data in row['sparse_weights'].items():
            values[data['ix'],names.index(name)]=data['vw']
        assert np.array_equal(values,current),row['name']+' export changed weights'
    neutral_scene=base/'scenes/flower_rig_v003.mb'
    cmds.file(rename=str(neutral_scene));cmds.file(save=True,type='mayaBinary',force=True)
    report.update(skin=str(skin_path),neutral_scene=str(neutral_scene),lossless_export_verified=True)
finally:
    if connection:
        cmds.connectAttr(connection[0],'C_flowerHead_CTL.petalCurl')
    else:
        cmds.setAttr('C_flowerHead_CTL.petalCurl',curl)
    cmds.currentTime(before['frame'])
    cmds.select(before['selection'],replace=True)

review=base/'scenes/flower_rabbit_review_v001.mb'
cmds.file(rename=str(review));cmds.file(save=True,type='mayaBinary',force=True)
report['review_scene']=str(review)
report['passed']=True
(base/'validation/rabbit_smoothing_20261016.json').write_text(json.dumps(report,indent=2))
result=report
