"""Opt-in Edward skin-only delivery snapshot and owned Maya verification."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(r'C:/proyectos/auto-rig')
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/skin_only_delivery_20261016_v001'
FOLDER.mkdir(parents=True, exist_ok=True)


def inspect_artist():
    from maya import cmds
    assert os.getpid() == 23404
    return {'pid': os.getpid(), 'scene': cmds.file(q=True, sn=True),
            'modified': cmds.file(q=True, modified=True),
            'skins': len(cmds.ls(type='skinCluster')),
            'prx': cmds.ls(type='proximityWrap'),
            'blendshapes': cmds.ls(type='blendShape'),
            'requested': {n: {'matches': cmds.ls(n, long=True),
                'skins': cmds.ls(cmds.listHistory(n) or [], type='skinCluster')
                    if cmds.objExists(n) else []} for n in ('cinturones2', 'pCube26')}}


def snapshot_artist():
    from maya import cmds
    before = inspect_artist()
    target = FOLDER / 'Edward_artist_before_skin_only.ma'
    assert not target.exists()
    cmds.file(str(target), exportAll=True, type='mayaAscii', force=False,
              options='v=0;', preserveReferences=True)
    after = inspect_artist()
    assert before == after, 'Snapshot changed artist scene state'
    data = {'path': str(target), 'artist': before, 'state_preserved': True}
    (FOLDER / 'snapshot.json').write_text(json.dumps(data, indent=2))
    return data


def apply_changes():
    from maya import cmds
    manifest = json.loads((ROOT / 'maya_tools/assets/Edward/experiments/'
                         'all_prx_bakes_20261016_v001/manifest.json').read_text())
    records = {}
    for wrap, item in manifest['items'].items():
        mesh = item['source']
        leaf = mesh.rsplit('|', 1)[-1]
        skins = cmds.ls(cmds.listHistory(mesh) or [], type='skinCluster')
        assert len(skins) == 1, (mesh, skins)
        skin = skins[0]
        records[wrap] = {'source': mesh, 'skin': skin,
                         'rest': leaf + '_BakedBindRest_BLS',
                         'before_method': cmds.getAttr(skin + '.skinningMethod')}
    rest = [r['rest'] for r in records.values()]
    assert all(cmds.objExists(n) and cmds.nodeType(n) == 'blendShape' for n in rest)
    other_bs = set(cmds.ls(type='blendShape')) - set(rest)
    cmds.delete(rest)
    for record in records.values():
        method = 0 if record['source'].rsplit('|', 1)[-1] in ('cinturones2', 'pCube26') else record['before_method']
        cmds.setAttr(record['skin'] + '.skinningMethod', method)
        record['method'] = method
    assert set(cmds.ls(type='blendShape')) == other_bs
    assert not cmds.ls('*_BakedBindRest_BLS')
    assert not cmds.ls(type='proximityWrap')
    return {'records': records, 'removed_blendshapes': rest,
            'preserved_original_blendshapes': sorted(other_bs)}


def apply_artist():
    from maya import cmds
    assert os.getpid() == 23404
    assert (FOLDER / 'published.json').exists()
    before = inspect_artist()
    assert before == json.loads((FOLDER / 'snapshot.json').read_text())['artist'], 'Artist changed during export'
    cmds.undoInfo(openChunk=True, chunkName='EdwardSkinOnlyGarments')
    try:
        data = apply_changes()
    finally:
        cmds.undoInfo(closeChunk=True)
    return {'changes': data, 'scene': cmds.file(q=True, sn=True),
            'modified': cmds.file(q=True, modified=True)}


def export_verify():
    import copy
    import hashlib
    import numpy as np
    from maya import cmds
    from maya.api import OpenMaya as om, OpenMayaAnim as oma
    from tools import proximity_wrap as pw
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    assert os.getpid() == json.loads((FOLDER / 'owned_launch.json').read_text())['pid']
    manifest = json.loads((ROOT / 'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001/manifest.json').read_text())

    def pose(values):
        for plug in manifest['axes']:
            cmds.setAttr(plug, values.get(plug, 0))
        for plug in ('C_masterwalk_CTL.translateX', 'C_masterwalk_CTL.rotateY'):
            cmds.setAttr(plug, values.get(plug, 0))
        cmds.setAttr('C_masterwalk_CTL.globalScale', values.get('C_masterwalk_CTL.globalScale', 1))
        for side in ('L', 'R'):
            for limb in ('arm', 'leg'):
                cmds.setAttr(side + '_' + limb + 'Settings_CTL.Ik_Fk', 1)

    def mesh_path(mesh):
        selection = om.MSelectionList(); selection.add(pw.mesh_shape(mesh))
        return selection.getDagPath(0)

    def surface(mesh):
        path = mesh_path(mesh); cmds.dgeval(path.fullPathName() + '.outMesh')
        fn = om.MFnMesh(path)
        return np.asarray(fn.getPoints(om.MSpace.kWorld))[:, :3].copy(), np.asarray(fn.getFaceVertexNormals(om.MSpace.kWorld))[:, :3].copy()

    def weights(record):
        selection = om.MSelectionList(); selection.add(record['skin'])
        fn = oma.MFnSkinCluster(selection.getDependNode(0)); path = mesh_path(record['source'])
        cf = om.MFnSingleIndexedComponent(); component = cf.create(om.MFn.kMeshVertComponent)
        cf.setCompleteData(om.MFnMesh(path).numVertices)
        names = [p.fullPathName() for p in fn.influenceObjects()]
        return np.asarray(fn.getWeights(path, component)[0]).reshape(-1, len(names)).copy(), np.asarray(fn.getBlendWeights(path, component)).copy(), names

    pose({})
    before = {}
    neutral_before = {}
    for wrap, item in manifest['items'].items():
        mesh = item['source']; skin = cmds.ls(cmds.listHistory(mesh) or [], type='skinCluster')[0]
        before[wrap] = weights({'skin': skin, 'source': mesh})
        neutral_before[wrap] = surface(mesh)[0]
    data = apply_changes(); records = data['records']
    neutral_changes = {w: float(np.linalg.norm(surface(r['source'])[0] - neutral_before[w], axis=1).max())
                       for w, r in records.items()}
    for wrap, record in records.items():
        a, b, names = weights(record); old, oldb, oldnames = before[wrap]
        assert names == oldnames and np.array_equal(a, old) and np.array_equal(b, oldb)
    native = FOLDER / 'Edward_skin_only_canonical_v001.ma'
    assert not native.exists()
    cmds.select(clear=True); cmds.file(rename=str(native)); cmds.file(save=True, type='mayaAscii', force=False, options='v=0;')
    obj = SkinManager.__new__(SkinManager)
    obj.k_skin_attrs = ['skinningMethod', 'normalizeWeights', 'maintainMaxInfluences', 'maxInfluences', 'weightDistribution']
    obj.tolerance = 1e-5; obj.folder_path = str(ROOT / 'autorig_tools/maya_tools/assets/Edward/skin_clusters')
    obj.asset_name = 'Edward'; obj.ext = '.skc'
    raw = FOLDER / 'Edward_skin_only_raw.skc'; assert not raw.exists()
    obj.export_skins(str(raw), lossless=True)
    package = json.loads(raw.read_text()); metadata = package[obj.SCENE_DEFORMERS_KEY]
    assert not any(n['name'] in data['removed_blendshapes'] or n['type'] == 'proximityWrap' for n in metadata['nodes'])
    assert not any('_ALLPRX_' in n['name'] for n in metadata['nodes'])
    keys = {}
    for wrap, record in records.items():
        key = next(k for k, v in package.items() if not k.startswith('__') and any(e['name'] == record['skin'] for e in v))
        if key != record['source']:
            assert record['source'] not in package
            package[record['source']] = package.pop(key)
        keys[wrap] = record['source']
    staged = FOLDER / 'Edward_skin_only_staged.skc'; assert not staged.exists()
    with staged.open('x') as stream:
        json.dump(package, stream, separators=(',', ':'), allow_nan=False)
    cases = [('neutral', {}), ('torso', {'C_spine03_CTL.rotateY': -20, 'C_localChest_CTL.rotateZ': 15}),
             ('arms', {'L_shoulderFk_CTL.rotateZ': 70, 'R_shoulderFk_CTL.rotateY': 35}),
             ('legs', {'L_hipFk_CTL.rotateX': 25, 'R_hipFk_CTL.rotateZ': 55, 'L_ankleFk_CTL.rotateX': 20}),
             ('neck', {'C_neck_CTL.rotateY': 25, 'C_head_CTL.rotateZ': 15}),
             ('global', {'C_masterwalk_CTL.translateX': 12, 'C_masterwalk_CTL.rotateY': 25}),
             ('scale', {'C_masterwalk_CTL.globalScale': 1.15})]
    baseline = {}
    for name, values in cases:
        pose(values); baseline[name] = {w: surface(r['source']) for w, r in records.items()}
    pose({})
    subset = {keys[w]: copy.deepcopy(package[keys[w]]) for w in records}
    meta = copy.deepcopy(metadata); names = {r['skin'] for r in records.values()}
    meta['nodes'] = [n for n in meta['nodes'] if n['name'] in names]
    meta['geometry_stacks'] = {pw.mesh_shape(r['source']): [r['skin']] for r in records.values()}
    for key in ('auxiliary_nodes', 'pose_targets', 'orientation_systems', 'detail_modes'):
        meta[key] = []
    subset[obj.SCENE_DEFORMERS_KEY] = meta
    partial = FOLDER / 'skin_only_roundtrip.skc'
    with partial.open('x') as stream:
        json.dump(subset, stream, separators=(',', ':'))
    cmds.delete(list(names))
    for record in records.values():
        cmds.rename(pw.mesh_shape(record['source']), record['source'].rsplit('|', 1)[-1] + '_ModelShapeRoundtrip')
    obj.import_skins(str(partial), replace_existing=True, import_wrinkles=False)
    rows = []
    for name, values in cases + list(reversed(cases)):
        pose(values)
        for wrap, record in records.items():
            p, n = surface(record['source']); bp, bn = baseline[name][wrap]
            rows.append({'pose': name, 'mesh': record['source'],
                         'max_position_cm': float(np.linalg.norm(p - bp, axis=1).max()),
                         'max_normal_error': float(np.linalg.norm(n - bn, axis=1).max())})
    max_weight = 0.
    for wrap, record in records.items():
        a, b, names = weights(record); old, oldb, oldnames = before[wrap]
        columns = [oldnames.index(n) for n in names]
        max_weight = max(max_weight, float(np.abs(a - old[:, columns]).max()))
        assert np.array_equal(b, oldb)
        assert cmds.getAttr(record['skin'] + '.skinningMethod') == record['method']
    quality = {'comparisons': len(rows), 'max_position_cm': max(r['max_position_cm'] for r in rows),
               'max_normal_error': max(r['max_normal_error'] for r in rows), 'max_weight_error': max_weight}
    quality['passed'] = quality['max_position_cm'] <= 1e-4 and quality['max_normal_error'] <= 1e-4 and max_weight == 0
    pose({})
    cmds.file(str(native), open=True, force=True, prompt=False, executeScriptNodes=False)
    reopened_position = 0.; reopened_normal = 0.
    for name, values in cases:
        pose(values)
        for wrap, record in records.items():
            p, n = surface(record['source']); bp, bn = baseline[name][wrap]
            reopened_position = max(reopened_position, float(np.linalg.norm(p - bp, axis=1).max()))
            reopened_normal = max(reopened_normal, float(np.linalg.norm(n - bn, axis=1).max()))
            assert cmds.getAttr(record['skin'] + '.skinningMethod') == record['method']
    quality['native_reopen_max_position_cm'] = reopened_position
    quality['native_reopen_max_normal_error'] = reopened_normal
    quality['passed'] = quality['passed'] and reopened_position <= 1e-4 and reopened_normal <= 1e-4
    pose({})
    report = dict(data, staged_skc=str(staged), native_scene=str(native), keys=keys, roundtrip=quality,
                  skin_count=len(cmds.ls(type='skinCluster')),
                  serialized_skin_count=sum(len(v) for k, v in package.items() if not k.startswith('__')),
                  wrinkles_present=bool(package.get(obj.WRINKLES_KEY)),
                  neutral_changes_cm=neutral_changes,
                  runtime=sys.modules[SkinManager.__module__].__file__,
                  staged_sha256=hashlib.sha256(staged.read_bytes()).hexdigest())
    (FOLDER / 'roundtrip_rows.json').write_text(json.dumps(rows, indent=2))
    (FOLDER / 'verified_export.json').write_text(json.dumps(report, indent=2))
    assert quality['passed'], quality
    return {k: v for k, v in report.items() if k not in ('records', 'keys')}


if __name__ == '__main__' or 'TRIAL_ARGUMENTS' in globals():
    action = globals().get('TRIAL_ARGUMENTS', {}).get('action', 'inspect')
    if action == 'inspect':
        result = inspect_artist()
    elif action == 'snapshot':
        result = snapshot_artist()
    elif action == 'export':
        result = export_verify()
    elif action == 'apply_artist':
        result = apply_artist()
