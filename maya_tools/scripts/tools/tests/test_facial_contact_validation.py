"""Detect a bad contact and restore animated channels and selection."""
import os,sys,tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
from maya import cmds
maya.standalone.initialize(name='python')
try:
    from maya_tools.scripts.tools import facial_contact_validation as f
    root=cmds.createNode('transform',name='Character')
    ctl=cmds.createNode('transform',name='C_jaw_CTL',parent=root)
    cmds.addAttr(ctl,ln='stickyLips',at='double',min=0,max=1,k=True)
    upper=cmds.createNode('transform',parent=root);lower=cmds.createNode('transform',parent=root)
    mesh=cmds.polyPlane()[0];cmds.parent(mesh,root)
    cmds.setAttr(upper+'.translateY',1)
    cmds.setDrivenKeyframe(upper+'.translateY',cd=ctl+'.stickyLips',dv=0,v=1)
    cmds.setDrivenKeyframe(upper+'.translateY',cd=ctl+'.stickyLips',dv=1,v=0)
    cmds.setAttr(ctl+'.rotateX',7);cmds.select(mesh)
    before=cmds.ls(sl=True,long=True)
    with tempfile.TemporaryDirectory() as tmp:
        good=f.run(root,[mesh],str(Path(tmp)/'good.json'),[(upper,lower)],[('close',{'C_jaw_CTL.stickyLips':1})],samples=5)
        assert good['sequences'][0]['closed_contact_pass'] and good['sequences'][0]['max_reverse_difference']==0
        cmds.setAttr(lower+'.translateY',-.3)
        bad=f.run(root,[mesh],str(Path(tmp)/'bad.json'),[(upper,lower)],[('close',{'C_jaw_CTL.stickyLips':1})],samples=5)
        assert not bad['sequences'][0]['closed_contact_pass']
    assert cmds.getAttr(ctl+'.rotateX')==7 and cmds.ls(sl=True,long=True)==before
    print('PASS continuous contact detection, reverse equality and state restoration')
finally:maya.standalone.uninitialize()
