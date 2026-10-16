"""Offline ownership refinement: include native SDK curves, stop at global time.

The first inventory stopped at all animCurve nodes. That excluded real module
SDKs along with time animation. Structural ownership must include those curves.
"""
from collections import Counter, defaultdict, deque
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
path=FOLDER/'catalog.json';data=json.loads(path.read_text());nodes=data['nodes']
backup=FOLDER/'catalog_before_sdk_ownership.json'
if not backup.exists():backup.write_text(json.dumps(data,indent=2),encoding='utf-8')
incoming=defaultdict(set)
for source,destination,*_ in data['edges']:incoming[destination].add(source)
boundaries={'skinCluster','blendShape','proximityWrap','bifrostGraphShape','bifrostGeoToMaya',
            'shadingEngine','objectSet','network','time','sequenceManager'}
claims=defaultdict(set)
for name,module in data['modules'].items():
    owned=set(module['dag_nodes']);todo=deque(owned)
    while todo:
        for source in incoming[todo.popleft()]:
            if source in owned or source not in nodes:continue
            row=nodes[source]
            if 'path' in row or row['type'] in boundaries:continue
            owned.add(source);todo.append(source)
    module['claimed_nodes']=sorted(owned)
    for n in owned:claims[n].add(name)
for name,module in data['modules'].items():
    module['exclusive_nodes']=sorted(n for n in module['claimed_nodes'] if len(claims[n])==1)
    module['shared_nodes']=sorted(n for n in module['claimed_nodes'] if len(claims[n])>1)
    module['types']=dict(Counter(nodes[n]['type'] for n in module['exclusive_nodes']))
data['module_attribution_method']='Most-specific DAG roots plus upstream native utilities and SDK animCurves, stopping at foreign DAG, deformation, sets/networks and global time. Shared claims remain separate.'
path.write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps({n:{'nodes':len(m['exclusive_nodes']),'curves':sum(v for k,v in m['types'].items() if k.startswith('animCurve'))} for n,m in data['modules'].items()}))
