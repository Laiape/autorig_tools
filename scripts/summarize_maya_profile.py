"""Summarize native profile events; inclusive totals are not a critical path."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def summarize(path):
    comments = {}
    groups = defaultdict(lambda: {'count': 0, 'inclusive_us': 0, 'maximum_us': 0})
    categories = []
    events = 0
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        for index, line in enumerate(stream):
            if index == 2:
                categories = line.rstrip().split('\t')
            if line.startswith('@') and ' = ' in line:
                key, value = line.rstrip().split(' = ', 1); comments[key] = value
            parts = line.rstrip().split('\t')
            if len(parts) != 9 or not parts[0].isdigit():
                continue
            name, node = comments.get(parts[1], parts[1]), comments.get(parts[2], parts[2])
            category = categories[int(parts[3])]
            duration = int(parts[4])
            row = groups[(name, node, category)]
            row['count'] += 1; row['inclusive_us'] += duration
            row['maximum_us'] = max(row['maximum_us'], duration)
            events += 1
    rows = [dict(name=k[0], node=k[1], category=k[2], **v) for k, v in groups.items()]
    return {'source': str(path), 'events': events,
            'measurement': 'Native inclusive event durations; nested/concurrent events overlap and cannot be added as frame time.',
            'largest_events': sorted(rows, key=lambda v: v['inclusive_us'], reverse=True)[:100],
            'wrinkle_events': [v for v in rows if 'bif' in v['category'].lower() or 'Wrinkles' in v['node']],
            'deform_events': [v for v in rows if 'deform' in v['name'].lower()]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('output')
    args = parser.parse_args()
    result = summarize(args.input)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'events': result['events'], 'largest_events': result['largest_events'][:12],
                      'wrinkle_events': result['wrinkle_events'][:20]}))
