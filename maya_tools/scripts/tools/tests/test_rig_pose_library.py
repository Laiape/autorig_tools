"""Real Maya portable poses, camera reference and unchanged animated report review."""
import os,sys,tempfile,json,copy
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as roles,rig_pose_library as bank,rig_validation as qa
    root=cmds.createNode('transform',name='Bird')
    control=cmds.createNode('transform',name='FeatherBend',parent=root)
    roles.bind(root,control,'wing.fold','L','wing')
    joint=cmds.createNode('joint',parent=root);cmds.connectAttr(control+'.rotate',joint+'.rotate')
    mesh=cmds.polyCube()[0];mesh=cmds.parent(mesh,root)[0];cmds.skinCluster(joint,mesh,toSelectedBones=True)
    roles.bind(root,mesh,'body.render',module='body',kind='mesh')
    camera,camera_shape=cmds.camera()
    neutral=bank.capture(root,'neutral',camera)
    cmds.setAttr(control+'.rotateZ',65);fold=bank.capture(root,'fold',camera)
    library=bank.library([neutral,fold])
    control=cmds.rename(control,'WingAnimator')
    bank.apply(root,neutral);assert cmds.getAttr(control+'.rotateZ')==0
    bank.apply(root,fold);assert cmds.getAttr(control+'.rotateZ')==65
    cmds.setKeyframe(control,attribute='rotateZ',time=1,value=10)
    cmds.setKeyframe(control,attribute='rotateZ',time=10,value=20);cmds.currentTime(5)
    before=cmds.getAttr(control+'.rotateZ')
    try:bank.apply(root,fold);raise AssertionError('Animated channels overwritten')
    except ValueError:pass
    with tempfile.TemporaryDirectory() as tmp:
        path=str(Path(tmp)/'first.rigqa.json')
        bank.review(root,[mesh],library,path,captures=False)
        report=bank.review(root,[mesh],library,str(Path(tmp)/'second.rigqa.json'),baseline=path,captures=False)
        assert report['quality_pass'] and all(c['max']<1e-6 for c in report['comparison'])
        changed=copy.deepcopy(report)
        stored=next(iter(changed['poses'][0]['meshes'].values()));stored['points'][0][0]+=.2
        original_colors=cmds.polyColorSet(mesh,q=True,allColorSets=True)
        preview=bank.color_difference(root,mesh,changed,json.loads(Path(path).read_text()),'neutral')
        assert abs(preview['max_difference']-.2)<1e-6
        assert cmds.polyColorSet(mesh,q=True,allColorSets=True)==original_colors
        assert 'bakeError' in cmds.polyColorSet(preview['preview'],q=True,allColorSets=True)
        cmds.undo();assert not cmds.objExists(preview['preview'])
    assert abs(cmds.getAttr(control+'.rotateZ')-before)<1e-7
    assert fold['camera']['settings']['focalLength']==cmds.getAttr(camera_shape+'.focalLength')
    # Reuse the same poses on different names without source-rig coupling.
    other=cmds.createNode('transform',name='Bat');other_control=cmds.createNode('transform',name='Membrane',parent=other)
    roles.bind(other,other_control,'wing.fold','L','wing')
    bank.apply(other,fold);assert cmds.getAttr(other_control+'.rotateZ')==65
    assert abs(cmds.getAttr(control+'.rotateZ')-before)<1e-7
    print('PASS pose library: capture camera, rename, different rig, undoable application, animated guard, baseline comparison and preserved animation')
finally:maya.standalone.uninitialize()
