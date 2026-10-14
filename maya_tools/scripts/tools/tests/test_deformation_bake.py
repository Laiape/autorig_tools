"""Real Maya: general stacks, held-out failure, colors and SKC recovery."""
import os,sys,tempfile,json
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1')
sys.path[:0]=[str(Path(__file__).resolve().parents[4]),str(Path(__file__).resolve().parents[2])]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
try:
    from tools import proximity_bake as bake,proximity_wrap
    from tools.skin_manager_api import SkinManager
    cmds.undoInfo(state=True)
    root=cmds.joint(name='root');tip=cmds.joint(name='tip',position=(0,4,0))
    mesh=cmds.polyCylinder(height=8,subdivisionsAxis=8,subdivisionsHeight=4)[0]
    cmds.skinCluster([root,tip],mesh,toSelectedBones=True)
    sculpt=cmds.duplicate(mesh)[0];cmds.delete(sculpt,constructionHistory=True)
    cmds.move(0,0,.4,sculpt+'.vtx[*]',relative=True,objectSpace=True)
    bs=cmds.blendShape(sculpt,mesh)[0];cmds.delete(sculpt)
    for f,value in ((0,0),(1,1),(2,0),(3,1),(4,0)):
        cmds.setKeyframe(bs,attribute='weight[0]',time=f,value=value)
    for f,value in ((0,0),(2,20),(4,-20)):
        cmds.setKeyframe(tip,attribute='rotateZ',time=f,value=value)
    cmds.currentTime(0)
    cmds.select(mesh)
    before=set(cmds.ls())
    try:
        bake.bake_selected(0,4,2,0,2,error_limit=.01)
        raise AssertionError('Held-out failure accepted')
    except RuntimeError as exc:
        assert 'exceeds limit' in str(exc),exc
    assert set(cmds.ls())==before
    assert cmds.objExists(bs) and cmds.currentTime(query=True)==0
    cmds.select(mesh)
    with tempfile.TemporaryDirectory() as folder:
        output=str(Path(folder)/'baked.skc')
        result=bake.bake_selected(0,4,2,0,2,output,color_error=True)
        assert result['frames']==[0.,2.,4.]
        assert result['validation_frames']==[1.,3.]
        record=result['records'][0]
        train=[r['max'] for r in record['validation'] if r['set']=='fit']
        assert record['held_out_max']>max(train)+.1
        shape=proximity_wrap.mesh_shape(record['destination'])
        selection=om.MSelectionList();selection.add(shape);fn=om.MFnMesh(selection.getDagPath(0))
        assert 'bakeError' in fn.getColorSetNames()
        assert len(fn.getVertexColors('bakeError'))==fn.numVertices
        assert cmds.attributeQuery('bakeValidation',node=record['metadata'],exists=True)
        data=json.loads(Path(output).read_text())
        assert not any(n['name']==bs for n in data[SkinManager.SCENE_DEFORMERS_KEY]['nodes']), ([n['name'] for n in data[SkinManager.SCENE_DEFORMERS_KEY]['nodes']],bs,proximity_wrap.direct_deformers(proximity_wrap.mesh_shape(mesh)))
        cmds.delete(record['destination']);cmds.delete(bs)
        manager=SkinManager();manager.import_skins(output,replace_existing=True)
        assert any(cmds.nodeType(n)=='skinCluster' for n,_ in proximity_wrap.direct_deformers(proximity_wrap.mesh_shape(mesh)))
    # Delta Mush is supported and source deformers remain intact.
    dm=cmds.deltaMush(mesh,smoothingIterations=3)[0]
    cmds.select(mesh)
    result=bake.bake_selected(0,4,2,0,2)
    assert cmds.objExists(dm) and result['records'][0]['held_out_max'] is not None
    print('PASS deformation bake: skin+blendshape/Delta Mush stacks, independent held-out frames, error-limit rollback, color map, native metrics, SKC restore and source preservation')
finally:maya.standalone.uninitialize()
