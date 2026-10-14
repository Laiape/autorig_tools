"""Real Maya version migration preserving motion, exact weights and corrective geometry."""
import os,sys,tempfile,math
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as r,rig_migration as migrate,pose_blendshapes as p,rig_validation as qa,skinning_volume as sv
    cmds.undoInfo(state=True)
    rigs=[]
    for name,ctl_name in [('OldRig','Bend'),('NewRig','CompletelyDifferentName')]:
        root=cmds.createNode('transform',name=name);ctl=cmds.createNode('transform',name=ctl_name,parent=root)
        joint=cmds.createNode('joint',name=name+'_Joint',parent=root);cmds.connectAttr(ctl+'.rotate',joint+'.rotate')
        mesh=cmds.polyPlane(width=2,height=2,subdivisionsX=2,subdivisionsY=2)[0];mesh=cmds.parent(mesh,root)[0]
        r.bind(root,ctl,'body.bend',module='body');r.bind(root,joint,'body.bend.skin',module='body',kind='joint')
        r.bind(root,mesh,'body.render',module='body',kind='mesh');rigs.append((root,ctl,joint,mesh))
    source,source_ctl,source_j,source_mesh=rigs[0];target,target_ctl,target_j,target_mesh=rigs[1]
    source_extra=cmds.createNode('joint',name='OldSecondInfluence',parent=source_j);cmds.setAttr(source_extra+'.translateX',1)
    target_extra=cmds.createNode('joint',name='NewSecondInfluence',parent=target_j);cmds.setAttr(target_extra+'.translateX',1)
    r.bind(source,source_extra,'body.bend.skin',module='body',kind='joint',index=1)
    r.bind(target,target_extra,'body.bend.skin',module='body',kind='joint',index=1)
    skin=cmds.skinCluster([source_j,source_extra],source_mesh,toSelectedBones=True)[0]
    cmds.skinPercent(skin,source_mesh+'.vtx[*]',transformValue=[(source_j,.25),(source_extra,.75)])
    cmds.setAttr(skin+'.skinningMethod',2);cmds.setAttr(skin+'.blendWeights[0:8]',*([.35]*9),size=9)
    bs=p.create_blendshape(source_mesh);cmds.setAttr(source_ctl+'.rotateZ',30)
    index,_=p.add_target(source_mesh,bs,source_ctl);cmds.move(0,.2,0,source_mesh+'.vtx[4]',relative=True,objectSpace=True);p.finish_edit()
    for frame,value in [(1,0),(10,30),(20,-10)]:cmds.setKeyframe(source_ctl,attribute='rotateZ',time=frame,value=value)
    cmds.currentTime(7)
    source_value=cmds.getAttr(source_ctl+'.rotateZ');source_nodes=set(cmds.ls())
    plan=migrate.preview(source,target);assert plan['ready'],plan
    # A failure after native skin creation must remove the entire candidate.
    original=migrate._copy_skin
    def injected(item):
        original(item)
        raise RuntimeError('Injected failure after binding')
    migrate._copy_skin=injected
    try:
        migrate.apply(source,target);raise AssertionError('Failure not propagated')
    except RuntimeError:pass
    finally:migrate._copy_skin=original
    assert not cmds.ls(cmds.listHistory(target_mesh),type='geometryFilter')
    assert set(cmds.ls())==source_nodes
    result=migrate.apply(source,target);assert len(result['animation_curves'])==1 and len(result['skins'])==1 and len(result['targets'])==1
    cmds.undo()
    assert not cmds.ls(cmds.listHistory(target_mesh),type='geometryFilter')
    assert not cmds.connectionInfo(target_ctl+'.rotateZ',sourceFromDestination=True)
    result=migrate.apply(source,target)
    assert abs(cmds.getAttr(source_ctl+'.rotateZ')-source_value)<1e-7
    assert cmds.keyframe(target_ctl,attribute='rotateZ',q=True,timeChange=True)==[1.,10.,20.]
    target_skin=result['skins'][0]
    fn,path,comp=sv.skin_data(target_mesh,target_skin);assert all(abs(w-.35)<1e-6 for w in fn.getBlendWeights(path,comp))
    weights,stride=fn.getWeights(path,comp)
    for i,influence in enumerate(fn.influenceObjects()):
        expected=.25 if influence.fullPathName()==r.path(target_j) else .75
        assert all(abs(weights[v*stride+i]-expected)<1e-7 for v in range(9))
    for frame in (1,5,10,15,20):
        cmds.currentTime(frame)
        assert abs(cmds.getAttr(source_ctl+'.rotateZ')-cmds.getAttr(target_ctl+'.rotateZ'))<1e-7
        a,b=qa.mesh_data(source_mesh),qa.mesh_data(target_mesh)
        assert max(math.dist(x,y) for x,y in zip(a['points'],b['points']))<1e-5
    # Existing target animation is never silently replaced.
    assert not migrate.preview(source,target)['ready']
    with tempfile.TemporaryDirectory() as tmp:
        scene=str(Path(tmp)/'migration.ma');cmds.file(rename=scene);cmds.file(save=True,type='mayaAscii')
        cmds.file(scene,open=True,force=True)
        cmds.currentTime(10);assert abs(cmds.getAttr(target_ctl+'.rotateZ')-30)<1e-7
        assert max(math.dist(x,y) for x,y in zip(qa.mesh_data(source_mesh)['points'],qa.mesh_data(target_mesh)['points']))<1e-5
    print('PASS rig migration: preflight, arbitrary naming, animated curves, exact weights/DQ, corrective geometry, source preservation, destination conflict guard and reopen')
finally:maya.standalone.uninitialize()
