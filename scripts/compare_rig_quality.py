"""Compare full evaluated mesh samples without merging quality and timing work."""
import argparse
import json
from pathlib import Path
import numpy as np


def compare(baseline, candidate, tolerance=1e-4):
    left = json.loads(Path(baseline).read_text(encoding='utf-8'))
    right = json.loads(Path(candidate).read_text(encoding='utf-8'))
    if left['definitions'] != right['definitions'] or left['missing'] or right['missing']:
        raise ValueError('Complete matching pose definitions are required.')
    rows = []
    for mode, baseline_rows in left['modes'].items():
        candidate_rows = right['modes'][mode]
        if len(baseline_rows) != len(candidate_rows):
            raise ValueError('Matching forward and reverse samples are required.')
        for a, b in zip(baseline_rows, candidate_rows):
            if a['name'] != b['name'] or a['meshes'].keys() != b['meshes'].keys():
                raise ValueError('Pose or mesh identity changed.')
            for mesh, first in a['meshes'].items():
                second = b['meshes'][mesh]
                if first['topology'] != second['topology'] or first['vertices'] != second['vertices']:
                    raise ValueError('Mesh topology changed: ' + mesh)
                maximum = float(np.max(np.linalg.norm(np.asarray(first['points']) - second['points'], axis=1)))
                if not np.allclose(first['world_matrix'], second['world_matrix'], atol=tolerance, rtol=0):
                    raise ValueError('Mesh world transform changed: ' + mesh)
                rows.append({'mode': mode, 'pose': a['name'], 'mesh': mesh, 'maximum_error': maximum})
    maximum = max(r['maximum_error'] for r in rows)
    first_rows = next(iter(left['modes'].values()))
    neutral = np.asarray(first_rows[0]['meshes']['head']['points'])
    movement = max(float(np.max(np.linalg.norm(np.asarray(row['meshes']['head']['points']) - neutral, axis=1)))
                   for row in first_rows)
    return {'success': maximum <= tolerance and movement > .01, 'maximum_vertex_error': maximum,
            'maximum_head_pose_change': movement, 'tolerance': tolerance, 'topology_match': True,
            'pose_count': len(left['definitions']), 'modes': list(left['modes']),
            'mesh_samples': len(rows), 'comparisons': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline'); parser.add_argument('candidate'); parser.add_argument('output')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Choose a new comparison report.')
    result = compare(args.baseline, args.candidate)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'comparisons'}))
    raise SystemExit(0 if result['success'] else 1)
