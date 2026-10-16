"""Compare equal-output routing experiments and report measured pass dispersion."""
import json
from pathlib import Path
import numpy as np

folder=Path(__file__).resolve().parents[1]/'maya_tools/assets/Edward/experiments/driver_routing_20261015_v001'
summary={'quality':[],'benchmarks':[]}
if (folder/'direct_wrinkles1_quality.json').exists():
    with np.load(folder/'direct_wrinkles0_quality.npz') as a,np.load(folder/'direct_wrinkles1_quality.npz') as b:
        keys=[k for k in set(a.files)&set(b.files) if k.endswith('_1')]
        summary['verified_wrinkle_displacement_max']=max(float(np.linalg.norm(a[k]-b[k],axis=1).max()) for k in keys)
for enabled in (0,1):
    reference=folder/('direct_wrinkles%d_quality.npz'%enabled)
    if not reference.exists():continue
    with np.load(reference) as a:
        for variant in ('shared','shared_wrinkles','body_driver','face_driver'):
            path=folder/('%s_wrinkles%d_quality.npz'%(variant,enabled))
            if not path.with_suffix('.json').exists():continue
            meta=json.loads(path.with_suffix('.json').read_text())
            names=meta['meshes'];errors={n:0. for n in names};worst={}
            with np.load(path) as b:
                keys=sorted(set(a.files)&set(b.files))
                for key in keys:
                    error=float(np.linalg.norm(a[key]-b[key],axis=1).max())
                    name=names[int(key.rsplit('_',1)[1])]
                    if error>errors[name]:errors[name]=error;worst[name]=key
            row={'variant':variant,'wrinkles':enabled,'reference':'direct','max_error':max(errors.values()),'per_mesh_error':errors,'worst_samples':worst,'mesh_pose_samples':len(keys),'tolerance':1e-4,'accepted':max(errors.values())<=1e-4}
            summary['quality'].append(row)
for path in sorted(folder.glob('*.performance.json')):
    p=json.loads(path.read_text())
    if 'routing_variant' not in p:continue
    medians=[r['median_ms'] for r in p['runs']]
    summary['benchmarks'].append({'file':path.name,'variant':p['routing_variant'],'wrinkles':p['wrinkles_enabled'],'state':p['state'],'playback':p['timing'],'interaction':p['control_interaction']['timing'],'run_medians_ms':medians,'run_median_span_ms':max(medians)-min(medians),'cache_safe_mode':p['diagnostics']['cache_safe_mode'],'fallback':p['diagnostics']['evaluation_fallback']})
(folder/'comparison.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({'quality':[{k:v for k,v in q.items() if k not in ('per_mesh_error','worst_samples')} for q in summary['quality']],'benchmarks':[{'variant':b['variant'],'w':b['wrinkles'],'state':b['state'],'ms':round(b['playback']['median_ms'],2),'p95':round(b['playback']['p95_ms'],2),'interaction_ms':round(b['interaction']['median_ms'],2) if b['interaction'] else None} for b in summary['benchmarks']]},indent=2))
