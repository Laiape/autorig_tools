"""Owned interactive model-open comparison; never touches artist sessions."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import struct
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'autorig_tools'
FOLDER = Path(os.environ.get('AUTORIG_CHIHUAHUA_TRIAL_FOLDER', str(ROOT / 'tmp/chihuahua_open_20261016_v001')))
FOLDER.mkdir(parents=True, exist_ok=True)


def run():
    sys.path[:0] = [str(RUNTIME), str(RUNTIME/'maya_tools/scripts')]
    from maya import cmds, mel
    from maya.api import OpenMaya as om
    from maya_tools.scripts.utils import model_cache
    importing = os.environ.get('AUTORIG_CHIHUAHUA_TRIAL_OPERATION') == 'import'
    source = RUNTIME/'maya_tools/assets/chihuahua/models/chihuahua_v001.ma'
    baseline = Path(os.environ.get('AUTORIG_CHIHUAHUA_TRIAL_BASELINE', str(source)))
    candidate = os.environ.get('AUTORIG_CHIHUAHUA_TRIAL_CANDIDATE')
    report = {'pid': os.getpid(), 'runtime': model_cache.__file__, 'source_path': str(source),
              'operation': 'import' if importing else 'open',
              'baseline': str(baseline), 'candidate': candidate,
              'source_sha256': model_cache.digest(source), 'api': cmds.about(apiVersion=True),
              'samples': [], 'scope': 'Interactive Maya, open command and explicit redraw measured separately; warm OS/plugin state.'}

    def commit():
        (FOLDER/'progress.json').write_text(json.dumps(report, indent=2))

    def prepare():
        cmds.file(new=True, force=True)
        if importing:
            cmds.createNode('transform', name='C_guides_GRP')
            cmds.setAttr('C_guides_GRP.translateX', 12)

    def load_source():
        if importing:
            cmds.file(str(baseline), i=True, type='mayaBinary' if baseline.suffix.lower() == '.mb' else 'mayaAscii', ignoreVersion=True,
                      mergeNamespacesOnClash=False, namespace=':')
        else:
            cmds.file(str(baseline), open=True, force=True)

    def signature():
        meshes = {}
        for name in cmds.ls(type='mesh', long=True):
            selection = om.MSelectionList(); selection.add(name)
            fn = om.MFnMesh(selection.getDagPath(0))
            def hashed(values):
                return hashlib.sha256(values).hexdigest()
            points = [v for point in fn.getPoints(om.MSpace.kWorld) for v in (point.x, point.y, point.z)]
            counts, ids = fn.getVertices()
            normals = [v for normal in fn.getFaceVertexNormals(om.MSpace.kWorld) for v in normal]
            uvs = {}
            for uvset in fn.getUVSetNames():
                u, v = fn.getUVs(uvset); uc, ui = fn.getAssignedUVs(uvset)
                uvs[uvset] = hashed(struct.pack('<%sd' % (len(u)+len(v)), *(list(u)+list(v))) +
                                    struct.pack('<%si' % (len(uc)+len(ui)), *(list(uc)+list(ui))))
            shaders, assigned = fn.getConnectedShaders(0)
            meshes[name] = {'points': hashed(struct.pack('<%sd' % len(points), *points)),
                            'topology': hashed(struct.pack('<%si' % (len(counts)+len(ids)), *(list(counts)+list(ids)))),
                            'normals': hashed(struct.pack('<%sd' % len(normals), *normals)), 'uvs': uvs,
                            'shaders': [om.MFnDependencyNode(s).name() for s in shaders], 'faces': list(assigned)}
        xgen = sorted((n, cmds.nodeType(n), cmds.ls(n, uuid=True)[0]) for n in cmds.ls() if cmds.nodeType(n).startswith('xgm'))
        return {'meshes': meshes, 'xgen_nodes': xgen,
                'connections': sorted(cmds.listConnections([n[0] for n in xgen], connections=True, plugs=True) or []) if xgen else [],
                'files': {n: cmds.getAttr(n+'.fileTextureName') for n in cmds.ls(type='file')},
                'transforms': {n: cmds.xform(n, q=True, matrix=True, worldSpace=True) for n in cmds.ls(type='transform', long=True)},
                'frame': cmds.currentTime(q=True), 'units': [cmds.currentUnit(q=True, linear=True), cmds.currentUnit(q=True, time=True)]}

    cmds.evaluationManager(mode='off')
    cmds.evaluator(name='cache', enable=False)
    # Warm renderer/plugin loading before the comparable samples.
    report['phase'] = 'warmup'; commit()
    prepare()
    started = time.perf_counter(); load_source()
    report['cold_source_open_seconds'] = time.perf_counter()-started
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4', edit=True, displayAppearance='smoothShaded', rendererName='vp2Renderer')
    cmds.refresh(force=True)
    # The cache already exists from CREATE RIG. Its content hashes are checked by open_model.
    signatures = {}
    for index, kind in enumerate(('source', 'cache', 'cache', 'source', 'source', 'cache')):
        report['phase'] = '%s_%s' % (index, kind); commit()
        prepare()
        start = time.perf_counter()
        if kind == 'source':
            load_source()
            info = {'cache_hit': False}
        else:
            chosen_source = candidate or source
            info = (model_cache.import_model(chosen_source, ignoreVersion=True, mergeNamespacesOnClash=False, namespace=':')
                    if importing else model_cache.open_model(chosen_source))
            assert info['cache_hit'] or candidate, 'Expected the pre-existing validated cache'
        opened = time.perf_counter()
        cmds.refresh(force=True)
        drawn = time.perf_counter()
        report['samples'].append({'kind': kind, 'open_seconds': opened-start,
                                  'redraw_seconds': drawn-opened, 'total_seconds': drawn-start,
                                  'scene': cmds.file(q=True, sceneName=True), **info})
        commit()
        if importing:
            assert cmds.getAttr('C_guides_GRP.translateX') == 12, 'Guide scene replaced during import'
        if kind not in signatures:
            signatures[kind] = signature()
    report['quality'] = {'exact_match': signatures['source'] == signatures['cache'],
                         'mesh_count': len(signatures['source']['meshes']),
                         'xgen_node_count': len(signatures['source']['xgen_nodes']),
                         'checked': 'All mesh positions/topology/face-vertex normals/UVs/material memberships, transform matrices, XGen node identities/connections, texture paths, frame and units.'}
    if candidate:
        assert not cmds.getAttr('xgen.visibility'), 'Expected the authorized hidden groom startup'
        cmds.setAttr('xgen.visibility', True)
        cmds.refresh(force=True)
        report['quality']['groom_reenabled_matches_source'] = signature() == signatures['source']
        report['quality']['intentional_change'] = 'Only xgen.visibility starts OFF in the candidate.'
        assert report['quality']['groom_reenabled_matches_source']
        cmds.playblast(format='image', compression='png', completeFilename=str(FOLDER/'groom_reenabled.png'),
                       forceOverwrite=True, viewer=False, showOrnaments=False, widthHeight=(960, 720),
                       frame=cmds.currentTime(q=True), percent=100, offScreen=True)
    (FOLDER/'signatures.json').write_text(json.dumps(signatures, sort_keys=True))
    for kind in ('source', 'cache'):
        rows = [r for r in report['samples'] if r['kind'] == kind]
        report[kind] = {key: statistics.median(r[key] for r in rows) for key in ('open_seconds', 'redraw_seconds', 'total_seconds')}
    report['source_unchanged'] = model_cache.digest(source) == report['source_sha256']
    report['phase'] = 'complete'; commit()
    assert report['quality']['exact_match'], 'Native binary model does not match source'
    assert report['source_unchanged']
    (FOLDER/'result.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    from maya import cmds
    try:
        run()
    except BaseException:
        (FOLDER/'failure.txt').write_text(traceback.format_exc())
    finally:
        cmds.quit(force=True)
