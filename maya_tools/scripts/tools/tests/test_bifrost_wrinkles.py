"""Run with mayapy: native Bifrost deformation, bypass and saved-scene regression."""
import os,sys,math,tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
import maya.api.OpenMaya as om
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bifrost_wrinkles as bw


def positions(mesh):
    shape,path,fn=bw._mesh_fn(mesh)
    cmds.dgeval(shape+'.outMesh')
    return np.asarray([[p.x,p.y,p.z] for p in fn.getPoints()])


try:
    cmds.file(new=True,force=True)
    source=cmds.polyPlane(w=8,h=8,sx=12,sy=12,ch=False)[0]
    deformers=cmds.createNode('transform',name='deformers_GRP')
    cmds.setAttr(deformers+'.translateX',13)
    cmds.setAttr(deformers+'.rotateY',20)
    cmds.setAttr(deformers+'.scaleX',2)
    shape,path,fn=bw._mesh_fn(source)
    rest=positions(source)
    patterns={r:[1. if r=='Forehead' else 0. for _ in rest] for r in bw.REGIONS}
    setup=bw.build(source,prefix='TestWrinkles',patterns=patterns)
    output,settings=setup['output'],setup['settings']
    assert cmds.listRelatives(setup['group'],parent=True)==[deformers]
    assert np.allclose(cmds.getAttr(output+'.worldMatrix[0]'),cmds.getAttr(source+'.worldMatrix[0]'))
    assert np.allclose(positions(output),rest,atol=2e-5)
    cmds.setAttr(settings+'.ManualActivation',1)
    assert np.allclose(positions(output)-rest,[0,.3,0],atol=2e-5)
    cmds.setAttr(settings+'.Forehead',0)
    assert np.allclose(positions(output),rest,atol=2e-5)
    cmds.setAttr(settings+'.Forehead',1)
    cmds.setAttr(settings+'.ManualActivation',0)
    # Uniform in-plane compression has a known analytic response.
    compressed=rest.copy();compressed[:,[0,2]]*=.9
    fn.setPoints(om.MPointArray([om.MPoint(*p) for p in compressed]))
    amount=(.1-.015)/.1
    expected=.3*amount*amount*(3-2*amount)
    assert np.allclose(positions(output)-compressed,[0,expected,0],atol=3e-5)
    cmds.setAttr(settings+'.Envelope',0)
    assert np.allclose(positions(output),compressed,atol=2e-5)
    cmds.setAttr(settings+'.Envelope',1)
    # Stretch and rigid motion produce no compression-driven wrinkles.
    stretched=rest.copy();stretched[:,[0,2]]*=1.2
    fn.setPoints(om.MPointArray([om.MPoint(*p) for p in stretched]))
    assert np.allclose(positions(output),stretched,atol=2e-5)
    matrix=om.MTransformationMatrix()
    matrix.setRotation(om.MEulerRotation(.3,.5,-.4))
    matrix.setTranslation(om.MVector(2,3,4),om.MSpace.kTransform)
    rigid=np.asarray([[q.x,q.y,q.z] for q in [om.MPoint(*p)*matrix.asMatrix() for p in rest]])
    fn.setPoints(om.MPointArray([om.MPoint(*p) for p in rigid]))
    assert np.allclose(positions(output),rigid,atol=2e-5)
    # Runtime is serialized Bifrost; reopening needs no builder callbacks.
    fn.setPoints(om.MPointArray([om.MPoint(*p) for p in compressed]))
    before=positions(output)
    with tempfile.TemporaryDirectory(prefix='bifrost_wrinkles_') as directory:
        scene=str(Path(directory)/'wrinkles.mb')
        cmds.file(rename=scene);cmds.file(save=True,type='mayaBinary',force=True)
        cmds.file(new=True,force=True)
        cmds.file(scene,open=True,force=True)
        assert cmds.polyEvaluate(output,v=True)==len(rest)
        assert np.allclose(positions(output),before,atol=2e-5)
    assert not (cmds.ls(type='expression') or [])
    print('PASS Bifrost wrinkles: neutral, analytic compression, stretch/rigid invariance, region controls, bypass and persistence',flush=True)
finally:
    maya.standalone.uninitialize()
