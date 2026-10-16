"""Recover completed mesh captures; never retry the unsafe native skin export."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
inventory=json.loads((FOLDER/'inventory.json').read_text())
rows=[]
for index,row in enumerate(inventory['meshes']):
    path=FOLDER/'payloads'/('mesh_%02d.mb'%index)
    assert path.is_file() and path.stat().st_size>1000
    rows.append({'kind':'baked_mesh','node':row['shape'],'bytes':path.stat().st_size,
                 'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'format':'native MB geometry'})
skc=json.loads((FOLDER/'Edward_exact_lossless_v002.skc').read_text())
seen=set()
for key,entries in skc.items():
    if key.startswith('__'):continue
    for entry in entries:
        if entry['name'] in seen:continue
        seen.add(entry['name'])
        item={k:v for k,v in entry.items() if k!='geometry'}
        rows.append({'kind':'skin_sparse_json','node':entry['name'],
                     'bytes':len(json.dumps(item,separators=(',',':')).encode()),
                     'file':str(FOLDER/'Edward_exact_lossless_v002.skc'),'format':'lossless SKC JSON entry without geometry'})
old=json.loads((FOLDER.parent/'full_audit_20261015_v001/storage.json').read_text())
for item in old['payloads']:
    # Original PRX/corrective payloads were preserved by the persistence gate.
    if item['label'].startswith('prx_') or item['label'].startswith('blend_'):
        prefix='prx_' if item['label'].startswith('prx_') else 'blend_'
        rows.append({'kind':'proximityWrap' if prefix=='prx_' else 'blendShape',
                     'node':item['label'][len(prefix):],'bytes':item['bytes'],'file':item['file'],
                     'format':'prior native MB payload, preserved data'})
result={'payloads':rows,'meaning':'All60 geometry captures completed before native selected-skin export crashed the owned trial. Skin rows use exact SKC sparse JSON bytes; these are a different format from native mesh/deformer bytes. PRX/corrective payloads reuse unchanged prior native captures. Not additive scene savings or RAM.'}
(FOLDER/'payloads.json').write_text(json.dumps(result,indent=2))
(FOLDER/'native_payload_export_failure.json').write_text(json.dumps({'pid':49180,'stage':'payload_deformer','node':'C_cheeks_high_local_SKC','artist_pid':35132,'artist_alive':True,'decision':'Do not retry this selected-skin native export; retain completed60 mesh captures and report SKC bytes separately.'},indent=2))
print(json.dumps({'meshes':60,'skin_entries':len(seen),'rows':len(rows)}))
