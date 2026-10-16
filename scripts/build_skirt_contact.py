"""Build a versioned skirt-contact candidate without touching the artist scene."""
import hashlib
import json
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
from maya_tools.scripts.tools import dress_keepout_chains as dress, skirt_contact as skirt

directory = ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
directory.mkdir(parents=True, exist_ok=True)
version = 1
while (directory/('candidate_v{:03d}.ma'.format(version))).exists():
    version += 1
source = ROOT/'maya_tools/assets/Nini/scenes/Nini_dress_chains_v005.ma'
scene = directory/('candidate_v{:03d}.ma'.format(version))
report_path = directory/('candidate_v{:03d}.json'.format(version))
cmds.file(str(source), open=True, force=True)
cmds.evaluationManager(mode='off')
meshes = ('c_tunic_GEO', 'c_embroider_GEO', 'c_body_GEO')
before = {m: dress.mesh_points(m) for m in meshes}
started = time.perf_counter()
info = skirt.upgrade()
report = {'source': str(source), 'scene': str(scene),
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'runtime': skirt.__file__, 'build_seconds': time.perf_counter()-started,
          'owned_node_count': info['owned_node_count'], 'poses': {},
          'neutral_error': {m: max(map(lambda pq: __import__('math').dist(*pq),
                                     zip(before[m], dress.mesh_points(m)))) for m in meshes}}
data = skirt._data()
rest = {s: cmds.xform(s+'_ankleIk_CTL', q=True, ws=True, t=True) for s in ('L','R')}
poses = {'neutral': ((0,0,0),(0,0,0)), 'left_step': ((0,15,18),(0,0,0)),
         'right_step': ((0,0,0),(0,15,18)), 'both_up': ((0,14,15),(0,14,15)),
         'spread': ((14,4,0),(-14,4,0)), 'held_left': ((0,9,12),(0,0,0))}
for name, pose in poses.items():
    for side, delta in zip(('L','R'), pose):
        cmds.xform(side+'_ankleIk_CTL', ws=True, t=[a+b for a,b in zip(rest[side],delta)])
    stats = skirt.audit()
    contact = dress.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],
                                          'c_body_GEO',surface_samples=True,penetration_tolerance=.01)
    stats['contact'] = contact
    report['poses'][name] = stats
    print('SKIRT_POSE='+json.dumps({'name':name, 'stretch':stats['max_stretch_ratio'],
          'lift':stats['max_lift_cm_local'], 'inside':len(contact['penetrating_vertices']),
          'minimum':contact['minimum_signed_clearance_cm']}), flush=True)
for side in ('L','R'):
    cmds.xform(side+'_ankleIk_CTL', ws=True, t=rest[side])
cmds.select(info['settings'])
cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii')
report['passed'] = (max(report['neutral_error'].values()) <= 1e-4 and all(
    row['length_gate_passed'] and not row['contact']['penetrating_vertices']
    and not row['contact']['uncertain_vertices'] for row in report['poses'].values()))
report_path.write_text(json.dumps(report,indent=2),encoding='ascii')
print('SKIRT_CANDIDATE='+json.dumps({k:v for k,v in report.items() if k!='poses'}),flush=True)
maya.standalone.uninitialize()
