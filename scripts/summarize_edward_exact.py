"""Assemble measured exact-cleanup results and every garment consumer."""
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import statistics
from summarize_edward_audit import summarize

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
OLD=FOLDER.parent/'full_audit_20261015_v001'
def read(name):return json.loads((FOLDER/name).read_text())
catalog=json.loads((OLD/'catalog.json').read_text())
profiles={}
for candidate in ('original','safe_full'):
    for enabled in (0,1):
        label='profile_%s_w%d'%(candidate,enabled)
        meta=read(label+'.json')
        assert meta['buffer_not_exhausted']
        local=deepcopy(catalog);names=set(meta['nodes'])
        local['nodes']=meta['nodes']
        for module in local['modules'].values():
            for k in ('exclusive_nodes','claimed_nodes'):
                module[k]=[n for n in module[k] if n in names]
        summary=summarize(FOLDER/(label+'.txt'),local)
        (FOLDER/(label+'.summary.json')).write_text(json.dumps(summary,indent=2))
        profiles[(candidate,enabled)]=summary

timings=[json.loads(p.read_text()) for p in sorted(FOLDER.glob('reopened_w*.performance.json'))]
cohorts=[]
for enabled in (False,True):
    refs=[r['timing']['median_ms'] for r in timings if r['wrinkles']==enabled and r['candidate']=='original']
    center=statistics.median(refs);band=max(max(refs)-min(refs),.05*center)
    for candidate in ('original','zero_influences','safe_full','math_static','cache'):
        rows=[r for r in timings if r['wrinkles']==enabled and r['candidate']==candidate]
        if not rows:continue
        flat=sorted(v for r in rows for run in r['raw_runs_ms'] for v in run)
        med=statistics.median(flat)
        cohorts.append({'candidate':candidate,'wrinkles':enabled,'median_ms':med,
                        'p95_ms':flat[min(len(flat)-1,int((len(flat)-1)*.95))],
                        'samples':len(flat),'block_medians':[r['timing']['median_ms'] for r in rows],
                        'pass_medians':[run['median_ms'] for r in rows for run in r['runs']],
                        'reference_center_ms':center,'reference_drift_ms':max(refs)-min(refs),
                        'noise_band_ms':band,'delta_ms':center-med,'percent_less_time':100*(center-med)/center,
                        'verdict':'diagnostic_only_cache_hung' if candidate=='cache' else
                                  'reference' if candidate=='original' else
                                  'gain_beyond_band' if center-med>band else
                                  'regression_beyond_band' if med-center>band else 'inconclusive'})

payload=read('payloads.json')['payloads'] if (FOLDER/'payloads.json').exists() else []
storage={r['node']:r['bytes'] for r in payload}
consumers=read('consumer_map.json');meshes=[]
for row in consumers:
    direct=[r['node'] for r in row['primary_chain']]
    upstream=[r['node'] for r in row['upstream_driver_deformers']]
    item={**row,'label':row['shape'].split('|')[-2],
          'group':row['shape'].split('|')[4],
          'clothing':('|cuerpo_geo|' in row['shape'] and '|cuerpo_base|' not in row['shape']) or '|botas_geo|' in row['shape'] or '|tijeras_geo|' in row['shape'],
          'mesh_bytes':storage.get(row['shape']),
          'direct_payloads':[{'node':n,'bytes':storage.get(n),'format':next((r['format'] for r in payload if r['node']==n),'not captured')} for n in direct]}
    for mode in (0,1):
        nodes={r['node']:r['inclusive_us']/48000 for r in profiles[('safe_full',mode)]['node_cpu']}
        item['direct_cpu_'+str(mode)]=sum(nodes.get(n,0.) for n in direct)
        item['driver_cpu_'+str(mode)]=sum(nodes.get(n,0.) for n in upstream)
    meshes.append(item)

modules=[]
old_modules={r['name']:r for r in json.loads((OLD/'report_data.json').read_text())['modules']}
for name in catalog['modules']:
    row={'name':name,'payload_bytes':old_modules[name]['bytes']}
    for candidate in ('original','safe_full'):
        for mode in (0,1):
            match=next(r for r in profiles[(candidate,mode)]['modules'] if r['module']==name)
            row[candidate+'_'+str(mode)]=match['cpu_inclusive_ms_per_frame']
    modules.append(row)

