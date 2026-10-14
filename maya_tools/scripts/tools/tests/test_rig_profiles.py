"""Real Maya semantic reports on rigs with unrelated names and proportions."""
import os, sys, tempfile, copy
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as roles, rig_profiles as profiles, rig_validation as qa
    root = cmds.createNode('transform', name='CustomCreature')
    ctl = cmds.createNode('transform', name='FrontBend', parent=root)
    joint = cmds.createNode('joint', parent=root)
    cmds.connectAttr(ctl+'.rotate', joint+'.rotate')
    mesh = cmds.polySphere(subdivisionsX=8, subdivisionsY=6)[0]; mesh = cmds.parent(mesh, root)[0]
    cmds.skinCluster(joint, mesh, toSelectedBones=True)
    roles.bind(root, ctl, 'arm.upper.fk', 'L', 'arm')
    roles.bind(root, mesh, 'body.render', module='body', kind='mesh')
    profile = profiles.preset('custom')
    profile['cases'].append(dict(name='bend', channels=[profiles.channel('arm.upper.fk', 'rotateZ', 80, 'L', 'arm')]))
    profile['transitions'] = [dict(start='neutral', end='bend', samples=11, max_step=.2)]
    reference=cmds.createNode('transform',name='MatchReference',parent=root)
    cmds.connectAttr(ctl+'.rotate',reference+'.rotate')
    roles.bind(root,reference,'arm.match',side='L',module='arm',kind='reference')
    profile['checks']=[dict(name='space_or_ik_match',type='matrix_match',a=dict(role='arm.upper.fk',side='L',module='arm'),b=dict(role='arm.match',side='L',module='arm',kind='reference'))]
    cmds.setKeyframe(ctl, attribute='rotateZ', time=1, value=10)
    cmds.setKeyframe(ctl, attribute='rotateZ', time=10, value=20)
    cmds.currentTime(5); cmds.select(ctl)
    value = cmds.getAttr(ctl+'.rotateZ')
    connection = cmds.connectionInfo(ctl+'.rotateZ', sourceFromDestination=True)
    with tempfile.TemporaryDirectory() as tmp:
        baseline = str(Path(tmp)/'first.rigqa.json')
        first = qa.run_report(root, [mesh], baseline, cases=profile, captures=False, repeats=1)
        assert first['quality_pass'] and first['transitions'][0]['max_reverse_difference'] < 1e-6
        ctl = cmds.rename(ctl, 'RenamedCustomBend'); mesh = cmds.rename(mesh, 'OtherGeometryName')
        second = qa.run_report(root, [mesh], str(Path(tmp)/'second.json'), baseline=baseline, cases=profile, captures=False, repeats=1)
        assert second['quality_pass'] and all(c['max'] < 1e-6 for c in second['comparison'])
        assert cmds.connectionInfo(ctl+'.rotateZ', sourceFromDestination=True) == connection
        assert abs(cmds.getAttr(ctl+'.rotateZ')-value) < 1e-7 and cmds.currentTime(q=True)==5
        assert cmds.ls(selection=True)==[ctl]
        failing = copy.deepcopy(profile); failing['transitions'][0]['max_step'] = .001
        assert not qa.run_report(root, [mesh], str(Path(tmp)/'bad.json'), cases=failing, captures=False, repeats=1)['quality_pass']
        cmds.setAttr(reference+'.translateX',.5)
        bad_match=qa.run_report(root,[mesh],str(Path(tmp)/'bad_match.json'),cases=profile,captures=False,repeats=1)
        assert not bad_match['quality_pass'] and bad_match['poses'][0]['checks'][0]['position_difference']>.49
        cmds.setAttr(reference+'.translateX',0)
        missing = profiles.preset('face')
        report = qa.run_report(root, [mesh], str(Path(tmp)/'missing.json'), cases=missing, captures=False, repeats=1)
        assert not report['quality_pass'] and len(report['poses'])==1 and report['missing_channels']
        # Same functionality, different anatomy/proportions, same portable profile.
        second_root = cmds.createNode('transform', name='Biped')
        second_ctl = cmds.createNode('transform', name='L_shoulderFk_CTL', parent=second_root)
        second_joint = cmds.createNode('joint', parent=second_root)
        cmds.connectAttr(second_ctl+'.rotate', second_joint+'.rotate')
        second_mesh = cmds.polyCube()[0]; second_mesh = cmds.parent(second_mesh, second_root)[0]
        cmds.skinCluster(second_joint, second_mesh, toSelectedBones=True)
        roles.discover(second_root)
        portable=copy.deepcopy(profile);portable['checks']=[]
        report = qa.run_report(second_root,[second_mesh],str(Path(tmp)/'biped.json'),cases=portable,captures=False,repeats=1)
        assert len(report['poses'])==2 and not report['missing_channels']
    print('PASS portable profiles: custom creature/biped, rename-safe comparison, thresholds, missing roles, forward/reverse, animation/state restoration')
finally:
    maya.standalone.uninitialize()
