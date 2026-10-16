import hashlib
import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import rig_manager

base = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
source = base/'flower_v01.ma'
cmds.file(str(source), open=True, force=True, executeScriptNodes=False)
cmds.evaluationManager(mode='off')
cmds.optionVar(sv=('currentAssetRigName', 'flower'))
rig_manager.create_assets_folders('flower')
for sub in ('scenes', 'rig_data', 'validation'):
    (base/sub).mkdir(exist_ok=True)
mapping = {'msh_stem': 'C_stem_GEO', 'msh_in': 'C_flowerCore_GEO',
           'msh_leaves': 'C_leaves_GEO', 'msh_petals_A': 'C_petalsA_GEO', 'msh_petals_B': 'C_petalsB_GEO'}
for old, new in mapping.items():
    cmds.rename(old, new)
cmds.rename('grp_EdwardFlower', 'flower')
cmds.rename('grp_flower', 'flowerHeadModel_GRP')

def points(mesh):
    sl = om.MSelectionList(); sl.add(mesh)
    path = sl.getDagPath(0); path.extendToShape()
    fn = om.MFnMesh(path)
    return fn, np.array([[p.x, p.y, p.z] for p in fn.getPoints(om.MSpace.kWorld)])

def shells(fn):
    counts, indices = fn.getVertices(); adjacency = [set() for _ in range(fn.numVertices)]; cursor = 0
    for count in counts:
        face = list(indices[cursor:cursor+count]); cursor += count
        for index in face:
            adjacency[index].update(face)
    unseen = set(range(fn.numVertices)); output = []
    while unseen:
        start = min(unseen); unseen.remove(start); todo = [start]; found = {start}
        while todo:
            for index in adjacency[todo.pop()]:
                if index in unseen:
                    unseen.remove(index); found.add(index); todo.append(index)
        output.append(sorted(found))
    return output

def frame(position, direction, up):
    x = direction / np.linalg.norm(direction)
    y = up - x*np.dot(up, x); y /= np.linalg.norm(y)
    z = np.cross(x, y)
    return [*x.tolist(), 0., *y.tolist(), 0., *z.tolist(), 0., *position.tolist(), 1.]

core_fn, core = points('C_flowerCore_GEO')
center = core.mean(axis=0)
_, vec = np.linalg.eigh(np.cov((core-center).T)); normal = vec[:, 0]
if normal[1] < 0:
    normal *= -1
stem_fn, stem = points('C_stem_GEO')
# Ring centers follow the authored bent stem, including its terminal cap.
ys = np.unique(np.round(stem[:, 1], 4))
order = np.argsort(stem[:, 1])
stem_positions = []
for y in np.linspace(stem[:, 1].min(), stem[:, 1].max(), 7):
    nearby = np.argsort(np.abs(stem[:, 1]-y))[:10]
    stem_positions.append(stem[nearby].mean(axis=0))
stem_positions = np.array(stem_positions)
guides = {}

def add_chain(prefix, positions, up):
    names = []
    for index, pos in enumerate(positions):
        name = '%s%02d_JNT' % (prefix, index)
        direction = positions[min(index+1, len(positions)-1)] - positions[max(index-1, 0)]
        guides[name] = {'joint_matrix': frame(pos, direction, up),
                        'parent': names[-1] if names else 'C_guides_GRP',
                        'isJoint': True, 'isLocator': False, 'isCurve': False, 'isSurface': False,
                        'children': []}
        if names:
            guides[names[-1]]['children'].append(name)
        names.append(name)
    return names

stem_guides = add_chain('C_stem', stem_positions, np.array([0., 0., 1.]))
head_matrix = frame(center, np.array([1., 0., 0.]), normal)
guides['C_flowerHead_JNT'] = {'joint_matrix': head_matrix, 'parent': 'C_guides_GRP',
                           'isJoint': True, 'isLocator': False, 'isCurve': False, 'isSurface': False, 'children': []}
config = {'schema_version': 1, 'stem': {'prefix': 'C_stem', 'mesh': 'C_stem_GEO', 'guides': stem_guides},
          'head': {'guide': 'C_flowerHead_JNT', 'mesh': 'C_flowerCore_GEO'}, 'petals': [], 'leaves': []}
reference = {}
for mesh in mapping.values():
    fn, pts = points(mesh)
    counts, indices = fn.getVertices()
    reference[mesh] = {'points': pts.tolist(), 'topology': [list(counts), list(indices)],
                       'vertices': len(pts), 'faces': fn.numPolygons, 'uv_count': fn.numUVs(),
                       'nonmanifold_edges': cmds.polyInfo(mesh, nonManifoldEdges=True) or [],
                       'nonmanifold_vertices': cmds.polyInfo(mesh, nonManifoldVertices=True) or [],
                       'lamina_faces': cmds.polyInfo(mesh, laminaFaces=True) or []}
    if 'petals' not in mesh and 'leaves' not in mesh:
        continue
    parts = shells(fn)
    for index, ids in enumerate(parts):
        p = pts[ids]
        if 'petals' in mesh:
            direction = p.mean(axis=0)-center; direction -= normal*np.dot(direction, normal)
            layer = 'A' if 'petalsA' in mesh else 'B'
            prefix = 'C_petal%s%02d' % (layer, index+1)
            up = normal
        else:
            # The leaf base is the end closest to the stem centerline.
            distances = np.linalg.norm(p[:, None, :]-stem_positions[None, :, :], axis=2).min(axis=1)
            root = p[np.argsort(distances)[:4]].mean(axis=0)
            direction = p.mean(axis=0)-root
            prefix = 'C_leaf%02d' % (index+1)
            up = normal
        direction /= np.linalg.norm(direction)
        q = np.dot(p, direction); low, high = q.min(), q.max()
        positions = []
        for fraction in (0.02, 0.50, 0.94):
            target = low+(high-low)*fraction
            nearby = np.argsort(np.abs(q-target))[:6]
            positions.append(p[nearby].mean(axis=0))
        chain_guides = add_chain(prefix, np.array(positions), up)
        entry = {'prefix': prefix, 'mesh': mesh, 'vertices': ids, 'guides': chain_guides,
                 'vertex_count': fn.numVertices}
        if 'petals' in mesh:
            entry['layer'] = layer; config['petals'].append(entry)
        else:
            entry['attachment'] = int(np.argmin(np.linalg.norm(stem_positions-positions[0], axis=1)))
            config['leaves'].append(entry)

(base/'rig_data/source_geometry.json').write_text(json.dumps(reference))
(base/'build/flower_v001.build').write_text(json.dumps({'Rig_Type': 2, 'mGear_integration': 0}, indent=2))
(base/'rig_data/flower.json').write_text(json.dumps(config, indent=2))
(base/'guides/flower_v001.guides').write_text(json.dumps({'flower': dict(reversed(list(guides.items())))}, indent=2))
cmds.select('flower', replace=True)
model_path = base/'models/flower_v001.ma'
cmds.file(str(model_path), force=True, exportSelected=True, type='mayaAscii',
          constructionHistory=False, channels=False, constraints=False, expressions=False,
          shader=True, preserveReferences=False)
result = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'model': str(model_path),
          'meshes': {m: {k:v for k,v in r.items() if k != 'points' and k != 'topology'} for m,r in reference.items()},
          'petals': len(config['petals']), 'leaves': len(config['leaves']), 'stem_controls': len(stem_positions),
          'head_center': center.tolist(), 'head_normal': normal.tolist(),
          'runtime': rig_manager.__file__, 'original_preserved': True}
(base/'validation/asset_setup_20261016.json').write_text(json.dumps(result, indent=2))
