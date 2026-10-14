"""Persistent sparse target names and character-wide neutral pose in real Maya."""
import os, sys, json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import pose_blendshapes as tool
try:
    cmds.undoInfo(state=True)
    root=cmds.createNode('transform',name='Character')
    mesh=cmds.polyPlane(name='body')[0]
    cmds.parent(mesh,root)
    control=cmds.createNode('transform',name='L_lipCorner_CTL',parent=root)
    jaw=cmds.createNode('transform',name='C_jaw_CTL',parent=root)
    other=cmds.createNode('transform',name='OtherCharacter')
    unrelated=cmds.createNode('transform',name='R_hand_CTL',parent=other)
    cmds.addAttr(jaw,longName='Follow',attributeType='double',defaultValue=.5,keyable=True)
    bs=tool.create_blendshape(mesh)
    for value in (5,-2,8):
        cmds.setAttr(control+'.translateX',value)
        i,name=tool.add_target(mesh,bs,control)
        cmds.move(0,.1,0,mesh+'.vtx[0]',relative=True,worldSpace=True)
        tool.finish_edit(True)
    tool.remove_target(mesh,bs,1)
    expected=tool.targets(bs)
    assert [i for i,name in expected]==[0,2]
    for i,name in expected:
        cmds.aliasAttr(bs+'.weight[%d]'%i,remove=True)
    assert tool.targets(bs)==expected
    assert len(tool.restore_target_names(bs))==2
    assert tool.targets(bs)==expected
    tool.begin_edit(mesh,bs,0,restore_pose=True)
    # Simulate an alias reset during native target array editing.
    for i,name in expected:
        cmds.aliasAttr(bs+'.weight[%d]'%i,remove=True)
    tool.finish_edit(False)
    assert tool.targets(bs)==expected
    assert len(cmds.aliasAttr(bs,q=True))==4
    cmds.setAttr(control+'.translateX',3)
    cmds.setAttr(jaw+'.rotateX',30)
    cmds.setAttr(jaw+'.scaleY',2)
    cmds.setAttr(jaw+'.Follow',.9)
    cmds.setAttr(unrelated+'.translateY',11)
    result=tool.neutral_pose(mesh)
    assert result['controls']==2 and result['channels']==4
    assert cmds.getAttr(control+'.translateX')==0
    assert cmds.getAttr(jaw+'.rotateX')==0
    assert cmds.getAttr(jaw+'.scaleY')==1
    assert cmds.getAttr(jaw+'.Follow')==.5
    assert cmds.getAttr(unrelated+'.translateY')==11
    cmds.undo()
    assert cmds.getAttr(control+'.translateX')==3 and cmds.getAttr(jaw+'.Follow')==.9
    print('PASS: sparse aliases, recovery, cancel preservation, whole-rig neutral defaults, other-character isolation and undo')
finally:
    maya.standalone.uninitialize()
