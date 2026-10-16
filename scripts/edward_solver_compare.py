"""Compare saved solver quality captures without contaminating timing."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001'
meta = {v: json.loads((FOLDER / (v + '_quality.json')).read_text()) for v in ('maya', 'custom')}
arrays = {v: np.load(FOLDER / (v + '_quality.npz')) for v in meta}
meshes = {v: {r['shape']: (key, r) for key, r in m['meshes'].items()} for v, m in meta.items()}
common = sorted(set(meshes['maya']) & set(meshes['custom']))
assert common
rows = []; joints = []; stability = {}
for case in meta['maya']['cases']:
    cid = case['id']
    for mesh in common:
        ia, ra = meshes['maya'][mesh]; ib, rb = meshes['custom'][mesh]
        assert ra['topology_sha256'] == rb['topology_sha256'], mesh
        a = arrays['maya'][cid + '_p_' + ia]; b = arrays['custom'][cid + '_p_' + ib]
        errors = np.linalg.norm(b - a, axis=1)
        normals = np.linalg.norm(arrays['custom'][cid + '_n_' + ib] - arrays['maya'][cid + '_n_' + ia], axis=1)
        rows.append({'case': case['name'], 'direction': case['direction'], 'mesh': mesh,
                     'max_cm': float(errors.max()), 'rms_cm': float(np.sqrt(np.mean(errors ** 2))),
                     'vertices_over_0_1_cm': int(np.count_nonzero(errors > .1)),
                     'max_normal_error': float(normals.max())})
    a = arrays['maya'][cid + '_j']; b = arrays['custom'][cid + '_j']
    for name in sorted(set(meta['maya']['joints']) & set(meta['custom']['joints'])):
        am = a[meta['maya']['joints'].index(name)].reshape(4, 4)
        bm = b[meta['custom']['joints'].index(name)].reshape(4, 4)
        ar = np.linalg.svd(am[:3, :3]); br = np.linalg.svd(bm[:3, :3])
        r = (ar[0] @ ar[2]).T @ (br[0] @ br[2])
        angle = float(np.degrees(np.arccos(np.clip((np.trace(r) - 1) / 2, -1, 1))))
        joints.append({'case': case['name'], 'direction': case['direction'], 'joint': name,
                       'position_cm': float(np.linalg.norm(am[3, :3] - bm[3, :3])), 'orientation_degrees': angle})
for variant in meta:
    worst = 0.
    for case in meta[variant]['cases']:
        if case['direction'] != 'forward':
            continue
        for index in meta[variant]['meshes']:
            a = arrays[variant]['forward_' + case['name'] + '_p_' + index]
            b = arrays[variant]['reverse_' + case['name'] + '_p_' + index]
            worst = max(worst, float(np.linalg.norm(a - b, axis=1).max()))
    stability[variant] = worst
per_case = []
for case in meta['maya']['cases']:
    if case['direction'] != 'forward':
        continue
    selected = [r for r in rows if r['case'] == case['name'] and r['direction'] == 'forward']
    worst = max(selected, key=lambda r: r['max_cm'])
    per_case.append({'case': case['name'], 'max_cm': worst['max_cm'], 'mesh': worst['mesh'],
                     'meshes_over_tolerance': sum(r['max_cm'] > 1e-4 for r in selected),
                     'max_normal_error': max(r['max_normal_error'] for r in selected)})
builds = {v: json.loads((FOLDER / (v + '_build.json')).read_text()) for v in meta}
schema = {}
for name in builds['maya']['controls']:
    a = builds['maya']['controls'][name]; b = builds['custom']['controls'][name]
    added = sorted(set(b) - set(a)); removed = sorted(set(a) - set(b))
    changed = {k: [a[k]['value'], b[k]['value']] for k in set(a) & set(b) if a[k]['value'] != b[k]['value']}
    if added or removed or changed:
        schema[name] = {'added': added, 'removed': removed, 'changed_defaults': changed}
summary = {'common_meshes': len(common), 'pose_count': len(per_case), 'comparisons': len(rows),
           'missing_meshes': {v: sorted(set(meshes[v]) - set(common)) for v in meta},
           'missing_channels': {v: meta[v]['missing'] for v in meta},
           'max_position_cm': max(r['max_cm'] for r in rows), 'per_case': per_case,
           'worst_meshes': sorted(rows, key=lambda r: r['max_cm'], reverse=True)[:15],
           'worst_joint_positions': sorted(joints, key=lambda r: r['position_cm'], reverse=True)[:15],
           'worst_joint_rotations': sorted(joints, key=lambda r: r['orientation_degrees'], reverse=True)[:15],
           'forward_reverse_max_cm': stability, 'control_schema_changes': schema,
           'equivalent_at_1e_4_cm': max(r['max_cm'] for r in rows) <= 1e-4}
(FOLDER / 'quality_rows.json').write_text(json.dumps(rows, indent=2))
(FOLDER / 'joint_rows.json').write_text(json.dumps(joints, indent=2))
(FOLDER / 'quality_summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k not in ('worst_meshes', 'worst_joint_positions', 'worst_joint_rotations')}, indent=2))
