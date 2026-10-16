"""Versioned Edward trials in an explicitly owned interactive Maya process."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from maya import cmds, mel
from importlib import reload
from maya_tools.scripts.tools import bifrost_wrinkles as bw, rig_performance as rp, rig_validation as qa
reload(bw); reload(rp)
repo = Path(__file__).resolve().parents[1]
folder = repo / 'maya_tools/assets/Edward/experiments' / TRIAL_ARGUMENTS.get('trial', 'rig_performance_20261014_v001')
folder.mkdir(parents=True, exist_ok=True)
if os.getpid() != TRIAL_ARGUMENTS['expected_pid'] or cmds.about(batch=True):
    raise RuntimeError('Use the explicitly owned interactive trial instance.')
action = TRIAL_ARGUMENTS['action']
progress = folder / 'progress.json'
progress.write_text(json.dumps({'action': action, 'status': 'running', 'utc': datetime.now(timezone.utc).isoformat()}))


def cases():
    definitions = [('neutral', {})]
    for name, channels in qa.COMBINATION_POSES[1:]:
        _, missing, _ = qa.resolve_cases('Edward', [('neutral', {}), (name, channels)])
        if not missing:
            definitions.append((name, channels))
    _, missing, _ = qa.resolve_cases('Edward', definitions)
    if missing or len(definitions) < 5 or not any('jaw' in n for n, _ in definitions):
        raise ValueError('The trial needs complete body and face controls.')
    return definitions


def displayed_head():
    record = next(r for r in bw.export_setups() if r['prefix'] == 'EdwardWrinkles')
    return record['source'] if record.get('in_place') else record['prefix'] + '_Face'


def capture_quality():
    definitions = cases()
    resolved, missing, skipped = qa.resolve_cases('Edward', definitions)
    meshes = {'head': displayed_head(), 'low': 'cabeza_low'}
    for name in ('cuerpo_base', 'collar2', 'collar3'):
        if cmds.objExists(name):
            meshes[name] = name
    initial = {p: cmds.getAttr(p) for p in resolved[0]['values']}
    result = {'missing': missing, 'skipped': skipped, 'definitions': definitions, 'modes': {}}
    with qa._session(), __import__('maya_tools.scripts.tools.pose_blendshapes', fromlist=['_temporary_values'])._temporary_values(initial):
        for mode in ('off', 'serial', 'parallel'):
            cmds.evaluationManager(mode=mode)
            rows = []
            for case in resolved + list(reversed(resolved)):
                for plug, value in case['values'].items():
                    cmds.setAttr(plug, value)
                rows.append({'name': case['name'], 'meshes': {k: qa.mesh_data(n) for k, n in meshes.items()}})
            result['modes'][mode] = rows
    return result


if action == 'setup':
    source = repo / 'maya_tools/assets/Edward/scenes/Edward_working_v001.mb'
    cmds.file(str(source), open=True, force=True, prompt=False, executeScriptNodes=False)
    originals = bw.export_setups()
    (folder / 'original_wrinkle_setup.json').write_text(json.dumps(originals, indent=2))
    details = rp.export_detail_modes()
    source_parent = cmds.listRelatives('cabeza_high', parent=True, fullPath=True)[0]
    cmds.parent('EdwardWrinkles_Face', source_parent, relative=True)
    face_path = cmds.ls('EdwardWrinkles_Face', long=True)[0]
    for data in details:
        if data['root'].rsplit('|', 1)[-1] != 'Edward':
            continue
        for index, node in enumerate(data['high']):
            if node.rsplit('|', 1)[-1] in ('cabeza_high', 'EdwardWrinkles_Face'):
                data['high'][index] = face_path
                data['original_values'].pop(node + '.visibility', None)
                data['original_values'][data['high'][index] + '.visibility'] = 1
        for n in ('cabeza_high',):
            incoming = cmds.connectionInfo(n + '.visibility', sourceFromDestination=True)
            if incoming:
                cmds.disconnectAttr(incoming, n + '.visibility')
            cmds.setAttr(n + '.visibility', 0)
    rp.restore_detail_modes(details)
    rp.set_detail_mode('Edward', 1)
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    panel = 'modelPanel4'
    cmds.modelEditor(panel, edit=True, displayAppearance='smoothShaded', displayTextures=False,
                     shadows=False, selectionHiliteDisplay=False, rendererName='vp2Renderer')
    cmds.select(displayed_head(), replace=True)
    cmds.viewFit('persp', fitFactor=.8)
    cmds.select(clear=True)
    cmds.file(rename=str(folder / ('Edward_' + TRIAL_ARGUMENTS.get('variant', 'dense') + '_trial.mb')))
    cmds.file(save=True, type='mayaBinary', force=True)
    result = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'trial_scene': cmds.file(query=True, sceneName=True), 'cases': cases(),
              'details': rp.export_detail_modes(), 'settings': originals[0]['settings'],
              'visible_head': cmds.ls(displayed_head(), visible=True, long=True)}
elif action == 'load':
    scene = folder / ('Edward_' + TRIAL_ARGUMENTS['variant'] + '_trial.mb')
    cmds.evaluator(name='deformer', enable=False)
    cmds.file(str(scene), open=True, force=True, prompt=False, executeScriptNodes=False)
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4', edit=True, displayAppearance='smoothShaded', displayTextures=False,
                     shadows=False, selectionHiliteDisplay=False, rendererName='vp2Renderer')
    result = {'scene': str(scene), 'smoothing': {n: cmds.getAttr(bw._mesh_fn(n)[0] + '.displaySmoothMesh')
              for n in ('cabeza_high', 'cabeza_low', displayed_head())}}
elif action == 'inspect':
    from maya_tools.scripts.tools import rig_benchmark as rb
    result = {'details': rp.export_detail_modes(), 'smoothing': {n: {
        'displaySmoothMesh': cmds.getAttr(bw._mesh_fn(n)[0] + '.displaySmoothMesh'),
        'smoothLevel': cmds.getAttr(bw._mesh_fn(n)[0] + '.smoothLevel')}
        for n in ('cabeza_high', 'cabeza_low', displayed_head())}, 'diagnostics': rb.diagnostics(),
        'collar_inputs': {n: cmds.listConnections(n + '.drivers', connections=True, plugs=True) for n in ('collar2_PRX', 'collar3_PRX')}}
elif action == 'collar_proxy':
    import numpy as np
    baseline = capture_quality()
    low_shape = bw._mesh_fn('cabeza_low')[0]
    low_rest = next(s for s in cmds.listRelatives('cabeza_low', shapes=True, fullPath=True)
                    if cmds.getAttr(s + '.intermediateObject'))
    routes = {}
    try:
        for node in ('collar2_PRX', 'collar3_PRX'):
            for attr, replacement in (('driverGeometry', low_shape + '.worldMesh[0]'),
                                      ('driverBindGeometry', low_rest + '.outMesh')):
                destination = node + '.drivers[1].' + attr
                routes[destination] = cmds.connectionInfo(destination, sourceFromDestination=True)
                cmds.connectAttr(replacement, destination, force=True)
        candidate = capture_quality()
        result = {'maximum_error': {}, 'source_vertices': cmds.polyEvaluate('cabeza_low', vertex=True)}
        for mode in baseline['modes']:
            for a, b in zip(baseline['modes'][mode], candidate['modes'][mode]):
                for mesh in a['meshes']:
                    error = float(np.max(np.linalg.norm(np.asarray(a['meshes'][mesh]['points']) - b['meshes'][mesh]['points'], axis=1)))
                    result['maximum_error'][mesh] = max(result['maximum_error'].get(mesh, 0.), error)
        result['accepted'] = max(result['maximum_error'].values()) <= 1e-4
    finally:
        for destination, source in routes.items():
            cmds.connectAttr(source, destination, force=True)
    result['rolled_back'] = True
    (folder / 'collar_proxy_comparison.json').write_text(json.dumps(result, indent=2))
elif action == 'quality':
    data = capture_quality()
    path = folder / (TRIAL_ARGUMENTS['variant'] + '_quality.json')
    path.write_text(json.dumps(data, separators=(',', ':')))
    result = {'quality_file': str(path), 'cases': len(data['definitions']), 'modes': list(data['modes'])}
elif action == 'benchmark':
    from maya_tools.scripts.tools import rig_benchmark
    reload(rig_benchmark)
    state = TRIAL_ARGUMENTS['state']
    detail = TRIAL_ARGUMENTS.get('detail', 1)
    path = folder / ('%s_%s_detail%d.performance.json' % (TRIAL_ARGUMENTS['variant'], state, detail))
    report = rig_benchmark.run_state('Edward', path, state=state, cases=cases(),
                                     frames=(1, 48), detail=detail, allow_unsaved=True)
    result = {'report': str(path), 'timing': report['timing'], 'cache': report['diagnostics']['cache_safe_mode']}
elif action == 'regional':
    candidate = bw.migrate_regional('EdwardWrinkles_Settings', in_place=True)
    rp.install_compute_bypass('Edward')
    rp.set_detail_mode('Edward', 1)
    cmds.file(rename=str(folder / ('Edward_' + TRIAL_ARGUMENTS.get('variant', 'regional') + '_trial.mb')))
    cmds.file(save=True, type='mayaBinary', force=True)
    result = {'scene': cmds.file(query=True, sceneName=True), 'output': candidate['output'],
              'support': {k: candidate['regional_support'][k] for k in
                          ('source_vertices', 'active_fraction', 'compression_fraction')},
              'active_vertices': len(candidate['regional_support']['active']),
              'compression_vertices': len(candidate['regional_support']['compression']),
              'full_face_duplicate_exists': cmds.objExists('EdwardWrinkles_Face')}
elif action == 'profile':
    from maya_tools.scripts.tools import rig_benchmark
    path = folder / ('%s_detail%d.mayaProfile' % (TRIAL_ARGUMENTS['variant'], TRIAL_ARGUMENTS['detail']))
    cmds.profiler(reset=True)
    cmds.profiler(bufferSize=64)
    result = rig_benchmark.capture_profile('Edward', path, cases=cases(), frames=(1, 24), detail=TRIAL_ARGUMENTS['detail'])
elif action == 'reopen':
    path = folder / 'Edward_regional_trial.mb'
    cmds.file(str(path), open=True, force=True, prompt=False, executeScriptNodes=False)
    result = {'scene': str(path), 'head': displayed_head(), 'wrinkles': bw.export_setups()[0]['settings']}
elif action == 'cache_quality':
    import numpy as np
    from maya_tools.scripts.tools import rig_benchmark as rb, pose_blendshapes as poses
    resolved, missing, _ = qa.resolve_cases('Edward', cases())
    initial = {p: cmds.getAttr(p) for p in resolved[0]['values']}
    initial['Edward.detailMode'] = cmds.getAttr('Edward.detailMode')
    initial['EdwardWrinkles_Settings.Depth'] = cmds.getAttr('EdwardWrinkles_Settings.Depth')
    initial['EdwardWrinkles_Settings.ManualActivation'] = cmds.getAttr('EdwardWrinkles_Settings.ManualActivation')
    result = {'maximum_error': 0., 'checks': []}
    with rb.evaluation_session(), poses._temporary_values(initial), rb.temporal_workload(resolved, (1, 48)):
        cmds.evaluationManager(mode='parallel'); cmds.evaluator(name='deformer', enable=True)
        rp.set_detail_mode('Edward', 1)
        cmds.setAttr('EdwardWrinkles_Settings.ManualActivation', 1)
        def sample(frame):
            cmds.currentTime(frame); cmds.refresh(force=True)
            return np.asarray(qa.mesh_data(displayed_head())['points'])
        cmds.evaluator(name='cache', enable=False)
        baseline = {f: sample(f) for f in (12, 24, 36)}
        cmds.cacheEvaluator(cacheFillMode='syncAsync'); cmds.evaluator(name='cache', enable=True)
        rb._play_once((1, 48)); cmds.cacheEvaluator(waitForCache=10.)
        result['initial_coverage'] = cmds.cacheEvaluator(query=True, cachedFrames=True)
        for frame, expected in baseline.items():
            error = float(np.max(np.linalg.norm(sample(frame) - expected, axis=1)))
            result['maximum_error'] = max(result['maximum_error'], error)
        curve = cmds.connectionInfo('C_jaw_CTL.rotateX', sourceFromDestination=True).split('.')[0]
        old = cmds.getAttr('C_jaw_CTL.rotateX')
        cmds.setKeyframe(curve, time=24, value=old + 10)
        result['after_key_coverage'] = cmds.cacheEvaluator(query=True, cachedFrames=True)
        edited = sample(24)
        result['key_edit_change'] = float(np.max(np.linalg.norm(edited - baseline[24], axis=1)))
        cmds.evaluator(name='cache', enable=False)
        expected = sample(24)
        result['maximum_error'] = max(result['maximum_error'], float(np.max(np.linalg.norm(edited - expected, axis=1))))
        cmds.evaluator(name='cache', enable=True)
        cmds.setAttr('EdwardWrinkles_Settings.Depth', initial['EdwardWrinkles_Settings.Depth'] + .2)
        edited = sample(24)
        result['depth_edit_change'] = float(np.max(np.linalg.norm(edited - expected, axis=1)))
        cmds.evaluator(name='cache', enable=False)
        result['maximum_error'] = max(result['maximum_error'], float(np.max(np.linalg.norm(edited - sample(24), axis=1))))
        for mode in (0, 1, 2, 1):
            rp.set_detail_mode('Edward', mode)
            cmds.evaluator(name='cache', enable=True); cached = sample(24)
            cmds.evaluator(name='cache', enable=False); uncached = sample(24)
            result['maximum_error'] = max(result['maximum_error'], float(np.max(np.linalg.norm(cached - uncached, axis=1))))
            result['checks'].append(mode)
    result['success'] = result['maximum_error'] <= 1e-4 and result['key_edit_change'] > .01 and result['depth_edit_change'] > .01
    (folder / 'cache_quality.json').write_text(json.dumps(result, indent=2))
elif action == 'interaction':
    result = rp.benchmark('Edward', folder / (TRIAL_ARGUMENTS['variant'] + '.viewport.json'),
                          cases=cases(), repeats=3, profile=False)
elif action == 'dependencies':
    result = {'references': cmds.file(query=True, reference=True) or [],
              'textures': {n: cmds.getAttr(n + '.fileTextureName') for n in cmds.ls(type='file') or []},
              'images': {n: cmds.getAttr(n + '.filename') for n in cmds.ls(type='aiImage') or []}}
    (folder / 'dependencies.json').write_text(json.dumps(result, indent=2))
elif action == 'freeze_working':
    from maya_tools.scripts.tools import wrinkle_presets, skin_manager_api
    rp.set_detail_mode('Edward', 1)
    scene = repo / 'maya_tools/assets/Edward/scenes/Edward_working_v002.mb'
    skc = repo / 'maya_tools/assets/Edward/skin_clusters/Edward_v066.skc'
    preset = repo / 'maya_tools/assets/Edward/wrinkles/Edward_v002.wrinkles.json'
    if any(p.exists() for p in (scene, skc, preset)):
        raise ValueError('Use new working asset versions.')
    cmds.optionVar(stringValue=('currentAssetRigName', 'Edward'))
    cmds.select(clear=True)
    manager = skin_manager_api.SkinManager()
    manager.export_skins(str(skc))
    wrinkle_presets.export_preset('EdwardWrinkles_Settings', preset)
    cmds.file(rename=str(scene)); cmds.file(save=True, type='mayaBinary', force=True)
    result = {'scene': str(scene), 'skc': str(skc), 'preset': str(preset),
              'scene_sha256': hashlib.sha256(scene.read_bytes()).hexdigest()}
    (folder / 'working_asset.json').write_text(json.dumps(result, indent=2))
elif action == 'export_skin':
    from maya_tools.scripts.tools import skin_manager_api
    reload(skin_manager_api)
    path = repo / 'maya_tools/assets/Edward/skin_clusters' / ('Edward_v%03d.skc' % TRIAL_ARGUMENTS.get('version', 68))
    if path.exists():
        raise ValueError('Choose a new SKC version.')
    cmds.select(clear=True)
    skin_manager_api.SkinManager().export_skins(str(path))
    data = json.loads(path.read_text())
    result = {'path': str(path), 'high_head_layers': len(data.get('cabeza_high_Shape', [])),
              'low_head_layers': len(data.get('cabeza_low_Shape', []))}
    if result['high_head_layers'] != 8:
        raise ValueError('The export lost high-head skin layers.')
elif action == 'reopen_working':
    before = capture_quality()
    cmds.file(str(repo / 'maya_tools/assets/Edward/scenes/Edward_working_v002.mb'),
              open=True, force=True, prompt=False, executeScriptNodes=False)
    after = capture_quality()
    import numpy as np
    error = 0.
    for mode in before['modes']:
        for a, b in zip(before['modes'][mode], after['modes'][mode]):
            for mesh in a['meshes']:
                error = max(error, float(np.max(np.linalg.norm(np.asarray(a['meshes'][mesh]['points']) - b['meshes'][mesh]['points'], axis=1))))
    result = {'success': error <= 1e-4, 'reopen_maximum_error': error,
              'pose_count': len(after['definitions']), 'high_head_layers': len(cmds.ls(cmds.listHistory('cabeza_high'), type='skinCluster'))}
    (folder / 'working_reopen.json').write_text(json.dumps(result, indent=2))
else:
    raise ValueError('Unknown trial action: ' + action)
progress.write_text(json.dumps({'action': action, 'status': 'completed', 'utc': datetime.now(timezone.utc).isoformat()}))
