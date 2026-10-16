"""Archive bounded build-integration evidence after native reopen comparison."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'tmp/edward_build_exact_integration_v002'
summary=json.loads((FOLDER/'summary.json').read_text());assert summary['accepted']
first=json.loads((FOLDER/'optimized/result.json').read_text());second=json.loads((FOLDER/'reopened/result.json').read_text())
assert second['success'] and first['shapes']==second['shapes'] and first['topology']==second['topology'] and first['joint_names']==second['joint_names']
before=np.load(FOLDER/'optimized/quality.npz');after=np.load(FOLDER/'reopened/quality.npz')
errors={'p':0.,'n':0.,'j':0.}
for key in before.files:
    difference=before[key]-after[key]
    error=float(np.abs(difference).max()) if key.startswith('j') else float(np.linalg.norm(difference,axis=-1).max())
    errors[key[0]]=max(errors[key[0]],error)
assert max(errors.values())<=1e-4,errors
head=next(i for i,s in enumerate(first['shapes']) if s.endswith('|cabeza_high_Shape'))
neutralized_detail=max(float(np.linalg.norm(before['p_1_%d_%d'%(i,head)]-before['p_0_%d_%d'%(i,head)],axis=1).max()) for i in range(first['cases']*2))
probe_before=np.load(FOLDER/'baseline_active_probe_v004/quality.npz')
probe_after=np.load(FOLDER/'optimized_active_probe_v004/quality.npz')
probe_errors={'p':0.,'n':0.,'j':0.}
for key in probe_before.files:
    difference=probe_before[key]-probe_after[key]
    error=float(np.abs(difference).max()) if key.startswith('j') else float(np.linalg.norm(difference,axis=-1).max())
    probe_errors[key[0]]=max(probe_errors[key[0]],error)
assert max(probe_errors.values())<=1e-4,probe_errors
detail=max(float(np.linalg.norm(probe_after['p_1_%d_%d'%(i,head)]-probe_after['p_0_%d_%d'%(i,head)],axis=1).max()) for i in range(6))
assert detail>0.,'The test-only active wrinkle probe must displace actual vertices'
motion={s:max(float(np.linalg.norm(before['p_0_%d_%d'%(i,m)]-before['p_0_0_%d'%m],axis=1).max()) for i in range(first['cases'])) for m,s in enumerate(first['shapes'])}
assert motion[first['shapes'][head]]>1e-4
inputs=json.loads((FOLDER/'input_hashes.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in inputs.items())
cross=json.loads((ROOT/'tmp/exact_build_cross_character_v001/result.json').read_text());assert cross['success']
summary.update(native_reopen_max_errors=errors,native_reopen_accepted=True,nonzero_wrinkle_displacement=detail,
               neutralized_pose_detail_displacement=neutralized_detail,active_wrinkle_probe_errors=probe_errors,
               active_probe_samples=720,active_probe_scope='Test-only manual activation and nonzero local depths/values; settings are not saved into source or delivered rigs.',
               maximum_motion_per_mesh=motion,
               omitted_zero_bindings=sum(r['before']-r['after'] for r in summary['optimizations']['new_skin_bindings']),
               optimized_skin_count=first['skins'],cross_character_smoke=[{'asset':r['asset'],'success':r['success'],'joints':r['joints'],'skins':r['skins']} for r in cross['results']],
               construction_timing_scope='One sequential A/B pair, OS cache warm; not a statistical speedup or viewport FPS measurement.',
               unknown_source_metadata=first['unknown_source_nodes'],
               source_format_note='Preserved native Maya ASCII. Unsupported source UI metadata blocked binary conversion; no artist data deleted.')
destination=ROOT/'autorig_tools/maya_tools/docs/validation/exact_build_integration_20261015'
destination.mkdir(exist_ok=False)
(destination/'summary.json').write_text(json.dumps(summary,indent=2))
shutil.copy2(FOLDER/'input_hashes.json',destination/'input_hashes.json')
for mode in ('baseline','optimized'):
    shutil.copy2(FOLDER/mode/'buildtiming.json',destination/(mode+'.buildtiming.json'))
    shutil.copy2(FOLDER/mode/'result.json',destination/(mode+'.result.json'))
    with (FOLDER/mode/'maya.log').open('rb') as source,gzip.open(destination/(mode+'.maya.log.gz'),'wb') as target:shutil.copyfileobj(source,target)
for name,count in (('test_build_exact_bindings_final',6),('test_build_pipeline_exact_final',11),('test_skin_manager_build_exact_final',20),('test_exact_cleanup_build_final',8)):
    source=ROOT/'tmp'/(name+'.log')
    assert 'Ran %d tests'%count in source.read_text(errors='replace')
    with source.open('rb') as stream,gzip.open(destination/(name+'.log.gz'),'wb') as target:shutil.copyfileobj(stream,target)
shutil.copy2(ROOT/'tmp/exact_build_cross_character_v001/result.json',destination/'cross_character_smoke.json')
sources=['maya_tools/scripts/utils/create_rig.py','maya_tools/scripts/tools/skin_manager_api.py','maya_tools/scripts/tools/rig_exact_cleanup.py']
(destination/'code_hashes.json').write_text(json.dumps({p:hashlib.sha256((ROOT/'autorig_tools'/p).read_bytes()).hexdigest() for p in sources},indent=2))
print(json.dumps({'accepted':True,'fresh_build_errors':summary['max_errors'],'reopen_errors':errors,'wrinkle_displacement':detail,'omitted_bindings':summary['omitted_zero_bindings'],'cross_character_smoke':summary['cross_character_smoke'],'evidence':str(destination)},indent=2))
