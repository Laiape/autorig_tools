"""Real Maya combination weights, sculpt, dependencies and SKC recovery."""
import os, sys, tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
from maya import cmds

def run():
    maya.standalone.initialize(name='python')
    try:
        from maya_tools.scripts.tools import pose_blendshapes as p, combination_correctives as c
        from maya_tools.scripts.tools.skin_manager_api import SkinManager
        root = cmds.createNode('transform', name='Character')
        mesh = cmds.polyPlane(name='face', subdivisionsX=3, subdivisionsY=3)[0]
        cmds.parent(mesh, root)
        a = cmds.createNode('transform', name='Jaw_CTL', parent=root)
        b = cmds.createNode('transform', name='Smile_CTL', parent=root)
        joint = cmds.createNode('joint', parent=root)
        cmds.skinCluster(joint, mesh, toSelectedBones=True)
        bs = p.create_blendshape(mesh)
        cmds.setAttr(a+'.rotateX',30)
        one,_ = p.add_target(mesh,bs,a); p.finish_edit(False)
        cmds.setAttr(a+'.rotateX',0); cmds.setAttr(b+'.translateX',5)
        two,_ = p.add_target(mesh,bs,b); p.finish_edit(False)
        idx,_=c.create(mesh,bs,[one,two],'JawSmile_BLS')
        cmds.move(0,.2,0,mesh+'.vtx[5]',relative=True,objectSpace=True)
        p.finish_edit()
        for x,y,w in [(0,0,0),(30,0,0),(0,5,0),(30,5,1),(15,2.5,.25)]:
            cmds.setAttr(a+'.rotateX',x);cmds.setAttr(b+'.translateX',y)
            assert abs(cmds.getAttr(bs+'.weight[%d]'%idx)-w)<1e-6
        try:p.remove_target(mesh,bs,one);raise AssertionError('Dependency deletion allowed')
        except ValueError:pass
        p.go_to_pose(bs,idx);assert cmds.getAttr(b+'.translateX')==5
        manager=SkinManager()
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'snapshot.skc');manager.export_skins(path)
            cmds.delete(mesh,constructionHistory=True)
            owned=[]
            for r in p._find(p.POSE_MARKER):owned.extend(cmds.listConnections(r+'.driverNodes',s=True,d=False) or [])
            cmds.delete(list(set(n for n in owned if cmds.objExists(n)))+p._find(p.POSE_MARKER))
            manager.import_skins(path,replace_existing=True)
            assert c.data(p.pose_record(bs,idx))
            cmds.setAttr(a+'.rotateX',15);cmds.setAttr(b+'.translateX',2.5)
            assert abs(cmds.getAttr(bs+'.weight[%d]'%idx)-.25)<1e-6
            scene=str(Path(tmp)/'test.ma');cmds.file(rename=scene);cmds.file(save=True,type='mayaAscii')
            cmds.file(new=True,force=True);cmds.file(scene,open=True,force=True)
            assert abs(cmds.getAttr(bs+'.weight[%d]'%idx)-.25)<1e-6
            p.remove_target(mesh,bs,idx);cmds.undo()
            assert abs(cmds.getAttr(bs+'.weight[%d]'%idx)-.25)<1e-6
        print('PASS combination weights, sculpt, dependencies, SKC, reopen and undo')
    finally:maya.standalone.uninitialize()

if __name__=='__main__':run()
