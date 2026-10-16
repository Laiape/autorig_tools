"""Attribute native EvaluateNode inclusive CPU events without inventing wall costs."""
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'

def summarize(path,catalog):
    mapping={};categories=[];node_us=Counter();node_count=Counter();types=Counter()
    event_us=Counter();event_count=Counter();per_frame=defaultdict(Counter)
    gpu_us=Counter();gpu_count=Counter()
    with path.open(encoding='utf-8',errors='replace') as stream:
        for index,line in enumerate(stream):
            if index==2:categories=line.rstrip().split('\t')
            if line.startswith('@') and ' = ' in line:
                key,value=line.rstrip().split(' = ',1);mapping[key]=value
                continue
            p=line.rstrip().split('\t')
            if len(p)!=9 or not p[0].isdigit():continue
            name=mapping.get(p[1],p[1]);node=mapping.get(p[2],p[2])
            duration=int(p[4]);event_us[name]+=duration;event_count[name]+=1
            if name=='MPxGPUDeformerEvaluate':
                gpu_us[node]+=duration;gpu_count[node]+=1
            if name!='EvaluateNode':continue
            leaf=node.rsplit('|',1)[-1]
            node_us[leaf]+=duration;node_count[leaf]+=1
    modules=[];exclusive=set();claimed=set()
    total=sum(node_us.values())
    for name,m in catalog['modules'].items():
        names=set(m['exclusive_nodes']);exclusive.update(names);claimed.update(m['claimed_nodes'])
        duration=sum(node_us[n] for n in names)
        modules.append(dict(module=name,nodes=len(names),evaluate_events=sum(node_count[n] for n in names),
                            cpu_inclusive_us=duration,cpu_inclusive_ms_per_frame=duration/48000,
                            percent_of_attributed_node_cpu=duration/total*100 if total else None,
                            top_nodes=[dict(node=n,cpu_us=node_us[n],type=catalog['nodes'][n]['type'])
                                       for n in sorted(names,key=lambda n:node_us[n],reverse=True)[:8]]))
    shared=claimed-exclusive
    def bucket(names):
        return dict(nodes=len(names),cpu_inclusive_ms_per_frame=sum(node_us[n] for n in names)/48000,
                    events=sum(node_count[n] for n in names))
    result=dict(source=str(path),frames=48,measurement='EvaluateNode inclusive CPU duration / 48 frames. Parallel/node nesting overlaps; not wall ms, FPS, GPU duration or marginal ablation cost.',
                modules=modules,node_cpu=[dict(node=n,inclusive_us=v,events=node_count[n],
                       type=catalog['nodes'].get(n,{}).get('type','not_in_catalog')) for n,v in node_us.most_common()],
                event_cpu=[dict(name=n,inclusive_us=v,events=event_count[n]) for n,v in event_us.most_common()],
                shared=bucket(shared),outside_modules=bucket(set(node_us)-claimed),
                gpu_deformer_cpu_events=[dict(node=n,inclusive_us=v,events=gpu_count[n]) for n,v in gpu_us.most_common()],
                all_evaluate_node_cpu_ms_per_frame=total/48000)
    return result

if __name__=='__main__':
    c=json.loads((FOLDER/'catalog.json').read_text())
    for prefix in ('final_profile_wrinkles','final2_profile_wrinkles'):
        for wrinkles in (0,1):
            path=FOLDER/('%s%d.txt'%(prefix,wrinkles))
            if path.exists():
                result=summarize(path,c)
                out=path.with_suffix('.summary.json');out.write_text(json.dumps(result,indent=2),encoding='utf-8')
                print(json.dumps({'profile':path.name,'modules':len(result['modules']),'all_cpu_ms_per_frame':result['all_evaluate_node_cpu_ms_per_frame']},ensure_ascii=False))
