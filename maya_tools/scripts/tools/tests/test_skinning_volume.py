"""Real Maya: twist collapse, local DQ and blend-mask SKC recovery."""
import os,sys,tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
from maya import cmds
maya.standalone.initialize(name='python')
try:
    from maya_tools.scripts.tools import skinning_volume as v
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    root=cmds.createNode('transform',name='Character');ctl=cmds.createNode('transform',name='Twist_CTL',parent=root)
    a=cmds.createNode('joint',parent=root);b=cmds.createNode('joint',parent=root)
    cmds.connectAttr(ctl+'.rotateY',b+'.rotateY')
    mesh=cmds.polyCylinder(subdivisionsX=16,subdivisionsY=4)[0];cmds.parent(mesh,root)
    skin=cmds.skinCluster(a,b,mesh,tsb=True)[0]
    cmds.skinPercent(skin,mesh+'.vtx[*]',transformValue=[(a,.5),(b,.5)])
    count=cmds.polyEvaluate(mesh,vertex=True);mask=[1.]*count
    before=cmds.getAttr(skin+'.skinningMethod')
    with tempfile.TemporaryDirectory() as tmp:
        report=v.compare(root,mesh,skin,str(Path(tmp)/'comparison.json'),[('neutral',{}),('twist',{'Twist_CTL.rotateY':180})],mask)
        linear=report['variants']['linear'][1]['metrics']['principal_rms'][0]
        dq=report['variants']['local_blend'][1]['metrics']['principal_rms'][0]
        assert dq>.1 and linear<dq*.01,(linear,dq)
        assert cmds.getAttr(skin+'.skinningMethod')==before and cmds.getAttr(ctl+'.rotateY')==0
        v.apply_mask(mesh,skin,mask)
        cmds.undo()
        assert cmds.getAttr(skin+'.skinningMethod')==before
        fn,p,c=v.skin_data(mesh,skin);assert max(fn.getBlendWeights(p,c))<1e-8
        v.apply_mask(mesh,skin,mask)
        path=str(Path(tmp)/'skin.skc');manager=SkinManager();cmds.select(mesh);manager.export_skins(path)
        cmds.delete(mesh,constructionHistory=True);manager.import_skins(path,replace_existing=True)
        restored=(cmds.ls(cmds.listHistory(mesh),type='skinCluster') or [])[0]
        assert cmds.getAttr(restored+'.skinningMethod')==2
        fn,p,c=v.skin_data(mesh,restored);assert min(fn.getBlendWeights(p,c))>.999
    print('PASS native twist preservation, restored comparison state and local blend SKC recovery')
finally:maya.standalone.uninitialize()
