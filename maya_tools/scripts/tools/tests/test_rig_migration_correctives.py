"""Native orientation and combination dependencies remain independent after migration."""
import os,sys,math
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as r,rig_migration as migrate,pose_blendshapes as p,orientation_correctives as o,combination_correctives as c,rig_validation as qa
    rigs=[]
    for name in ('Old','New'):
        root=cmds.createNode('transform',name=name)
        ref=cmds.createNode('transform',name=name+'_Reference',parent=root);r.bind(root,ref,'body.reference',module='body',kind='reference')
        a=cmds.createNode('transform',name=name+'_Bend',parent=root);r.bind(root,a,'body.bend',module='body')
        b=cmds.createNode('transform',name=name+'_Lift',parent=root);r.bind(root,b,'body.lift',module='body')
        joint=cmds.createNode('joint',name=name+'_Joint',parent=ref);r.bind(root,joint,'body.skin',module='body',kind='joint')
        cmds.connectAttr(a+'.rotate',joint+'.rotate')
        mesh=cmds.polyPlane(subdivisionsX=2,subdivisionsY=2)[0];mesh=cmds.parent(mesh,root)[0]
        r.bind(root,mesh,'body.render',module='body',kind='mesh');rigs.append((root,ref,a,b,joint,mesh))
    root,ref,a,b,joint,mesh=rigs[0]
    cmds.skinCluster(joint,mesh,toSelectedBones=True)
    region=o.create_system(joint,ref,'BodyOrientation',axis='Z')
    bs=p.create_blendshape(mesh)
    cmds.setAttr(a+'.rotateZ',30);one,_=p.add_target(mesh,bs,a,region,pose_type='twist')
    cmds.move(0,.2,0,mesh+'.vtx[4]',relative=True,objectSpace=True);p.finish_edit();cmds.setAttr(a+'.rotateZ',0)
    cmds.setAttr(b+'.translateY',1);two,_=p.add_target(mesh,bs,b)
    cmds.move(0,.1,0,mesh+'.vtx[5]',relative=True,objectSpace=True);p.finish_edit();cmds.setAttr(b+'.translateY',0)
    combined,_=c.create(mesh,bs,[one,two],'BendLift_BLS')
    cmds.move(0,.3,0,mesh+'.vtx[3]',relative=True,objectSpace=True);p.finish_edit()
    cmds.setAttr(a+'.rotateZ',0);cmds.setAttr(b+'.translateY',0)
    assert migrate.preview(root,rigs[1][0])['ready'],migrate.preview(root,rigs[1][0])
    result=migrate.apply(root,rigs[1][0]);assert len(result['targets'])==3
    target_a,target_b,target_mesh=rigs[1][2],rigs[1][3],rigs[1][5]
    target_bs=p.blendshapes(target_mesh)[0]
    for av,bv in ((0,0),(15,.5),(30,1)):
        for aa,bb in ((a,b),(target_a,target_b)):
            cmds.setAttr(aa+'.rotateZ',av);cmds.setAttr(bb+'.translateY',bv)
        assert max(math.dist(x,y) for x,y in zip(qa.mesh_data(mesh)['points'],qa.mesh_data(target_mesh)['points']))<2e-5
        assert abs(cmds.getAttr(bs+'.weight[%d]'%combined)-cmds.getAttr(target_bs+'.weight[2]'))<1e-6
    cmds.setAttr(a+'.rotateZ',0)
    assert cmds.getAttr(target_bs+'.weight[0]')>.999
    print('PASS migration orientation/combination samples, independent destination drivers and neutral/intermediate/extreme geometry')
finally:maya.standalone.uninitialize()
