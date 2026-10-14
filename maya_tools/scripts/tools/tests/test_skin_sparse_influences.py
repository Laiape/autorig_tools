"""Real Maya: logical influence holes must survive dense skin reconstruction."""
import os,sys,tempfile,json
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
try:
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    manager=SkinManager.__new__(SkinManager);manager.k_skin_attrs=[];manager.tolerance=1e-5
    joints=[]
    for name,pos in (('root',(0,0,0)),('removed',(0,1,0)),('tip',(0,2,0)),('tail',(2,0,0))):
        cmds.select(clear=True);joints.append(cmds.joint(name=name,position=pos))
    mesh=cmds.polyPlane(width=4,height=4,subdivisionsX=2,subdivisionsY=2)[0]
    skin=cmds.skinCluster(joints,mesh,toSelectedBones=True,name='sparseSkin')[0]
    cmds.skinPercent(skin,mesh,transformValue=[('root',.2),('removed',0),('tip',.3),('tail',.5)])
    cmds.skinCluster(skin,edit=True,removeInfluence='removed')
    def skin_fn():
        sel=om.MSelectionList();sel.add(skin);return oma.MFnSkinCluster(sel.getDependNode(0))
    fn=skin_fn();logical=[fn.indexForInfluenceObject(p) for p in fn.influenceObjects()]
    assert logical==[0,2,3],logical
    def posed():
        cmds.setAttr('tip.rotateX',25);cmds.setAttr('tail.rotateZ',-40)
        sel=om.MSelectionList();sel.add(mesh);path=sel.getDagPath(0);path.extendToShape()
        result=om.MFnMesh(path).getPoints()
        return om.MPointArray(result)
    with tempfile.TemporaryDirectory() as folder:
        path=str(Path(folder)/'sparse.skc');cmds.select(mesh);manager.export_skins(path)
        expected=posed();cmds.setAttr('tip.rotateX',0);cmds.setAttr('tail.rotateZ',0)
        cmds.delete(mesh,constructionHistory=True)
        assert not cmds.objExists(skin),'Source skin survived history deletion'
        manager.import_skins(path,replace_existing=True)
        actual=posed();error=max((a-b).length() for a,b in zip(actual,expected))
        assert error<1e-5,error
        fn=skin_fn()
        assert len(fn.influenceObjects())==3
    print('PASS sparse influence reconstruction: logical [0,2,3] remapped to dense slots, correct bind matrices and posed geometry')
finally:maya.standalone.uninitialize()
