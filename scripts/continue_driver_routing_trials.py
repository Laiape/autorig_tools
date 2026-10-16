"""Continue serialized routing trials after the initial GPU comparison finishes."""
import json
from pathlib import Path
import subprocess
import sys
import time
from maya_trial_client import dispatch

repo=Path(__file__).resolve().parents[1]
folder=repo/'maya_tools/assets/Edward/experiments/driver_routing_20261015_v001'
script=repo/'scripts/edward_driver_routing_trial.py'
last=folder/'benchmark_r1_shared_wrinkles_w1_C.receipt.json'
deadline=time.monotonic()+1800
while not last.exists():
    if time.monotonic()>deadline:raise TimeoutError('Initial comparison has not finished')
    time.sleep(2)
if not json.loads(last.read_text())['success']:raise RuntimeError('Initial comparison failed')
for variant in ('body_driver','face_driver'):
    receipt=folder/(variant+'_prepare.receipt.json')
    if not receipt.exists():
        print('PREPARE '+variant,flush=True)
        dispatch(script,receipt,7002,dict(action='prepare_variant',variant=variant))
    p=json.loads(receipt.read_text())
    if not p['success']:raise RuntimeError(p['traceback'])
def run(*args):
    subprocess.run([sys.executable,str(repo/'scripts/run_driver_routing_trials.py'),*args],check=True)
run('quality','--variants','body_driver','face_driver')
run('benchmark','--variants','body_driver','face_driver','--states','C')
# A second GPU capture checks the large first-pass difference after the scene
# has been reopened and the experiment order changed. Interaction is not repeated.
run('benchmark','--variants','shared_wrinkles','shared','direct','--states','C','--label','r2')
run('benchmark','--variants','direct','shared','--states','A','B','D')
print('CONTINUATION_COMPLETE',flush=True)
