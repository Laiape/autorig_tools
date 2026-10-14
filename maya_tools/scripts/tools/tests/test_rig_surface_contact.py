"""Native Maya world-space region distance and closed surface penetration."""
import os,sys,tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as r,rig_surface_contact as contact,rig_validation as qa,rig_profiles as profiles
    root=cmds.createNode('transform',name='Character')
    body=cmds.polyCube(width=4,height=4,depth=4)[0];body=cmds.parent(body,root)[0]
    cloth=cmds.polyPlane(width=1,height=1,subdivisionsX=1,subdivisionsY=1)[0];cloth=cmds.parent(cloth,root)[0]
    r.bind(root,body,'body.render',module='body',kind='mesh')
    r.bind(root,cloth,'body.garment',module='body',kind='mesh')
    spec={'source':{'role':'body.garment','module':'body'},'target':{'role':'body.render','module':'body'},'mode':'closed','max_penetration':.01}
    # All four cloth vertices lie inside the cube, although no rig landmarks exist.
    result=contact.measure(root,spec)
    assert not result['pass'] and len(result['offending_vertices'])==4 and result['max_penetration']>1.4
    cmds.setAttr(cloth+'.translateY',2.1)
    assert contact.measure(root,spec)['pass']
    # World transforms must not alter the classification.
    cmds.setAttr(root+'.translateX',30);cmds.setAttr(root+'.rotateZ',27)
    result=contact.measure(root,spec);assert result['pass'] and result['max_penetration']==0
    spec['mode']='proximity';spec.pop('max_penetration');spec['max_gap']=.11
    assert contact.measure(root,spec)['pass']
    spec['max_gap']=.05;assert not contact.measure(root,spec)['pass']
    # Open surfaces cannot be reported as valid closed-mesh containment.
    invalid=dict(spec,mode='closed',target=spec['source'],source=spec['target'])
    try:contact.measure(root,invalid);raise AssertionError('Open containment accepted')
    except ValueError:pass
    profile=profiles.preset('custom');profile['contacts']=[spec]
    with tempfile.TemporaryDirectory() as tmp:
        report=qa.run_report(root,[cloth,body],str(Path(tmp)/'contact.json'),cases=profile,captures=False,repeats=1)
        assert not report['quality_pass'] and report['poses'][0]['contacts'][0]['offending_vertices']
    print('PASS surface contacts: closed penetration, clearance, world transforms, open-region proximity, closed guard, QA integration')
finally:maya.standalone.uninitialize()
