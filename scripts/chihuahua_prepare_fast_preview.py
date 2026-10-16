"""Create the user-requested native model with its groom hidden on opening."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'autorig_tools'
sys.path[:0] = [str(RUNTIME), str(RUNTIME/'maya_tools/scripts')]
FOLDER = ROOT/'tmp/chihuahua_fast_preview_20261016'
FOLDER.mkdir(parents=True, exist_ok=True)
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import model_cache

source = RUNTIME/'maya_tools/assets/chihuahua/models/chihuahua_v001.ma'
target = source.with_name('chihuahua_v002.mb')
assert not target.exists(), 'Never overwrite a model version'
cache = model_cache._cache_record(source)
assert cache['valid'], 'Expected the verified original binary'
cmds.evaluationManager(mode='off')
started = time.perf_counter()
cmds.file(str(cache['binary']), open=True, force=True, executeScriptNodes=False)

def signature():
    meshes = {}
    for name in cmds.ls(type='mesh', long=True):
        selection = om.MSelectionList(); selection.add(name)
        fn = om.MFnMesh(selection.getDagPath(0))
        points = [v for p in fn.getPoints(om.MSpace.kWorld) for v in (p.x, p.y, p.z)]
        counts, ids = fn.getVertices()
        normals = [v for n in fn.getFaceVertexNormals(om.MSpace.kWorld) for v in n]
        uvdata = {}
        for uvset in fn.getUVSetNames():
            u, v = fn.getUVs(uvset); uc, ui = fn.getAssignedUVs(uvset)
            uvdata[uvset] = [list(u), list(v), list(uc), list(ui)]
        shaders, faces = fn.getConnectedShaders(0)
        meshes[name] = {'points': hashlib.sha256(struct.pack('<%sd' % len(points), *points)).hexdigest(),
                        'topology': [list(counts), list(ids)],
                        'normals': hashlib.sha256(struct.pack('<%sd' % len(normals), *normals)).hexdigest(),
                        'uvs': uvdata, 'materials': [om.MFnDependencyNode(n).name() for n in shaders],
                        'faces': list(faces)}
    groom = sorted(cmds.ls(type='xgmSplineDescription'))
    return {'meshes': meshes, 'nodes': sorted((n, cmds.nodeType(n)) for n in cmds.ls()),
            'groom': groom, 'groom_connections': sorted(cmds.listConnections(groom, connections=True, plugs=True) or []),
            'transforms': {n: cmds.xform(n, q=True, matrix=True, worldSpace=True) for n in cmds.ls(type='transform', long=True)}}

original = signature()
assert len(original['groom']) == 4 and cmds.objExists('|xgen')
original_visibility = cmds.getAttr('xgen.visibility')
assert original_visibility and not cmds.listConnections('xgen.visibility', source=True, destination=False)
cmds.setAttr('xgen.visibility', False)
cmds.file(rename=str(target))
cmds.file(save=True, type='mayaBinary')
cmds.file(str(target), open=True, force=True, executeScriptNodes=False)
assert not cmds.getAttr('xgen.visibility')
assert signature() == original, 'The preview changed model or groom ownership'
cmds.setAttr('xgen.visibility', original_visibility)
assert signature() == original, 'Re-enabled groom differs from original'
report = {'source': str(source), 'candidate': str(target),
          'source_sha256': model_cache.digest(source), 'candidate_sha256': model_cache.digest(target),
          'intentional_change': 'xgen.visibility = 0; set Visibility on xgen to 1 to show all four groom descriptions.',
          'mesh_count': len(original['meshes']), 'groom_count': len(original['groom']),
          'native_reopen_exact_model_and_connections': True, 're_enable_exact_model_and_connections': True,
          'elapsed_seconds': time.perf_counter()-started}
(FOLDER/'prepare.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
os._exit(0)
