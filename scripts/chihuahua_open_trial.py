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
FOLDER = ROOT / 'tmp/chihuahua_open_20261016_v001'
FOLDER.mkdir(parents=True, exist_ok=True)


def run():
    sys.path[:0] = [str(RUNTIME), str(RUNTIME/'maya_tools/scripts')]
    from maya import cmds, mel
    from maya.api import OpenMaya as om
    from maya_tools.scripts.utils import model_cache
    source = RUNTIME/'maya_tools/assets/chihuahua/models/chihuahua_v001.ma'
    report = {'pid': os.getpid(), 'runtime': model_cache.__file__, 'source': str(source),
              'source_sha256': model_cache.digest(source), 'api': cmds.about(apiVersion=True),
              'samples': [], 'scope': 'Interactive Maya, open command and explicit redraw measured separately; warm OS/plugin state.'}

    def commit():
        (FOLDER/'progress.json').write_text(json.dumps(report, indent=2))

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
    started = time.perf_counter(); cmds.file(str(source), open=True, force=True)
    report['cold_source_open_seconds'] = time.perf_counter()-started
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4', edit=True, displayAppearance='smoothShaded', rendererName='vp2Renderer')
    cmds.refresh(force=True)
    # The cache already exists from CREATE RIG. Its content hashes are checked by open_model.
    signatures = {}
    for index, kind in enumerate(('source', 'cache', 'cache', 'source', 'source', 'cache')):
        report['phase'] = '%s_%s' % (index, kind); commit()
        cmds.file(new=True, force=True)
        start = time.perf_counter()
        if kind == 'source':
            cmds.file(str(source), open=True, force=True)
            info = {'cache_hit': False}
        else:
            info = model_cache.open_model(source)
            assert info['cache_hit'], 'Expected the pre-existing validated cache'
        opened = time.perf_counter()
        cmds.refresh(force=True)
        drawn = time.perf_counter()
        report['samples'].append({'kind': kind, 'open_seconds': opened-start,
                                  'redraw_seconds': drawn-opened, 'total_seconds': drawn-start,
                                  'scene': cmds.file(q=True, sceneName=True), **info})
        commit()
        if kind not in signatures:
            signatures[kind] = signature()
    report['quality'] = {'exact_match': signatures['source'] == signatures['cache'],
                         'mesh_count': len(signatures['source']['meshes']),
                         'xgen_node_count': len(signatures['source']['xgen_nodes']),
                         'checked': 'All mesh positions/topology/face-vertex normals/UVs/material memberships, transform matrices, XGen node identities/connections, texture paths, frame and units.'}
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
