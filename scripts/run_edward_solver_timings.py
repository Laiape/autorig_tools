"""Run clean sequential ABBA viewport comparisons in the owned Maya only."""
import json
from pathlib import Path
import time
import sys
from maya_trial_client import dispatch

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001'
worker = ROOT / 'scripts/edward_solver_trial_worker.py'
tasks = []
blocks = (('A3', 'maya'),) if '--closing-reference' in sys.argv else (('A1', 'maya'), ('B1', 'custom'), ('B2', 'custom'), ('A2', 'maya'))
for block, variant in blocks:
    for scenario in ('FK', 'IK'):
        for detail in (0, 1):
            tasks.append({'action': 'benchmark', 'variant': variant, 'block': block,
                          'scenario': scenario, 'detail': detail, 'mode': 'B'})
for index, task in enumerate(tasks):
    name = 'receipt_timing_%s_%s_%s_detail%d.json' % (task['block'], task['variant'], task['scenario'], task['detail'])
    receipt = FOLDER / name
    if not receipt.exists():
        dispatch(worker, receipt, port=7392, arguments=task, timeout=150)
    response = json.loads(receipt.read_text())
    if not response['success']:
        print(json.dumps(response), flush=True)
        raise RuntimeError('Benchmark failed: ' + str(task))
    result = response['result']
    print(json.dumps({'completed': index + 1, 'total': len(tasks), 'task': task,
                      'median_ms': result['timing']['median_ms'],
                      'p95_ms': result['timing']['p95_ms']}), flush=True)
print('COMPLETE ABBA viewport timings', flush=True)
