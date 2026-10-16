"""Reject static, noisy, stale and out-of-budget performance evidence."""
import copy
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.tools import rig_performance_policy as p

valid = {'format': 'autorig-performance', 'version': 1, 'state': 'C', 'detail': 0,
         'profiler_during_timing': False, 'runs': [{}, {}, {}],
         'verified_temporal_change': ['jaw.rx'], 'workload': {'animated_channels': ['jaw.rx']},
         'verified_visible_display': {'head': True},
         'environment': {'scene_sha256': 'scene', 'code_sha256': 'code'},
         'timing': {'median_ms': 20, 'p95_ms': 28, 'max_ms': 32, 'cv_percent': 4},
         'diagnostics': {'evaluation_fallback': {'status': 'available', 'value': False}}}
policy = {'scene_sha256': 'scene', 'shot_fps': 24}
assert p.validate(valid, policy)['success']
for key, value in [('verified_temporal_change', []), ('runs', [{}]), ('detail', 1),
                   ('profiler_during_timing', True), ('state', 'D'), ('verified_visible_display', {'head': False})]:
    report = copy.deepcopy(valid); report[key] = value
    try:
        p.validate(report, policy); raise AssertionError('Invalid evidence was accepted: ' + key)
    except ValueError:
        pass
for key, value in [('p95_ms', 50), ('cv_percent', 30), ('median_ms', float('nan'))]:
    report = copy.deepcopy(valid); report['timing'][key] = value
    try:
        p.validate(report, policy); raise AssertionError('Invalid metrics were accepted: ' + key)
    except ValueError:
        pass
try:
    p.validate(valid, dict(policy, scene_sha256='different')); raise AssertionError('Stale scene accepted')
except ValueError:
    pass
print('PASS performance publish policy: clean temporal evidence, matching hashes, budget, variation and fallback')
