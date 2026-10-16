"""Create a scoped decision record from completed interleaved CPU trials."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(path):
    report=json.loads(path.read_text())
    if not report.get('complete'):raise ValueError('Incomplete trial: '+str(path))
    result={'source':str(path),'cohort':report['cohort'],'guide_samples_per_lid':report['guide_samples_per_lid'],
            'joint_count':len(report['output_joints']),'measurement':report['measurement'],
            'head_mesh_demand':report.get('head_mesh_demand',[]),'comparisons':[]}
    for mode in ('off','parallel'):
        blocks=sorted(set(row['block'] for row in report['rows'] if row['mode']==mode))
        def values(block):
            return [v for row in report['rows'] if row['mode']==mode and row['block']==block for v in row['raw_ms']]
        def stats(values):
            ordered=sorted(values)
            return {'median_ms':statistics.median(values),'p95_ms':ordered[max(0,int(.95*len(ordered)+.999999)-1)],
                    'max_ms':max(values),'samples':len(values)}
        for block in blocks:
            rows=[r for r in report['rows'] if r['mode']==mode and r['block']==block]
            variant=rows[0]['variant']
            if variant=='reference':continue
            a,b=statistics.median(values(block-1)),statistics.median(values(block+1))
            reference=(a+b)*.5
            candidate=stats(values(block))
            delta=reference-candidate['median_ms']
            noise=max(.05*reference,abs(a-b))
            quality=report['quality'][mode+'_'+variant]
            result['comparisons'].append({'mode':mode,'variant':variant,'candidate':candidate,
                'neighbor_reference':stats(values(block-1)+values(block+1)),
                'reference_before_ms':a,'reference_after_ms':b,'reference_for_delta_ms':reference,
                'delta_ms':delta,'reduction_percent':100*delta/reference,
                'reference_drift_percent':100*abs(a-b)/reference,'noise_band_ms':noise,
                'outside_noise':abs(delta)>noise,'equivalent':quality['equivalent_to_reference'],
                'quality':quality,'decision':('reject_quality' if not quality['equivalent_to_reference']
                    else ('faster' if delta>noise else 'slower' if -delta>noise else 'inconclusive_noise')),
                'pass_medians_ms':[r['statistics']['median_ms'] for r in rows],
                'install_median_ms':statistics.median(report['install_ms'][variant])})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('reports',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result={'date':'2026-10-16','scope':'CPU evaluation only; no viewport FPS/GPU/cache acceptance.',
            'trials':[summarize(path) for path in args.reports]}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='ascii')
    for trial in result['trials']:
        print(trial['cohort'],trial['joint_count'])
        for row in trial['comparisons']:
            print(row['mode'],row['variant'],round(row['candidate']['median_ms'],3),round(row['reduction_percent'],2),row['decision'])
