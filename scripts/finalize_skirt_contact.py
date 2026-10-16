"""Verify the final module adapter against the accepted native deformation."""
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import skirt_contact as skirt, dress_keepout_chains as dress, rig_profiles

FOLDER = ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
QUALITY = json.loads((FOLDER/'validation_v003.json').read_text())
assert QUALITY['passed']
SOURCE = Path(QUALITY['source'])
ACCEPTED = Path(QUALITY['delivery'])
version = 4
while (FOLDER/('final_delivery_v%03d.json' % version)).exists():
    version += 1
DELIVERY = ACCEPTED.with_name('Nini_skirt_contact_v%03d.ma' % version)
REPORT = FOLDER/('final_delivery_v%03d.json' % version)
assert not DELIVERY.exists()
report = {'passed': False, 'source': str(SOURCE), 'delivery': str(DELIVERY),
          'quality_reference': str(FOLDER/'validation_v003.json'),
          'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
              (Path(skirt.__file__), Path(dress.__file__), Path(skirt.__file__).with_name('skirt_surface_contact.py'))}}
POSES = {'neutral': ((0,0,0),(0,0,0)), 'left_step': ((0,15,18),(0,0,0)),
         'right_step': ((0,0,0),(0,15,18)), 'both_up': ((0,14,15),(0,14,15)),
         'spread': ((14,4,0),(-14,4,0)), 'held_left': ((0,9,12),(0,0,0)),
         'cross_left': ((-9,5,7),(2,0,0)), 'cross_right': ((-2,0,0),(9,5,7))}
MESHES = ('c_tunic_GEO','c_embroider_GEO','c_body_GEO')

def snapshot():
    return {m: dress.mesh_points(m) for m in MESHES}

def error(a,b):
    return max(math.dist(p,q) for m in a for p,q in zip(a[m], b[m]))

def pose(name):
    for side,delta in zip(('L','R'), POSES[name]):
        cmds.xform(side+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[side],delta)])

