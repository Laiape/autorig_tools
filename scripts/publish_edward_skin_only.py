"""Publish a new SKC after the owned skin-only persistence checks pass."""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/skin_only_delivery_20261016_v001'
data = json.loads((FOLDER / 'verified_export.json').read_text())
assert data['roundtrip']['passed'] and data['roundtrip']['max_weight_error'] == 0
source = Path(data['staged_skc'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == data['staged_sha256']
package = json.loads(source.read_text())
entries = [e for k, v in package.items() if not k.startswith('__') for e in v]
assert len(entries) == 71
assert all(e['weight_encoding'] == 'float64_exact_nonzero' for e in entries)
records = data['records']
assert len(records) == 23
for record in records.values():
    entry = next(e for e in package[record['source']] if e['name'] == record['skin'])
    expected = 0 if record['source'].rsplit('|', 1)[-1] in ('cinturones2', 'pCube26') else 1
    assert entry['attributes']['skinningMethod'] == expected == record['method']
meta = package['__scene_deformers__']
assert not any(n['type'] == 'proximityWrap' or '_BakedBindRest_BLS' in n['name'] or '_ALLPRX_' in n['name'] for n in meta['nodes'])
assert {n['name'] for n in meta['nodes'] if n['type'] == 'blendShape'} == set(data['preserved_original_blendshapes'])
meta['skin_only_delivery'] = {
    'date': '2026-10-16', 'source_artist_snapshot': json.loads((FOLDER / 'snapshot.json').read_text()),
    'garment_count': 23, 'classic_linear_meshes': ['cinturones2', 'pCube26'],
    'remaining_fitted_garments_method': 'Dual Quaternion',
    'removed_static_bind_blendshapes': data['removed_blendshapes'],
    'original_correctives_preserved': True, 'weights_preserved': True,
    'roundtrip': data['roundtrip'], 'neutral_changes_cm': data['neutral_changes_cm'],
    'quality_scope': 'Requested skin-only candidate versus its SKC reimport and native reopen. No new equivalence approval versus original proximityWrap; artist will rebuild and review.'}
folder = ROOT / 'autorig_tools/maya_tools/assets/Edward/skin_clusters'
versions = []
for directory in (folder, ROOT / 'maya_tools/assets/Edward/skin_clusters'):
    for path in directory.glob('Edward_v*.skc'):
        match = re.fullmatch(r'Edward_v(\d+)\.skc', path.name)
        if match:
            versions.append(int(match.group(1)))
version = max(versions, default=0) + 1
temporary = folder / ('.Edward_skin_only_' + uuid.uuid4().hex + '.tmp')
with temporary.open('x', encoding='utf-8') as stream:
    json.dump(package, stream, separators=(',', ':'), allow_nan=False)
while True:
    target = folder / ('Edward_v%03d.skc' % version)
    try:
        os.link(temporary, target)
        temporary.unlink()
        break
    except FileExistsError:
        version += 1
summary = {'skc': str(target), 'version': version, 'bytes': target.stat().st_size,
           'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
           'garment_skins': 23, 'DQ_garments': 21, 'classic_linear_meshes': ['cinturones2', 'pCube26'],
           'removed_static_bind_blendshapes': len(data['removed_blendshapes']),
           'original_blendshapes_preserved': data['preserved_original_blendshapes'],
           'native_skin_nodes': data['skin_count'], 'serialized_polygon_skins': len(entries),
           'lossless': True, 'wrinkles_present': data['wrinkles_present'],
           'roundtrip': data['roundtrip'], 'raw_folder': str(FOLDER),
           'max_neutral_change_cm': max(data['neutral_changes_cm'].values())}
with target.with_suffix('.skin_only_export.json').open('x', encoding='utf-8') as stream:
    json.dump(summary, stream, indent=2)
(FOLDER / 'published.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
