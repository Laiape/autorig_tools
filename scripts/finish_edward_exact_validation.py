"""Finish bounded persistence gates and separate native diagnostic captures."""
import json
from pathlib import Path
from maya_trial_client import dispatch
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
port=json.loads((FOLDER/'owned_maya.json').read_text())['port']

def call(script,name,arguments):
    receipt=FOLDER/(name+'.receipt.json')
    if not receipt.exists():dispatch(ROOT/'scripts'/script,receipt,port,arguments,timeout=900)
    data=json.loads(receipt.read_text())
    print(json.dumps({'step':name,**data}),flush=True)
    if not data['success']:raise RuntimeError(data.get('traceback'))
    return data['result']

repeat=call('edward_exact_persistence.py','reproduce_frozen03',{'action':'reproduce','label':'repeat03'})
assert repeat['accepted'] and repeat['changes']=={'share_math':17,'static_points':5451,'zero_influences':474},repeat
skc=call('edward_exact_persistence.py','skc_roundtrip',{'action':'skc'})
if skc['accepted']:
    quality=call('edward_exact_dispatch.py','skc_native_quality',{'action':'exact_quality','reload_module':True,
                 'candidate':'original','source':skc['file'],'label':'skc_native_roundtrip'})
    print('SKC_QUALITY_ACCEPTED '+str(quality['accepted']),flush=True)
call('edward_exact_dispatch.py','persisted_profiles',{'action':'profiles','reload_module':True,'candidate':'safe_full'})
call('edward_exact_dispatch.py','all_output_payloads',{'action':'payloads','reload_module':True})
print('EXACT_VALIDATION_COMPLETE',flush=True)
