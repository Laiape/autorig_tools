"""Serialize final measurements after the component batch; never compete for CPU."""
import json
from pathlib import Path
import subprocess
import sys
import time
from maya_trial_client import dispatch

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
previous=ROOT/'tmp/edward_final_components_receipt.json'
deadline=time.monotonic()+7200
while not previous.exists():
    if time.monotonic()>deadline:raise TimeoutError('Component batch did not finish')
    time.sleep(2)
if not json.loads(previous.read_text())['success']:raise RuntimeError(previous.read_text())

catalog=json.loads((FOLDER/'catalog.json').read_text())
layers=[s['name'] for s in catalog['skins'] if any('|cabeza_high|' in g['shape'] or '|cabeza_low|' in g['shape'] for g in s['geometry'])]
labels=['reference_start','all_skinning','all_facial_high_skinning','all_facial_low_skinning','all_PRX','all_correctives','eyelid_curve_blendShapes','reference_end']+['skin_'+s for s in layers]
steps=[('routing_repeat',{}),('profiles',{'prefix':'final2_profile_wrinkles'}),
       ('components',{'labels':labels,'prefix':'final2_component_'}),
       ('states',{}),('display',{}),('quality',{}),('cache_quality',{}),('weight_thresholds',{})]
for action,extra in steps:
    receipt=ROOT/('tmp/edward_final_v2_'+action+'_receipt.json')
    if not receipt.exists():
        print('BEGIN '+action,flush=True)
        dispatch(ROOT/'scripts/edward_final_audit.py',receipt,7002,dict(action=action,**extra),timeout=7200)
    result=json.loads(receipt.read_text())
    if not result['success']:raise RuntimeError(result['traceback'])
    print('COMPLETE '+action,flush=True)
subprocess.run([sys.executable,str(ROOT/'scripts/summarize_edward_audit.py')],check=True)
print('AUDIT_MEASUREMENTS_COMPLETE',flush=True)
