"""Clean temporal/control benchmarks with separate native GPU/graph diagnostics."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import time

from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_validation as qa, pose_blendshapes as poses

STATES = {'A': ('off', False, False), 'B': ('parallel', False, False),
          'C': ('parallel', True, False), 'D': ('parallel', True, True)}


def _disable_evaluator(name):
    if name in (cmds.evaluator(query=True) or []):
        cmds.evaluator(name=name, enable=False)


def statistics_ms(samples):
    if not samples or any(not math.isfinite(v) or v < 0 for v in samples):
        raise ValueError('Timing samples must be nonempty, finite and nonnegative.')
    ordered = sorted(samples)
    mean = statistics.mean(samples)
    median = statistics.median(samples)
    return {'mean_ms': mean, 'median_ms': median,
            'p95_ms': ordered[max(0, math.ceil(.95 * len(ordered)) - 1)],
            'max_ms': max(ordered), 'cv_percent': statistics.pstdev(samples) / mean * 100 if mean else 0,
            'samples': len(samples), 'derived_fps': 1000 / median if median else None}


def _query(function):
    try:
        return {'status': 'available', 'value': function()}
    except (RuntimeError, ValueError) as exc:
        return {'status': 'unavailable', 'reason': str(exc)}


def diagnostics():
    """Call after animated warm-up, outside the timed loop."""
    scheduling = _query(lambda: json.loads(cmds.dbpeek(op='graph', argument='scheduling', all=True)))
    if scheduling['status'] == 'available':
        raw = scheduling.pop('value').get('scheduling', {})
        scheduling.update(counts={k: len(v) for k, v in raw.items() if isinstance(v, list)},
                          restricted={k: v for k, v in raw.items()
                                      if isinstance(v, list) and not k.startswith('Parallel')})
    return {'scheduling': scheduling,
            'enabled_evaluators': cmds.evaluator(query=True, enable=True) or [],
            'gpu_meshes': _query(lambda: cmds.deformerEvaluator(query=True, list=True, meshes=True)),
            'gpu_chains': _query(lambda: cmds.deformerEvaluator(query=True, dumpInfo=True)),
            'gpu_active_chains': _query(lambda: cmds.deformerEvaluator(query=True, deformerChain=True, active=True)),
            'evaluation_fallback': _query(lambda: cmds.evaluationManager(query=True, fallbackTriggered=True)),
            'cache_safe_mode': _query(lambda: cmds.cacheEvaluator(query=True, safeModeTriggered=True)),
            'cache_messages': _query(lambda: cmds.cacheEvaluator(query=True, safeModeMessages=True)),
            'cached_frames': _query(lambda: cmds.cacheEvaluator(query=True, cachedFrames=True)),
            'cache_resource': _query(lambda: cmds.cacheEvaluator(query=True, resourceUsage=True))}


def environment(root):
    scene = Path(cmds.file(query=True, sceneName=True))
    code_root = Path(__file__).resolve().parents[3]
    code_files = {p.relative_to(code_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((code_root / 'maya_tools/scripts').rglob('*.py'))}
    return {'root': cmds.ls(root, long=True)[0], 'scene': str(scene),
            'scene_sha256': hashlib.sha256(scene.read_bytes()).hexdigest() if scene.is_file() else None,
            'code_sha256': hashlib.sha256(json.dumps(code_files, sort_keys=True).encode('ascii')).hexdigest(),
            'code_files': code_files,
            'maya': cmds.about(version=True), 'api': cmds.about(apiVersion=True),
            'units': cmds.currentUnit(query=True, linear=True), 'time_unit': cmds.currentUnit(query=True, time=True),
            'platform': platform.platform(), 'logical_cpus': os.cpu_count(),
            'plugins': {n: cmds.pluginInfo(n, query=True, version=True)
                        for n in cmds.pluginInfo(query=True, listPlugins=True) or []},
            'gpu_device': _query(lambda: cmds.ogs(query=True, deviceInformation=True)),
            'viewports': {p: {'width': cmds.control(p, query=True, width=True),
                             'height': cmds.control(p, query=True, height=True),
                             'camera': cmds.modelEditor(p, query=True, camera=True),
                             'appearance': cmds.modelEditor(p, query=True, displayAppearance=True),
                             'textures': cmds.modelEditor(p, query=True, displayTextures=True)}
                          for p in cmds.getPanel(type='modelPanel')}}


@contextmanager
def evaluation_session():
    """Restore evaluator, playback, cache, undo and artist scene state on failure."""
    mode = cmds.evaluationManager(query=True, mode=True)[0]
    names = cmds.evaluator(query=True) or []
    enabled = {n: bool(cmds.evaluator(name=n, query=True, enable=True)) for n in names}
    ranges = {n: cmds.playbackOptions(query=True, **{n: True})
              for n in ('minTime', 'maxTime', 'animationStartTime', 'animationEndTime')}
    auto_key = cmds.autoKeyframe(query=True, state=True)
    cache_fill = cmds.cacheEvaluator(query=True, cacheFillMode=True)
    from maya_tools.scripts.tools import rig_performance
    bypass_routes = {route['destination']: cmds.connectionInfo(route['destination'], sourceFromDestination=True)
                     for r in rig_performance.export_detail_modes()
                     for route in r.get('compute_bypass', {}).get('routes', [])}
    modified = cmds.file(query=True, modified=True)
    try:
        with qa._session():
            cmds.autoKeyframe(state=False)
            yield
    finally:
        _disable_evaluator('deformer')
        _disable_evaluator('cache')
        cmds.evaluationManager(mode='off')
        cmds.currentTime(cmds.currentTime(query=True)); cmds.refresh(force=True)
        cmds.evaluationManager(mode=mode)
        cmds.refresh(force=True)
        for name, value in enabled.items():
            if bool(cmds.evaluator(name=name, query=True, enable=True)) != value:
                cmds.evaluator(name=name, enable=value)
        cmds.cacheEvaluator(cacheFillMode=cache_fill)
        cmds.evaluationManager(mode=mode)
        cmds.playbackOptions(**ranges)
        cmds.autoKeyframe(state=auto_key)
        for destination, source in bypass_routes.items():
            cmds.connectAttr(source, destination, force=True)
        cmds.file(modified=modified)


@contextmanager
def temporal_workload(resolved, frames):
    """Create owned time curves after original animation has been disconnected."""
    changing = [p for p in resolved[0]['values']
                if len({case['values'][p] for case in resolved}) > 1]
    if not changing:
        raise ValueError('The playback workload needs genuinely changing controls.')
    curves = []
    try:
        for plug in changing:
            kind = {'doubleAngle': 'animCurveTA', 'doubleLinear': 'animCurveTL'}.get(
                cmds.getAttr(plug, type=True), 'animCurveTU')
            curve = cmds.createNode(kind, name='rigBenchmarkTemporaryCurve')
            curves.append(curve)
            cmds.connectAttr('time1.outTime', curve + '.input', force=True)
            for index, case in enumerate(resolved):
                frame = frames[0] + (frames[1] - frames[0]) * index / float(len(resolved) - 1)
                cmds.setKeyframe(curve, time=frame, value=case['values'][plug])
            tangent = 'step' if cmds.getAttr(plug, type=True) == 'enum' else 'linear'
            cmds.keyTangent(curve, edit=True, outTangentType=tangent, inTangentType='linear')
            cmds.connectAttr(curve + '.output', plug)
        yield {'animated_channels': changing, 'curves': len(curves)}
    finally:
        if curves:
            # Avoid GPU repartition pulling live curve targets while temporary
            # time curves are disconnected/deleted. The outer session restores
            # the artist's evaluator state after original animation is restored.
            try:
                _disable_evaluator('deformer')
            finally:
                cmds.delete([n for n in curves if cmds.objExists(n)])


def _play_once(frames):
    samples = []
    for frame in range(frames[0], frames[1] + 1):
        start = time.perf_counter()
        cmds.currentTime(frame, edit=True)
        cmds.refresh(force=True)
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def run_state(root, output, state='C', cases=None, frames=(1, 120), repeats=3,
              warmup_frames=8, detail=None, allow_unsaved=False):
    """Run one state per call. No geometry reads or Profiler during timed samples."""
    if cmds.about(batch=True):
        raise ValueError('Interactive Viewport 2.0 is required for a playback benchmark.')
    if state not in STATES or repeats < 3 or frames[1] - frames[0] + 1 <= warmup_frames:
        raise ValueError('Choose A/B/C/D, at least three repeats and enough warm-up frames.')
    if cmds.file(query=True, modified=True) and not allow_unsaved:
        raise ValueError('Use a saved trial scene for a temporal benchmark.')
    if cmds.profiler(query=True, sampling=True):
        raise ValueError('Stop Profiler sampling before clean timing.')
    output = Path(output)
    if output.exists():
        raise ValueError('Choose a new benchmark report version.')
    root = cmds.ls(root, long=True)[0]
    resolved, missing, skipped = qa.resolve_cases(root, cases)
    if missing or len(resolved) < 2:
        raise ValueError('Complete changing pose cases are required: ' + ', '.join(missing))
    initial = {p: cmds.getAttr(p) for p in resolved[0]['values']}
    if detail is not None:
        initial[root + '.detailMode'] = cmds.getAttr(root + '.detailMode')
    report = {'format': 'autorig-performance', 'version': 1,
              'created_utc': datetime.now(timezone.utc).isoformat(), 'environment': environment(root),
              'state': state, 'detail': detail, 'frames': list(frames),
              'measurement': 'currentTime plus forced VP2 refresh wall time; includes submission, not isolated GPU execution',
              'quality_measured': False, 'skipped_channels': skipped,
              'pose_definition': [{'name': c['name'], 'channels': c.get('definition', c['values'])} for c in resolved],
              'profiler_during_timing': False, 'warmup_frames': warmup_frames}
    mode, gpu, cache = STATES[state]
    with evaluation_session(), poses._temporary_values(initial):
        cmds.evaluationManager(mode=mode)
        cmds.evaluator(name='cache', enable=False)
        cmds.evaluator(name='deformer', enable=False)
        if detail is not None:
            from maya_tools.scripts.tools import rig_performance
            rig_performance.set_detail_mode(root, detail)
            recipe = next(r for r in rig_performance.export_detail_modes() if r['root'] == root)
            display = recipe['low' if detail == 0 else 'high']
            visible = {n: om.MSelectionList().add(n).getDagPath(0).isVisible() for n in display}
            if not all(visible.values()):
                raise ValueError('The benchmark display mesh has a hidden ancestor; refusing invisible-detail timing.')
            report['verified_visible_display'] = visible
        cmds.playbackOptions(minTime=frames[0], maxTime=frames[1],
                             animationStartTime=frames[0], animationEndTime=frames[1])
        with temporal_workload(resolved, frames) as workload:
            report['workload'] = workload
            cmds.currentTime(frames[0], edit=True)
            beginning = {p: cmds.getAttr(p) for p in workload['animated_channels']}
            cmds.currentTime((frames[0] + frames[1]) // 2, edit=True)
            changed = [p for p, value in beginning.items()
                       if abs(cmds.getAttr(p) - value) > 1e-7]
            if not changed:
                raise ValueError('Temporal controls did not change; refusing a static-scene benchmark.')
            report['verified_temporal_change'] = changed
            cmds.currentTime(frames[0]); cmds.refresh(force=True)
            if gpu:
                cmds.deformerEvaluator(purge=True)
                cmds.evaluator(name='deformer', enable=True)
            report['gpu_initialization'] = 'CPU materialization before GPU partition; CPU cleanup of temporary animation'
            if cache:
                cmds.cacheEvaluator(cacheFillMode='syncAsync')
                cmds.evaluator(name='cache', enable=True)
            start = time.perf_counter()
            _play_once(frames)
            report['warmup_wall_seconds'] = time.perf_counter() - start
            if cache:
                report['cache_wait_completed'] = cmds.cacheEvaluator(waitForCache=10.)
            runs = [_play_once(frames)[warmup_frames:] for _ in range(repeats)]
            report['runs'] = [statistics_ms(s) for s in runs]
            report['timing'] = statistics_ms([v for s in runs for v in s])
            report['median_of_run_medians_ms'] = statistics.median(r['median_ms'] for r in report['runs'])
            report['diagnostics'] = diagnostics()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    return report


def capture_profile(root, output, cases=None, frames=(1, 48), detail=None, state='C'):
    """Independent diagnostic capture; its times are never merged with benchmarks."""
    if cmds.about(batch=True) or cmds.profiler(query=True, sampling=True):
        raise ValueError('Use interactive Maya without an existing Profiler recording.')
    output = Path(output)
    if output.exists():
        raise ValueError('Choose a new profile capture.')
    resolved, missing, _ = qa.resolve_cases(root, cases)
    if missing:
        raise ValueError('Missing profile channels: ' + ', '.join(missing))
    initial = {p: cmds.getAttr(p) for p in resolved[0]['values']}
    if detail is not None:
        initial[root + '.detailMode'] = cmds.getAttr(root + '.detailMode')
    with evaluation_session(), poses._temporary_values(initial), temporal_workload(resolved, frames):
        mode, gpu, cache = STATES[state]
        cmds.evaluationManager(mode=mode)
        cmds.evaluator(name='cache', enable=cache)
        cmds.evaluator(name='deformer', enable=False)
        cmds.currentTime(frames[0]); cmds.refresh(force=True)
        cmds.evaluator(name='deformer', enable=gpu)
        if detail is not None:
            from maya_tools.scripts.tools import rig_performance
            rig_performance.set_detail_mode(root, detail)
        _play_once(frames)
        cmds.profiler(sampling=True)
        try:
            _play_once(frames)
        finally:
            cmds.profiler(sampling=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmds.profiler(output=str(output))
    return str(output)
