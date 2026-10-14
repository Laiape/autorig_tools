"""Real Maya dependency-preserving mirror/transfer across arbitrary rig names."""
import os, sys, tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as roles, pose_blendshapes as p, combination_correctives as c, corrective_transfer as transfer
    cmds.undoInfo(state=True)
    root = cmds.createNode('transform', name='Animal')
    controls = {}
    for side in ('L','R'):
        for role, label in [('a','Stretch'),('b','Lift')]:
            node = cmds.createNode('transform', name=side+label, parent=root)
            roles.bind(root,node,'custom.'+role,side,'custom')
            controls[side,role] = node
    mesh = cmds.polyPlane(width=4,height=4,axis=(0,0,1),subdivisionsX=4,subdivisionsY=4)[0]
    mesh = cmds.parent(mesh,root)[0]
    bs = p.create_blendshape(mesh)
    indices = []
    for role, vertex in [('a',14),('b',19)]:
        ctl = controls['L',role]
        cmds.setAttr(ctl+'.translateY',1)
        i,_ = p.add_target(mesh,bs,ctl)
        cmds.move(0,.1,0,mesh+'.vtx[%d]'%vertex,relative=True,objectSpace=True);p.finish_edit()
        cmds.setAttr(ctl+'.translateY',0);indices.append(i)
    combination,_ = c.create(mesh,bs,indices,'Combined_BLS')
    cmds.move(.2,.4,0,mesh+'.vtx[14]',relative=True,objectSpace=True);p.finish_edit()
    for ctl in controls.values():cmds.setAttr(ctl+'.translateY',0)
    mirrored,_ = p.mirror_target(mesh,bs,combination)
    snapshot = c.data(p.pose_record(bs,mirrored))
    assert len(snapshot['drivers'])==2 and not set(snapshot['drivers']).intersection(indices)
    zero = {bs+'.weight[%d]'%i:0 for i,_ in p.targets(bs)}
    with p._temporary_values(zero):
        base = p._mesh_points(mesh)
        cmds.setAttr(bs+'.weight[%d]'%mirrored,1)
        reflected = p._mesh_points(mesh)
        delta = reflected[10]-base[10]
        assert abs(delta.x+.2)<1e-5 and abs(delta.y-.4)<1e-5
    for value,expected in [(0,0),(.5,.25),(1,1)]:
        for role in ('a','b'):cmds.setAttr(controls['R',role]+'.translateY',value)
        assert abs(cmds.getAttr(bs+'.weight[%d]'%mirrored)-expected)<1e-6
    # Composite capture links survive a control rename.
    controls['R','b'] = cmds.rename(controls['R','b'],'NewRightLift')
    for role in ('a','b'):cmds.setAttr(controls['R',role]+'.translateY',0)
    p.go_to_pose(bs,mirrored)
    assert cmds.getAttr(controls['R','b']+'.translateY')==1
    # Transfer full dependency graph to a different named rig and topology.
    target_root = cmds.createNode('transform',name='OtherSpecies')
    destination_controls = []
    for role in ('a','b'):
        node = cmds.createNode('transform',name='front_'+role,parent=target_root)
        roles.bind(target_root,node,'custom.'+role,'L','custom');destination_controls.append(node)
    target = cmds.polyPlane(width=4,height=4,axis=(0,0,1),subdivisionsX=8,subdivisionsY=8)[0]
    target = cmds.parent(target,target_root)[0]
    result = transfer.transfer_target(mesh,bs,combination,target)
    assert len(result['dependency_targets'])==3
    target_bs, target_i = result['blendShape'],result['index']
    with p._temporary_values({target_bs+'.weight[%d]'%i:0 for i,_ in p.targets(target_bs)}):
        base = p._mesh_points(target)
        cmds.setAttr(target_bs+'.weight[%d]'%target_i,1)
        corrected = p._mesh_points(target)
        assert max((a-b).length() for a,b in zip(base,corrected)) > .4
    for value,expected in [(0,0),(.5,.25),(1,1)]:
        for control in destination_controls:cmds.setAttr(control+'.translateY',value)
        assert abs(cmds.getAttr(target_bs+'.weight[%d]'%target_i)-expected)<1e-6
    try:
        p.remove_target(target,target_bs,result['dependency_targets'][indices[0]])
        raise AssertionError('Transferred dependency deletion accepted')
    except ValueError:pass
    # Unsupported/missing semantic counterparts must fail before altering targets.
    old = set(cmds.ls())
    cmds.delete(destination_controls[1])
    before = set(cmds.ls())
    try:
        transfer.transfer_target(mesh,bs,combination,target)
        raise AssertionError('Missing composite controller accepted')
    except ValueError:pass
    assert before==set(cmds.ls())
    with tempfile.TemporaryDirectory() as tmp:
        scene = str(Path(tmp)/'combined.ma')
        cmds.file(rename=scene);cmds.file(save=True,type='mayaAscii')
        cmds.file(scene,open=True,force=True)
        p.go_to_pose(bs,mirrored)
        assert abs(cmds.getAttr(bs+'.weight[%d]'%mirrored)-1)<1e-6
    print('PASS composite workflows: semantic mirror, dependency weights, rename links, cross-rig/topology transfer, deletion protection, failure rollback, reopen')
finally:
    maya.standalone.uninitialize()
