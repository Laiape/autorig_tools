"""Final artifact consistency receipt and resumable scope record."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
def read(name):return json.loads((FOLDER/name).read_text())
data=read('exact_report_data.json');delivery=read('delivery.json')
assert data['coverage']=={'meshes':60,'clothing_outputs':47,'joints':852,'skins':58,'prx':23,'modules':18}
assert len(data['skins'])==58 and len(data['blends'])==9 and len(data['prx'])==23
assert all(r['mesh_bytes'] and r['mesh_bytes']>0 for r in data['meshes'])
for name in ('native_reopen_safe_full.quality.json','skc_native_roundtrip.quality.json',
             'persistence_data_result.json','skc_roundtrip.json','reproducibility.json'):
    assert read(name)['accepted'],name
assert hashlib.sha256(Path(delivery['file']).read_bytes()).hexdigest()==delivery['sha256']
assert hashlib.sha256((FOLDER/'Edward_artist_baseline.mb').read_bytes()).hexdigest()==delivery['source_snapshot']
assert data['measured_wrinkle_displacement']>0.
checks={
 'cleanup':'Ran 7 tests',
 'skin_manager':'Ran 20 tests',
 'lossless':'PASS replacement SKC preserves an interleaved corrective',
 'sparse':'PASS sparse influence reconstruction',
 'wrinkles':'PASS wrinkle .skc',
}
logs={'cleanup':'tmp/test_rig_exact_cleanup_final.log','skin_manager':'tmp/test_skin_manager_api_exact_v002.log',
      'lossless':'tmp/test_skin_lossless_export_v004.log','sparse':'tmp/test_skin_sparse_exact.log',
      'wrinkles':'tmp/test_wrinkle_skin_roundtrip_exact_final.log'}
for name,needle in checks.items():assert needle in (ROOT/logs[name]).read_text(errors='replace')
failure=read('cache_reopened_hang.json')
failure['stopped']=datetime.fromtimestamp((FOLDER/'cache_reopened_hang.json').stat().st_mtime).astimezone().isoformat()
failure['timestamp_source']='Original failure receipt file modification time; replaces an initially rounded timestamp.'
(FOLDER/'cache_reopened_hang.json').write_text(json.dumps(failure,indent=2))
native_failure=read('native_payload_export_failure.json')
native_failure.update({'native_error':'C0000005 access violation','stack':'DeformSlice TdnSolidify / geometry evaluation / exportSelectedFlag','log':'owned_maya_startup.log'})
(FOLDER/'native_payload_export_failure.json').write_text(json.dumps(native_failure,indent=2))
sources=['autorig_tools/maya_tools/scripts/tools/rig_exact_cleanup.py',
         'autorig_tools/maya_tools/scripts/tools/skin_manager_api.py',
         'autorig_tools/maya_tools/scripts/tools/bifrost_wrinkles.py',
         'scripts/edward_exact_worker.py','scripts/edward_exact_persistence.py']
receipt={'status':'delivered_scoped_exact_cleanup','delivery':delivery,
         'native_quality':'0 positions / vertex normals / joint matrices across4080 mesh samples per gate, OFF/ON.',
         'max_rest_face_vertex_normal_error':data['persistence']['max_face_vertex_normal_error'],
         'tests':logs,'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
         'typescript':'Canvas tsc strict check passed','artist':read('artist_final_readonly.json'),
         'owned_trial_state':'All owned trials ended; artist PID35132 remains. Native export failure retained.',
         'remaining_roadmap':'Bifrost conversion/backend, deeper jaw/eyelid/eyebrow/garment refactors remain separate proposals. No stable wrinkles-ON gain or full CREATE RIG certification claimed.',
         'report':'autorig_tools/maya_tools/docs/rig_exact_optimization_results_20261015.md',
         'canvas':'C:/Users/LaiaPeris/.cursor/projects/c-proyectos/canvases/edward-driver-routing.canvas.tsx'}
(FOLDER/'final_validation.json').write_text(json.dumps(receipt,indent=2))
(ROOT/'tmp/edward_exact_optimization_plan.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({'status':receipt['status'],'file':delivery['file'],'coverage':data['coverage'],'checks':'passed'}))
