"""Save a fresh local asset version only after the measured native gates."""
import hashlib
import json
from pathlib import Path
import re
import shutil
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
def read(name):return json.loads((FOLDER/name).read_text())
assert read('persistence_data_result.json')['accepted']
assert read('native_reopen_safe_full.quality.json')['accepted']
assert read('skc_native_roundtrip.quality.json')['accepted']
assert read('skc_roundtrip.json')['accepted']
assert read('reproducibility.json')['accepted']
assert read('artist_final_readonly.json')['success']
rows=read('saved_variants.json');candidate=next(r for r in rows if r['candidate']=='safe_full')
source=Path(candidate['file'])
assert hashlib.sha256(source.read_bytes()).hexdigest()==candidate['sha256']
folder=ROOT/'autorig_tools/maya_tools/assets/Edward/scenes'
versions=[int(m.group(1)) for p in folder.glob('Edward_working_v*.mb') if (m:=re.fullmatch(r'Edward_working_v(\d+)\.mb',p.name))]
version=max(versions,default=0)+1
target=folder/('Edward_working_v%03d.mb'%version)
with source.open('rb') as original,target.open('xb') as output:shutil.copyfileobj(original,output)
assert hashlib.sha256(target.read_bytes()).hexdigest()==candidate['sha256']
manifest={'file':str(target),'source':str(source),'sha256':candidate['sha256'],'bytes':target.stat().st_size,
          'source_snapshot':read('snapshot.json')['sha256'],'coverage':read('exact_report_data.json')['coverage'],
          'quality':'Original final geometry preserved; full CPU native reopen and weight roundtrip pose checks passed.',
          'settings':'Parallel CPU; cache/GPU override OFF through AutoRig Tools profile marker; authored wrinkles ON.',
          'changes':{'shared_identical_native_math':17,'static_point_curves_baked':5451,'exact_zero_influences_removed':474},
          'not_done':'No live artist replacement; no automatic live cleanup; no full CREATE RIG or deformer rebuild certification; no global GPU/cache approval.',
          'evidence_folder':str(FOLDER)}
target.with_suffix('.optimization.json').write_text(json.dumps(manifest,indent=2))
(FOLDER/'delivery.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