quality=[]
for name in ('original','jaw','share_math','static_points','zero_influences','zero_static','safe_full','cache','native_reopen_safe_full','skc_native_roundtrip'):
    p=FOLDER/(name+'.quality.json')
    if not p.exists():continue
    d=json.loads(p.read_text())
    quality.append({'candidate':name,'accepted':d['accepted'],
                    'max_position_error':max(r['max_error'] for r in d['rows']),
                    'max_normal_error':max(r['max_normal_error'] for r in d['rows']),
                    'max_joint_error':max(r['matrix_error'] for r in d['rows']),
                    'mesh_samples':sum(r['samples'] for r in d['rows'])})

saved=[{k:r[k] for k in ('candidate','file','bytes','sha256','nodes','head_source')} for r in read('saved_variants.json')]
safe=next(r for r in read('saved_variants.json') if r['candidate']=='safe_full')
after={r['skin']:r['after'] for r in safe['change']['zero_influences']['skins']}
node_times={mode:{r['node']:r['inclusive_us']/48000 for r in profiles[('safe_full',mode)]['node_cpu']} for mode in (0,1)}
old_payloads={r['label']:r['bytes'] for r in json.loads((OLD/'storage.json').read_text())['payloads']}
skins=[]
for r in catalog['skins']:
    skins.append({'name':r['name'],'before':r['influences'],'after':after.get(r['name'],r['influences']),
                  'geometry':r['geometry'],'method':r['skinning_method'],
                  'max_setting':r['max_influences_setting'],'maintain_max':r['maintain_max_influences'],
                  'native_original_bytes':old_payloads.get('skin_'+r['name']),
                  'exact_skc_bytes':next((p['bytes'] for p in payload if p['node']==r['name'] and p['kind']=='skin_sparse_json'),None),
                  'cpu_0':node_times[0].get(r['name'],0.),'cpu_1':node_times[1].get(r['name'],0.)})
blend_rows=[{'name':r['name'],'targets':r['targets'],'native_bytes':storage.get(r['name']),
             'cpu_0':node_times[0].get(r['name'],0.),'cpu_1':node_times[1].get(r['name'],0.)} for r in catalog['blendShapes']]
prx_rows=[{**r,'native_bytes':storage.get(r['node']),'cpu_0':node_times[0].get(r['node'],0.),'cpu_1':node_times[1].get(r['node'],0.)}
          for r in read('inventory.json')['prx']]
import numpy as np
reference=np.load(FOLDER/'exact_reference.npz')
meta=read('exact_reference.json');head=next(i for i,s in enumerate(meta['shapes']) if s.endswith('|cabeza_high_Shape'))
detail=max(float(np.linalg.norm(reference['p_1_%d_%d'%(i,head)]-reference['p_0_%d_%d'%(i,head)],axis=1).max()) for i in range(len(meta['frames'])))
data={'source':read('snapshot.json'),'timings':cohorts,'meshes':meshes,'modules':modules,
      'skins':skins,'blends':blend_rows,'prx':prx_rows,'measured_wrinkle_displacement':detail,
      'quality':quality,'saved':saved,'persistence':read('persistence_data_result.json'),
      'reproducibility':read('reproducibility.json'),'skc':read('skc_roundtrip.json'),
      'cache_failure':read('cache_reopened_hang.json'),
      'payload_meaning':'Strict isolated native bytes, not additive complete-scene savings or RAM.',
      'profile_meaning':'EvaluateNode inclusive CPU / 48 frames; shared upstream work repeats across consumers. Not wall time, intrinsic component cost or removable savings.',
      'coverage':{'meshes':len(meshes),'clothing_outputs':sum(r['clothing'] for r in meshes),'joints':852,'skins':58,'prx':23,'modules':18}}
(FOLDER/'exact_report_data.json').write_text(json.dumps(data,indent=2))
print(json.dumps({'coverage':data['coverage'],'timings':cohorts,'quality':quality},indent=2))
