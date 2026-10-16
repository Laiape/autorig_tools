"""Summarize scoped all-PRX comparisons and preserve native input identities."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001'
OUT=ROOT/'autorig_tools/maya_tools/docs/validation/all_prx_bakes_20261016'
OUT.mkdir(parents=True,exist_ok=True)


def read(name):return json.loads((FOLDER/name).read_text())


def identity(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest.hexdigest()}


manifest=read('manifest.json');quality=read('quality_summary.json');rows=read('quality_rows.json')
timing=read('batch_DG_timing.json')
scripts=sorted((ROOT/'scripts').glob('edward_all_prx_*.py'))+[ROOT/'scripts/edward_belt_blendshape_trial.py',Path(__file__).resolve()]
for script in scripts:
    text=script.read_text(encoding='utf-8');text.encode('ascii');ast.parse(text,filename=str(script))
compact=[]
for wrap,item in manifest['items'].items():
    record={'wrap':wrap,'source':item['source'],'vertices':item['vertices'],
            'skin_influences':manifest['skin'][wrap]['influences'],'skin_max_nonzero':manifest['skin'][wrap]['actual_max'],
            'blendshape_targets':len(manifest['blendshape']['outputs'][wrap]['targets'])}
    for kind in ('BLENDSHAPE','SKIN'):
        selected=[r for r in rows if r['wrap']==wrap and r['variant']==kind]
        record[kind]={bank:max(r['max_position_cm'] for r in selected if r['bank']==bank) for bank in ('capture','held_out','global')}
        record[kind]['max_normal']=max(r['max_normal'] for r in selected)
        record[kind]['passed']=all(r['max_position_cm']<=1e-4 and r['max_normal']<=1e-4 for r in selected)
    compact.append(record)
summary={'date':'2026-10-16','scope':'Both comparison methods applied to every one of the 23 PRX garment outputs.',
         'production_approval':False,'source':identity(FOLDER/'Edward_artist_baseline.ma'),'snapshot':read('snapshot.json'),
         'runtime':manifest['runtime'],'outputs':len(compact),'vertices':sum(r['vertices'] for r in compact),
         'capture_poses':len(manifest['fit']),'held_out_poses':len(manifest['held_out']),
         'shared_blendshape':manifest['blendshape']['node'],'blendshape_geometry_indices':manifest['blendshape']['geometry_indices'],
         'shared_weights':len(manifest['blendshape']['target_samples']),'skin_clusters':len(manifest['skin']),
         'capture_seconds':manifest['capture_seconds'],'build_seconds':manifest['build_seconds'],
         'quality_gate':{k:v for k,v in quality.items() if k not in ('summary','invariants')},
         'per_output':compact,'timing_scope':timing['scope'],'timing_summary':timing['summary'],
         'scenes':{kind:dict(record,identity=identity(Path(record['path']))) for kind,record in manifest['scenes'].items()},
         'native_reopen':{kind:read('reopen_'+kind+'_summary.json') for kind in ('BLENDSHAPE','SKIN')},
         'artist_windows':{kind:read('artist_window_'+kind+'_ready.json') for kind in ('BLENDSHAPE','SKIN')},
         'previous_reviews':{kind:{k:v for k,v in read('previous_review_'+kind+'.json').items() if k!='free_control_values'} for kind in ('BLENDSHAPE','SKIN')},
         'scripts':[identity(p) for p in scripts],'code_syntax_ascii':True,'raw_folder':str(FOLDER),
         'limitations':['Finite FK pose targets and fitted linear skins do not guarantee arbitrary/combined deformation.',
                        'Original PRX remains available in both review scenes; no production build integration.',
                        'Timing is standalone DG latency for 23 requested outputs, not viewport or full-rig FPS.']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({'summary':str(OUT/'summary.json'),'outputs':len(compact),'shared_targets':summary['shared_weights'],
                  'skin_clusters':summary['skin_clusters'],'quality_passed':quality['passed'],
                  'opened':{kind:record['success'] for kind,record in summary['artist_windows'].items()}},indent=2))
