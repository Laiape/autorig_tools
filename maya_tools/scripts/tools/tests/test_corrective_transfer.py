"""Real Maya: changed topology, analytic landmarks, shared pose, SKC and undo."""
import os,sys,tempfile,json
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY","1")
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
try:
    from maya_tools.scripts.tools import corrective_transfer as transfer
    from maya_tools.scripts.tools import pose_blendshapes as poses,orientation_correctives as orient
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    cmds.undoInfo(state=True)
    root=cmds.createNode('transform',name='Character')
    ref=cmds.createNode('transform',name='C_torso',parent=root)
    ctl=cmds.createNode('transform',name='L_shoulder_CTL',parent=root)
    joint=cmds.createNode('joint',name='L_arm_JNT',parent=ref)
    cmds.connectAttr(ctl+'.rotate',joint+'.rotate')
    source=cmds.polyPlane(width=2,height=2,subdivisionsX=1,subdivisionsY=1)[0]
    target=cmds.polyPlane(width=2,height=2,subdivisionsX=3,subdivisionsY=3)[0]
    for mesh in (source,target):
        cmds.parent(mesh,root);cmds.skinCluster(joint,mesh,toSelectedBones=True)
    bs=poses.create_blendshape(source)
    region=orient.create_system(joint,ref,'L_arm_orientation')
    cmds.setAttr(ctl+'.rotateZ',45)
    index,_=poses.add_target(source,bs,ctl,region)
    cmds.move(.1,.2,.3,source+'.vtx[*]',relative=True,objectSpace=True)
    poses.finish_edit()
    cmds.setAttr(ctl+'.rotateZ',0)
    with poses._temporary_values({bs+'.weight[%d]'%index:0}):
        base=poses._mesh_points(source)
    with poses._temporary_values({bs+'.weight[%d]'%index:1}):
        corrected=poses._mesh_points(source)
    expected=np.array([[p.x,p.y,p.z] for p in corrected])-np.array([[p.x,p.y,p.z] for p in base])
    cmds.setAttr(ctl+'.rotateZ',17);cmds.select(ctl)
    result=transfer.transfer_target(source,bs,index,target)
    assert abs(cmds.getAttr(ctl+'.rotateZ')-17)<1e-7
    assert cmds.ls(selection=True)==[ctl]
    dest_bs=result['blendShape'];dest_index=result['index']
    new_record=poses.pose_record(dest_bs,dest_index)
    assert orient.linked(new_record,'orientationSystem')==region
    assert result['transfer']['affected_vertices']==16
    assert result['transfer']['source_topology']!=result['transfer']['target_topology']
    cmds.setAttr(ctl+'.rotateZ',0)
    with poses._temporary_values({dest_bs+'.weight[%d]'%dest_index:0}):
        target_base=poses._mesh_points(target)
    with poses._temporary_values({dest_bs+'.weight[%d]'%dest_index:1}):
        target_result=poses._mesh_points(target)
    actual=np.array([[p.x,p.y,p.z] for p in target_result])-np.array([[p.x,p.y,p.z] for p in target_base])
    assert np.allclose(actual,expected[0],atol=2e-5),(actual,expected)
    for angle in (0,22.5,45):
        cmds.setAttr(ctl+'.rotateZ',angle)
        assert abs(cmds.getAttr(bs+'.weight[%d]'%index)-cmds.getAttr(dest_bs+'.weight[%d]'%dest_index))<1e-6
    poses.remove_target(target,dest_bs,dest_index)
    assert abs(cmds.getAttr(bs+'.weight[%d]'%index)-1)<1e-6,'shared source pose was disabled'
    cmds.undo();assert poses.pose_record(dest_bs,dest_index)
    # Invalid match/mask must roll back all destination nodes and original values.
    before=set(cmds.ls())
    try:
        transfer.transfer_target(source,bs,index,target,vertices=[999])
        raise AssertionError('Invalid region accepted')
    except ValueError: pass
    assert before==set(cmds.ls())
    # Another character gets an independent matching controller SDK, rather
    # than coupling its motion to the source character's orientation region.
    cmds.namespace(add='variant')
    variant_root=cmds.createNode('transform',name='variant:Character')
    variant_control=cmds.createNode('transform',name='variant:L_shoulder_CTL',parent=variant_root)
    variant_mesh=cmds.polyPlane(width=2,height=2,subdivisionsX=2,subdivisionsY=2)[0]
    cmds.parent(variant_mesh,variant_root)
    variant_result=transfer.transfer_target(source,bs,index,variant_mesh)
    variant_record=poses.pose_record(variant_result['blendShape'],variant_result['index'])
    assert poses.linked(variant_record,'controller')==variant_control
    assert not orient.linked(variant_record,'orientationSystem')
    cmds.setAttr(variant_control+'.rotateZ',45)
    assert abs(cmds.getAttr(variant_result['blendShape']+'.weight[0]')-1)<1e-6
    cmds.setAttr(variant_control+'.rotateZ',0)
    # Affine scale registration must also scale displacement vectors correctly.
    target_lm=np.array([[0,0,0],[2,0,0],[0,2,0],[0,0,2]],dtype=float)
    query=np.array([[.4,.8,.2],[1.,.2,.6]])
    mapped,inverse=transfer.landmark_warp(query,target_lm,target_lm*.5)
    assert np.allclose(mapped,query*.5,atol=1e-7)
    assert np.allclose(np.einsum('vi,vij->vj',np.ones_like(query),inverse),2)
    cmds.setAttr(ctl+'.rotateZ',0)
    manager=SkinManager.__new__(SkinManager);manager.k_skin_attrs=[];manager.tolerance=1e-5
    with tempfile.TemporaryDirectory() as folder:
        path=str(Path(folder)/'transfer.skc');cmds.select(clear=True);manager.export_skins(path)
        metadata=json.loads(Path(path).read_text())
        saved=next(p for p in metadata[manager.SCENE_DEFORMERS_KEY]['pose_targets'] if p['name']==new_record)
        assert saved['transfer']['affected_vertices']==16
        native_nodes=[orient.linked(region,a) for a in ('helper','relative','rotation')]+[region]
        for mesh in (source,target):cmds.delete(mesh,constructionHistory=True)
        cmds.delete([n for n in poses._find(poses.POSE_MARKER)])
        remaining=[n for n in native_nodes if n and cmds.objExists(n)]
        if remaining:cmds.delete(remaining)
        manager.import_skins(path,replace_existing=True)
        assert cmds.attributeQuery('transferData',node=poses.pose_record(dest_bs,dest_index),exists=True)
        cmds.setAttr(ctl+'.rotateZ',45)
        assert abs(cmds.getAttr(dest_bs+'.weight[%d]'%dest_index)-1)<1e-6
    assert not (cmds.cycleCheck(all=True,list=True) or [])
    print('PASS corrective transfer: different topology, barycentric sculpts, preserved state, shared orientation, independent cross-rig SDK, delete/undo, invalid-mask rollback, landmark scale/Jacobian, SKC metadata/drivers')
finally:
    maya.standalone.uninitialize()
