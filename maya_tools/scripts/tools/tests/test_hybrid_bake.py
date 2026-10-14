"""Native residual bank corrects motion absent from a pure skin fit."""
import os,sys
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path[:0]=[str(Path(__file__).resolve().parents[4]),str(Path(__file__).resolve().parents[2])]
import maya.standalone
from maya import cmds
maya.standalone.initialize(name='python')
try:
    from maya_tools.scripts.tools import hybrid_bake as h,pose_blendshapes as p
    root=cmds.createNode('transform',name='Character');ref=cmds.createNode('joint',parent=root)
    joint=cmds.createNode('joint',parent=ref);ctl=cmds.createNode('transform',name='Jaw_CTL',parent=root)
    cmds.connectAttr(ctl+'.rotateX',joint+'.rotateX')
    mesh=cmds.polyPlane(subdivisionsX=2,subdivisionsY=2)[0];cmds.parent(mesh,root)
    cmds.skinCluster(joint,mesh,tsb=True)
    bs=p.create_blendshape(mesh);cmds.setAttr(ctl+'.rotateX',30)
    idx,_=p.add_target(mesh,bs,ctl);cmds.move(0,.3,0,mesh+'.vtx[4]',r=True,os=True);p.finish_edit()
    for frame,value in ((0,0),(10,30)):cmds.setKeyframe(ctl+'.rotateX',t=frame,v=value)
    cmds.keyTangent(ctl+'.rotateX',itt='linear',ott='linear');cmds.currentTime(0);cmds.select(mesh)
    result=h.bake_with_residuals(0,10,5,ctl,joint,ref,error_limit=.1)
    assert result['targets'] and result['worst_max']<result['plain_worst_max']
    assert max(m['max'] for m in result['validation'] if m['set']=='fit')<1e-4
    assert cmds.currentTime(q=True)==0 and cmds.ls(sl=True)==[mesh]
    print('PASS hybrid native residuals and held-out validation',result['plain_worst_max'],result['worst_max'])
finally:maya.standalone.uninitialize()