try:
    cmds.file(str(ACCEPTED), open=True, force=True)
    cmds.evaluationManager(mode='off')
    rest = {s: cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
    expected = {}
    for name in POSES:
        pose(name); expected[name] = snapshot()
    cmds.file(str(SOURCE), open=True, force=True)
    cmds.evaluationManager(mode='off')
    # The archived base rig has its own global-transform limitations. Keep
    # this distinct from equivalence to the accepted skirt deformation.
    pose('held_left')
    body_before = dress.mesh_points('c_body_GEO')
    cmds.setAttr('C_masterwalk_CTL.globalScale',.5)
    body_after = dress.mesh_points('c_body_GEO')
    report['source_uniform_scale_error_cm'] = max(math.dist(tuple(v*.5 for v in p),q)
                                                 for p,q in zip(body_before,body_after))
    cmds.setAttr('C_masterwalk_CTL.globalScale',1)
    pose('neutral')
    start = time.perf_counter()
    module = skirt.SkirtContactModule('NiniDress_Module_GRP')
    info = module.make()
    report['build_seconds'] = time.perf_counter()-start
    cmds.evaluationManager(mode='off')
    report['equivalence'] = {}
    for name in POSES:
        pose(name)
        difference = error(expected[name], snapshot())
        report['equivalence'][name] = difference
        assert difference <= 1e-4, (name, difference)
    data = skirt._data()
    env = cmds.listRelatives('skeletonHierarchy_GRP',allDescendents=True,type='joint') or []
    report['hierarchy'] = {'root': cmds.ls('rig_GRP',long=True)[0],
        'mechanics': cmds.ls(info['group'],long=True)[0],
        'controllers': cmds.ls(info['controls_group'],long=True)[0],
        'skeleton': cmds.ls(module.skeleton_grp,long=True)[0], 'env_joint_count': len(env)}
    assert env and all(n.endswith('_ENV') for n in env)
    assert info['controls_group'].endswith('Controllers_GRP')
    assert '|rig_GRP|modules_GRP|' in report['hierarchy']['mechanics']
    assert '|rig_GRP|skel_GRP|' in report['hierarchy']['skeleton']
    assert '|controls_GRP|' in report['hierarchy']['controllers']
    # Test final geometry covariance, including the sparse surface correction.
    pose('held_left')
    reference = snapshot()
    global_ctl = 'C_masterwalk_CTL'
    global_rest = {'scale':cmds.getAttr(global_ctl+'.globalScale'),
                   'rotate':cmds.getAttr(global_ctl+'.rotate')[0],
                   'translate':cmds.getAttr(global_ctl+'.translate')[0]}
    root_matrix = om.MMatrix(cmds.xform(global_ctl,q=True,ws=True,matrix=True))
    report['global_transforms'] = []
    for scale,rotation,translation in ((.5,(0,0,0),(0,0,0)),(2,(0,0,0),(0,0,0)),
                                        (1,(0,35,0),(12,4,-7)),(1,(12,0,-8),(0,0,0))):
        cmds.setAttr(global_ctl+'.globalScale',scale)
        cmds.setAttr(global_ctl+'.rotate',*rotation,type='double3')
        cmds.setAttr(global_ctl+'.translate',*translation,type='double3')
        transform = root_matrix.inverse()*om.MMatrix(cmds.xform(global_ctl,q=True,ws=True,matrix=True))
        target = {m:[tuple(om.MPoint(*p)*transform)[:3] for p in ps] for m,ps in reference.items()}
        actual = snapshot()
        difference = error(target,actual)
        report['global_transforms'].append({'scale':scale,'rotation':rotation,
            'translation':translation,'max_error_cm':difference,
            'per_mesh_error_cm':{m:error({m:target[m]},{m:actual[m]}) for m in MESHES}})
        report['global_transforms'][-1]['accepted'] = difference <= 1e-4
        print('SKIRT_GLOBAL='+json.dumps(report['global_transforms'][-1]),flush=True)
    cmds.setAttr(global_ctl+'.globalScale',global_rest['scale'])
    cmds.setAttr(global_ctl+'.rotate',*global_rest['rotate'],type='double3')
    cmds.setAttr(global_ctl+'.translate',*global_rest['translate'],type='double3')
    report['delivery_scope'] = 'Recorded Nini global transform and scale 1. Global changes with failed covariance are not accepted; base-rig error is recorded separately.'
    pose('neutral')
    resolved,missing,skipped = rig_profiles.resolve_cases('Nini',info['validation_profile'])
    report['test_rig_profile'] = {'cases': len(resolved), 'missing': missing, 'skipped': skipped}
    assert not missing
    skirt.export_validation_profile(FOLDER/('test_rig_v%03d.json' % version))
    skirt.export_preset(FOLDER/('delivery_preset_v%03d.json' % version))
    # Store world snapshots for a fresh process with no project runtime import.
    snapshots = {}
    for name in ('neutral','left_step','right_step','cross_left'):
        pose(name); snapshots[name] = snapshot()
    (FOLDER/('portability_reference_v%03d.json' % version)).write_text(json.dumps(
        {'poses': {n:POSES[n] for n in snapshots}, 'rest':rest, 'snapshots':snapshots}),encoding='ascii')
    pose('neutral')
    cmds.evaluationManager(mode='parallel')
    cmds.select(data['settings'])
    cmds.file(rename=str(DELIVERY));cmds.file(save=True,type='mayaAscii')
    report['delivery_sha256'] = hashlib.sha256(DELIVERY.read_bytes()).hexdigest()
    report['passed'] = True
except BaseException:
    import traceback
    report['error'] = traceback.format_exc()
    raise
finally:
    REPORT.write_text(json.dumps(report,indent=2),encoding='ascii')
    print('SKIRT_FINAL='+json.dumps(report),flush=True)
