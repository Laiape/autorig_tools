"""Sequence independent quality gates before any performance acceptance."""
import json
from pathlib import Path
from maya_trial_client import dispatch

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
SCRIPT=ROOT/'scripts/edward_exact_dispatch.py'
port=json.loads((FOLDER/'owned_maya.json').read_text())['port']
accepted=[]
for candidate in ('original','jaw','share_math','static_points','zero_influences','combined','zero_static','full','safe_full','cache'):
    if candidate=='combined' and not all(name in accepted for name in ('jaw','static_points')):
        continue
    if candidate=='zero_static' and not all(name in accepted for name in ('zero_influences','static_points')):
        continue
    if candidate=='full' and not all(name in accepted for name in ('jaw','static_points','zero_influences')):
        continue
    if candidate=='safe_full' and not all(name in accepted for name in ('share_math','static_points','zero_influences')):
        continue
    receipt=FOLDER/(candidate+'.quality.receipt.json')
    if not receipt.exists():
        dispatch(SCRIPT,receipt,port,{'action':'exact_quality','candidate':candidate,'reload_module':True},timeout=1800)
    data=json.loads(receipt.read_text())
    if not data['success']:
        raise RuntimeError(data.get('traceback',data))
    print(json.dumps(data['result']),flush=True)
    if data['result']['accepted'] and candidate!='original':accepted.append(candidate)
    if candidate=='original' and not data['result']['accepted']:
        raise RuntimeError('The original did not reproduce its own geometry reference.')
(FOLDER/'accepted_quality_candidates.json').write_text(json.dumps(accepted,indent=2))
print('QUALITY_COMPLETE '+json.dumps(accepted),flush=True)
