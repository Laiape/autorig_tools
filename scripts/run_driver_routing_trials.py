"""Serialize Edward driver routing checks in the selected interactive Maya."""
import argparse
import json
from pathlib import Path
from maya_trial_client import dispatch

p=argparse.ArgumentParser()
p.add_argument('phase',choices=('quality','benchmark','restore'))
p.add_argument('--port',type=int,default=7002)
p.add_argument('--variants',nargs='+',default=['original','direct','shared','shared_wrinkles'])
p.add_argument('--states',nargs='+',default=['A','B','C','D'])
p.add_argument('--label',default='r1')
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
folder=repo/'maya_tools/assets/Edward/experiments/driver_routing_20261015_v001'
script=repo/'scripts/edward_driver_routing_trial.py'
steps=[]
if a.phase=='restore':steps=[{'action':'restore'}]
else:
    for enabled in (False,True):
        for v in a.variants:
            for state in (a.states if a.phase=='benchmark' else [None]):
                steps.append(dict(action=a.phase,variant=v,wrinkles=enabled,state=state,label=a.label))
for i,step in enumerate(steps):
    ident='%s_%s_%s_w%d_%s'%(a.phase,a.label,step.get('variant','scene'),step.get('wrinkles',False),step.get('state','q'))
    receipt=folder/(ident+'.receipt.json')
    if receipt.exists():
        prior=json.loads(receipt.read_text())
        if prior['success']:continue
        raise RuntimeError('Existing failed receipt: '+str(receipt))
    (folder/'progress.json').write_text(json.dumps({'step':i+1,'total':len(steps),**step}))
    print('START '+ident,flush=True)
    dispatch(script,receipt,a.port,step)
    result=json.loads(receipt.read_text())
    if not result['success']:raise RuntimeError(result['traceback'])
    print(json.dumps(result['result']),flush=True)
(folder/'progress.json').write_text(json.dumps({'phase':a.phase,'complete':True,'steps':len(steps)}))
