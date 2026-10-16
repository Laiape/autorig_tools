"""Run final quality, diagnostic and versioned working-asset checks in order."""
import argparse
import json
from pathlib import Path
from maya_trial_client import dispatch

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--actions', nargs='+', default=['profile_animation', 'profile_review', 'interaction',
                                                       'cache_quality', 'collar_proxy', 'freeze_working'])
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = repo / 'maya_tools/assets/Edward/validation' / args.label
    if output.exists():
        raise ValueError('Choose a new final-check label.')
    output.mkdir(parents=True)
    for index, action in enumerate(args.actions):
        step = {'action': action, 'variant': args.label, 'expected_pid': args.pid}
        if action.startswith('profile_'):
            step.update(action='profile', detail=0 if action == 'profile_animation' else 1)
        receipt = output / ('%02d_%s.json' % (index, action))
        dispatch(repo / 'scripts/edward_performance_trial.py', receipt, arguments=step)
        data = json.loads(receipt.read_text(encoding='utf-8'))
        if not data['success'] or (isinstance(data['result'], dict) and data['result'].get('success') is False):
            raise RuntimeError(json.dumps(data))
        print(action + ': ' + json.dumps(data['result'] if action != 'interaction' else data['result']['variants']), flush=True)
