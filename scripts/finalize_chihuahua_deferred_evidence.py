"""Record accepted native world-data comparisons with explicit groom ownership."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
trial=ROOT/'tmp/chihuahua_deferred_groom_20261016_release'
data=json.loads((trial/'snapshots.json').read_text())
def canonical(records):
    return {name.replace('|chihuahua|xgen','|xgen'):value for name,value in records.items()}
reference,candidate=data['visible'],data['restored']
report={
    'model_geometry_normals_uvs_materials_exact':canonical(reference['meshes'])==canonical(candidate['meshes']),
    'world_matrices_exact':canonical(reference['transforms'])==canonical(candidate['transforms']),
    'groom_names_and_direct_connections_exact':reference['groom']==candidate['groom'] and reference['groom_connections']==candidate['groom_connections'],
    'unloaded_primary_geometry_exact':data['preview']['meshes']=={n:v for n,v in data['hidden']['meshes'].items() if not n.startswith('|xgen|')},
    'mesh_count_loaded':len(candidate['meshes']), 'mesh_count_unloaded':len(data['preview']['meshes']),
    'groom_description_count':len(candidate['groom']),
    'ownership': 'The deferred reference restores xgen below the character root; compare its real world matrices/data with that declared path change. Show Groom uses FINAL space if the rig has been built.',
    'intentional_behavior': 'Groom is unloaded at open. Show Groom explicitly loads and displays it.',
    'scope': 'Static native source model and native save/reopen/reload; no new full-rig deformation or external texture-availability certification.',
    'failures_retained': ['Full groom interactive import trial cancelled after preference changed.',
                          'Owned diagnostic GUI stalled on file(new), no samples accepted.',
                          'Standalone reference teardown crashed after some quality captures; final interactive open/load/show/unload passed.']}
assert all(report[k] for k in ('model_geometry_normals_uvs_materials_exact','world_matrices_exact',
                              'groom_names_and_direct_connections_exact','unloaded_primary_geometry_exact'))
asset=ROOT/'autorig_tools/maya_tools/assets/chihuahua'
report['files']={}
for relative in ('models/chihuahua_v001.ma','models/chihuahua_v002.mb','groom/Chihuahua_groom_v001.mb'):
    path=asset/relative
    report['files'][relative]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
assert report['files']['models/chihuahua_v001.ma']['sha256']=='43ec2ab71d712410af609c5599f5ec61bc3439e9c55e0e5ccebec6656b1c6df5'
destination=ROOT/'autorig_tools/maya_tools/docs/validation/chihuahua_deferred_groom_20261016/quality.json'
destination.write_text(json.dumps(report,indent=2))
print('Accepted exact native model data and groom connections with declared reference ownership.')
