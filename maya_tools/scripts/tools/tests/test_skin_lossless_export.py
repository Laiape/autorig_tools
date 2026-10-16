"""Native SKC retains sub-threshold weights and full double precision."""
import json
import os
from pathlib import Path
import sys
import tempfile
import numpy as np

os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'maya_tools/scripts')]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools.skin_manager_api import SkinManager

cmds.file(new=True,force=True)
cmds.select(clear=True)
one=cmds.joint(name='firstInfluence')
unused=cmds.joint(name='removedMiddleInfluence',position=(.5,0,0))
two=cmds.joint(name='secondInfluence',position=(1,0,0))
mesh=cmds.polyCube(name='precisionMesh')[0]
skin=cmds.skinCluster([one,unused,two],mesh,toSelectedBones=True,skinMethod=2)[0]
cmds.skinCluster(skin,edit=True,removeInfluence=unused)
assert cmds.getAttr(skin+'.matrix',multiIndices=True)==[0,2]
shape=cmds.listRelatives(mesh,shapes=True,fullPath=True)[0]
path=om.MSelectionList().add(shape).getDagPath(0)
c=om.MFnSingleIndexedComponent();component=c.create(om.MFn.kMeshVertComponent);c.setCompleteData(8)
fn=oma.MFnSkinCluster(om.MSelectionList().add(skin).getDependNode(0))
values=np.asarray([[1.-1e-12,1e-12],[.1234567890123456,.8765432109876544]]*4)
blend=np.asarray([1e-12,.1234567890123456]*4)
cmds.setAttr(skin+'.normalizeWeights',0)
fn.setWeights(path,component,om.MIntArray([0,1]),om.MDoubleArray(values.ravel().tolist()),False)
fn.setBlendWeights(path,component,om.MDoubleArray(blend.tolist()))
expected_weights=np.asarray(fn.getWeights(path,component)[0]).reshape((8,2)).copy()
expected_blend=np.asarray(fn.getBlendWeights(path,component)).copy()
manager=SkinManager.__new__(SkinManager)
manager.k_skin_attrs=['skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution']
manager.tolerance=1e-5
with tempfile.TemporaryDirectory() as directory:
    target=str(Path(directory)/'lossless.skc')
    cmds.select(mesh)
    assert manager.export_skins(target)==target
    data=json.loads(Path(target).read_text())
    row=next(v[0] for k,v in data.items() if not k.startswith('__'))
    assert row['weight_encoding']=='float64_exact_nonzero'
    assert any(1e-12 in r['vw'] for r in row['sparse_weights'].values())
    assert all(v in row['sparse_blend']['vw'] for v in expected_blend if 0<v<1e-5)
    fn.setWeights(path,component,om.MIntArray([0,1]),om.MDoubleArray(np.tile([.5,.5],8).tolist()),False)
    fn.setBlendWeights(path,component,om.MDoubleArray([0.]*8))
    cmds.select(clear=True)
    manager.import_skins(target,replace_existing=True,import_method='index',import_wrinkles=False)
    restored,count=fn.getWeights(path,component)
    assert np.array_equal(np.asarray(restored).reshape((8,2)),expected_weights)
    assert np.array_equal(np.asarray(fn.getBlendWeights(path,component)),expected_blend)
    compact=str(Path(directory)/'compact.skc')
    cmds.select(mesh);manager.export_skins(compact,lossless=False)
    old=json.loads(Path(compact).read_text())
    old_row=next(v[0] for k,v in old.items() if not k.startswith('__'))
    assert old_row['weight_encoding']=='legacy_rounded_5'
    assert not any(1e-12 in r['vw'] for r in old_row['sparse_weights'].values())
print('PASS lossless native SKC: sparse logical indices, tiny positive weights, full precision, DQ masks, replacement import and explicit legacy encoding',flush=True)

from maya_tools.scripts.tools import bifrost_wrinkles as bw
setup=bw.build(mesh,'PrecisionWrinkles',in_place=True,hide_source=False)
graph_input='PrecisionWrinklesGraphShape.AnimatedFace'
source_before=cmds.connectionInfo(graph_input,sourceFromDestination=True)
output_before=cmds.connectionInfo(shape+'.inMesh',sourceFromDestination=True)
presets=bw.export_setups()
with tempfile.TemporaryDirectory() as directory:
    target=str(Path(directory)/'in_place.skc')
    cmds.select(clear=True);manager.export_skins(target)
    data=json.loads(Path(target).read_text())
    exported=[s['name'] for k,v in data.items() if not k.startswith('__') for s in v]
    assert skin in exported,'In-place Bifrost must not hide the native polygon skin'
    assert data[manager.WRINKLES_KEY]==presets
    assert cmds.connectionInfo(graph_input,sourceFromDestination=True)==source_before
    assert cmds.connectionInfo(shape+'.inMesh',sourceFromDestination=True)==output_before
    try:
        with bw.primary_inputs_for_skin_export():
            assert not cmds.connectionInfo(graph_input,sourceFromDestination=True)
            with bw.primary_inputs_for_skin_export():
                assert not cmds.connectionInfo(graph_input,sourceFromDestination=True)
            raise RuntimeError('Deliberate scope failure')
    except RuntimeError as error:
        assert str(error)=='Deliberate scope failure'
    assert cmds.connectionInfo(graph_input,sourceFromDestination=True)==source_before
    assert cmds.connectionInfo(shape+'.inMesh',sourceFromDestination=True)==output_before
print('PASS in-place Bifrost SKC: native skin included, original presets, nested scope and failure route restoration',flush=True)

layered=cmds.polyCube(name='interleavedMesh')[0]
inner=cmds.skinCluster([one,two],layered,toSelectedBones=True,name='innerSkin')[0]
target=cmds.duplicate(layered,name='interleavedTarget')[0];cmds.delete(target,constructionHistory=True)
cmds.move(.2,target+'.vtx[0]',relative=True)
corrective=cmds.blendShape(target,layered,after=True,name='betweenSkinsCorrective')[0]
cmds.setAttr(corrective+'.weight[0]',.7)
outer=cmds.skinCluster([one,two],layered,toSelectedBones=True,multi=True,name='outerSkin')[0]
cmds.reorderDeformers(outer,corrective,layered)
layered_shape=cmds.listRelatives(layered,shapes=True,noIntermediate=True,fullPath=True)[0]
plugs=[n+'.input[0].inputGeometry' for n in (inner,corrective,outer)]+[layered_shape+'.inMesh']
routes={p:cmds.connectionInfo(p,sourceFromDestination=True) for p in plugs}
assert routes[outer+'.input[0].inputGeometry'].split('.')[0]==corrective
before=np.asarray(om.MFnMesh(om.MSelectionList().add(layered_shape).getDagPath(0)).getPoints()).copy()
with tempfile.TemporaryDirectory() as directory:
    target=str(Path(directory)/'interleaved.skc')
    cmds.select(layered);manager.export_skins(target)
    data=json.loads(Path(target).read_text())
    data={k:v for k,v in data.items() if not k.startswith('__')}
    Path(target).write_text(json.dumps(data))
    manager.import_skins(target,replace_existing=True,import_method='index',import_wrinkles=False)
    assert {p:cmds.connectionInfo(p,sourceFromDestination=True) for p in plugs}==routes
    after=np.asarray(om.MFnMesh(om.MSelectionList().add(layered_shape).getDagPath(0)).getPoints())
    assert np.array_equal(after,before)
print('PASS replacement SKC preserves an interleaved corrective, native routes and evaluated geometry',flush=True)
