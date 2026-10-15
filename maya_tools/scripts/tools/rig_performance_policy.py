"""Fail closed when performance-certified packages lack comparable evidence."""
import math


def validate(report, policy):
    if report.get('format') != 'autorig-performance' or report.get('version') != 1:
        raise ValueError('A native temporal performance report is required.')
    if report.get('state') != policy.get('state', 'C') or report.get('detail') != policy.get('detail', 0):
        raise ValueError('Performance state/detail do not match the publish policy.')
    if report.get('state') == 'D' and report.get('cache_quality_approved') is not True:
        raise ValueError('Cached performance needs matching cache quality approval.')
    if report.get('profiler_during_timing') is not False or len(report.get('runs', [])) < 3:
        raise ValueError('At least three clean timing runs are required.')
    if not report.get('verified_temporal_change') or not report.get('workload', {}).get('animated_channels'):
        raise ValueError('Static scenes cannot certify animated performance.')
    if not report.get('verified_visible_display') or not all(report['verified_visible_display'].values()):
        raise ValueError('Hidden output cannot certify visible rig performance.')
    environment = report.get('environment', {})
    if not environment.get('scene_sha256') or not environment.get('code_sha256'):
        raise ValueError('Scene and code hashes are required.')
    expected = policy.get('scene_sha256')
    if expected and expected != environment['scene_sha256']:
        raise ValueError('Performance evidence belongs to a different scene.')
    timing = report.get('timing', {})
    required = ('median_ms', 'p95_ms', 'max_ms', 'cv_percent')
    if any(not isinstance(timing.get(k), (int, float)) or not math.isfinite(timing[k]) or timing[k] < 0 for k in required):
        raise ValueError('Timing metrics must be finite and nonnegative.')
    fps = policy.get('shot_fps', 24)
    if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError('Choose a positive shot FPS.')
    budget = policy.get('p95_budget_ms', 1000 / fps)
    if not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0:
        raise ValueError('Choose a positive timing budget.')
    if timing['p95_ms'] > budget:
        raise ValueError('Animation p95 exceeds the declared timing budget.')
    if timing['cv_percent'] > policy.get('maximum_cv_percent', 15):
        raise ValueError('Timing variability requires a new clean comparison.')
    fallback = report.get('diagnostics', {}).get('evaluation_fallback', {})
    if fallback.get('status') != 'available' or fallback.get('value') not in (False, 0, '0'):
        raise ValueError('Evaluation fallback is active or unknown.')
    return {'success': True, 'budget_ms': budget, 'p95_ms': timing['p95_ms'],
            'state': report['state'], 'detail': report['detail'], 'scene_sha256': environment['scene_sha256']}
