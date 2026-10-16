"""Sequence owned interactive Edward benchmark states without concurrent workloads."""
import argparse
import json
from pathlib import Path
from maya_trial_client import dispatch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--port', type=int, default=7102)
    parser.add_argument('--label', required=True)
    parser.add_argument('--variants', nargs='+', default=['dense', 'regional_encoded'])
    parser.add_argument('--states', nargs='+', default=list('ABCD'))
    parser.add_argument('--details', nargs='+', type=int, default=[0, 1])
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = repo / 'maya_tools/assets/Edward/validation' / args.label
    if output.exists():
        raise ValueError('Choose a new trial label.')
    output.mkdir(parents=True)
    script = repo / 'scripts/edward_performance_trial.py'
    for variant in args.variants:
        steps = [{'action': 'load', 'variant': variant}]
        steps += [{'action': 'benchmark', 'variant': variant + '_' + args.label, 'state': s, 'detail': d}
                  for d in args.details for s in args.states]
        for index, step in enumerate(steps):
            receipt = output / ('%s_%02d.json' % (variant, index))
            dispatch(script, receipt, args.port, dict(step, expected_pid=args.pid))
            result = json.loads(receipt.read_text(encoding='utf-8'))
            if not result['success']:
                raise RuntimeError(result['traceback'])
            print(json.dumps(dict(step, result=result['result'])), flush=True)
