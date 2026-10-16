"""Publish a new exclusive asset SKC only after exact DQ import verification."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001/dq_20261016_v001'
data=json.loads((FOLDER/'canonical_export.json').read_text())
quality=json.loads((FOLDER/'roundtrip_portable.json').read_text())
applied=json.loads((FOLDER/'apply_dq.json').read_text())
assert quality['passed'] and quality['max_weight_error']==0
assert applied['skins_changed']==23 and applied['weights_and_blend_weights_unchanged']
package=json.loads(Path(data['staged_skc']).read_text())
new_names={r['skin'] for r in data['records'].values()}
entries=[e for k,v in package.items() if not k.startswith('__') for e in v]
selected=[e for e in entries if e['name'] in new_names]
assert len(selected)==23 and all(e['attributes']['skinningMethod']==1 for e in selected)
metadata=package['__scene_deformers__']
assert not any(n['type']=='proximityWrap' for n in metadata['nodes'])
assert all(e['weight_encoding']=='float64_exact_nonzero' for e in entries)
metadata['dq_bake_export']={'date':'2026-10-16','requested_method':'Dual Quaternion','garments':23,
    'source_artist_scene':json.loads((FOLDER/'current_artist_snapshot.json').read_text()),
    'comparison_scene':applied['scene'],'canonical_scene':data['native_scene'],
    'weights_preserved':True,'other_authored_skin_methods_preserved':True,
    'static_bind_rest_blendshapes':{w:r['rest_blendshape'] for w,r in data['records'].items()},
    'static_rest_reason':'Preserve the fitted PRX copies bind positions on the original model meshes; no pose SDK or per-frame Python.',
    'retired_deleted_prx_detail_routes':data['retired_prx_detail_routes'],
    'roundtrip':{k:v for k,v in quality.items() if k!='rows'},
    'quality_scope':'DQ snapshot versus its lossless SKC reimport, including renamed output shapes. Not an equivalence approval versus the original proximityWrap.'}
folder=ROOT/'autorig_tools/maya_tools/assets/Edward/skin_clusters'
versions=[]
for directory in (folder,ROOT/'maya_tools/assets/Edward/skin_clusters'):
    for path in directory.glob('Edward_v*.skc'):
        match=re.fullmatch(r'Edward_v(\d+)\.skc',path.name)
        if match:versions.append(int(match.group(1)))
version=max(versions,default=0)+1
encoded=json.dumps(package,separators=(',',':'),allow_nan=False)
temporary=folder/('.Edward_DQ_'+uuid.uuid4().hex+'.tmp')
with temporary.open('x',encoding='utf-8') as stream:stream.write(encoded)
while True:
    target=folder/('Edward_v%03d.skc'%version)
    try:
        os.link(temporary,target)
        temporary.unlink()
        break
    except FileExistsError:version+=1
sha=hashlib.sha256(target.read_bytes()).hexdigest()
scripts=[ROOT/'scripts'/name for name in ('edward_prx_apply_dq.py','edward_prx_dq_export.py','edward_prx_dq_host.py','publish_edward_prx_dq.py')]
for script in scripts:
    source=script.read_text(encoding='utf-8');source.encode('ascii');ast.parse(source,filename=str(script))
summary={'skc':str(target),'version':version,'bytes':target.stat().st_size,'sha256':sha,'new_DQ_skins':23,
         'native_skin_nodes':data['skin_count'],'serialized_polygon_skin_records':len(entries),'lossless':True,
         'wrinkles_present':data['wrinkles_present'],'roundtrip':{k:v for k,v in quality.items() if k!='rows'},
         'dq_comparison_scene':applied['scene'],'canonical_scene':data['native_scene'],
         'source_weights_preserved':True,'static_bind_rest_nodes':23,
         'raw_folder':str(FOLDER),'scripts_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts}}
(FOLDER/'published.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
with target.with_suffix('.dq_export.json').open('x',encoding='utf-8') as stream:json.dump(summary,stream,indent=2)
print(json.dumps(summary,indent=2))
