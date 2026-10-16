import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.flower.autorig import petal_module
from maya_tools.scripts.utils import scene_evaluation

base = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
original = json.loads((base/'rig_data/source_geometry.json').read_text())
config = json.loads((base/'build/flower_v001.build').read_text())['flower']
scene = base/'scenes/flower_rig_v001.mb'
cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
scene_evaluation.apply()

def points(mesh):
    sl = om.MSelectionList(); sl.add(mesh)
    path = sl.getDagPath(0); path.extendToShape()
    return np.array([[p.x, p.y, p.z] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)])

def snapshot():
    return {m: points(m) for m in original}

def error(a, b):
    return {m: float(np.linalg.norm(a[m]-b[m], axis=1).max()) for m in a}

report = {'neutral': error({m: np.array(v['points']) for m,v in original.items()}, snapshot()),
          'cases': []}
neutral = snapshot()
ctl = 'C_petalA0100_CTL'
cmds.setAttr(ctl+'.tz', 2.)
posed = snapshot()
entry = next(e for e in config['petals'] if e['prefix'] == 'C_petalA01')
delta = np.linalg.norm(posed[entry['mesh']]-neutral[entry['mesh']], axis=1)
shell = set(entry['vertices'])
report['independent_petal'] = {'inside_min': float(delta[list(shell)].min()),
                              'outside_max': float(max(delta[i] for i in range(len(delta)) if i not in shell)),
                              'other_mesh_max': max(v for m,v in error(neutral, posed).items() if m != entry['mesh'])}
cmds.setAttr(ctl+'.tz', 0.)
cmds.setAttr(ctl+'.curl', 45.)
report['curl_displacement'] = error(neutral, snapshot())
cmds.setAttr(ctl+'.curl', 0.)
cmds.setAttr('C_stem02_CTL.rz', 18)
cmds.setAttr('C_stem04_CTL.ry', -24)
cmds.setAttr('C_flowerHead_CTL.rz', 15)
cmds.setAttr('C_masterwalk_CTL.translate', 3, 2, -4, type='double3')
cmds.setAttr('C_masterwalk_CTL.rotate', 23, 38, -12, type='double3')
cmds.setAttr('C_masterwalk_CTL.globalScale', 1.6)
before = snapshot()
petal_module.set_space([ctl], space='World', key=False)
after = snapshot()
report['release_error'] = error(before, after)
released = points(entry['mesh'])[entry['vertices']]
cmds.setAttr('C_masterwalk_CTL.tx', 15)
cmds.setAttr('C_stem04_CTL.rz', 26)
moved = points(entry['mesh'])[entry['vertices']]
report['released_world_drift'] = float(np.linalg.norm(released-moved, axis=1).max())
petal_module.set_space([ctl], space='Head', key=False)
report['cycles'] = cmds.cycleCheck(all=True, list=True) or []
cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
cmds.currentTime(12)
before = snapshot()
petal_module.set_space([ctl], space='World', key=True)
report['keyed_release_error'] = error(before, snapshot())
report['release_keys'] = {a: cmds.keyframe(ctl+'.'+a, query=True, timeChange=True) for a in ['space','tx','ry']}
cmds.setKeyframe(ctl+'.ty', time=40, value=-9)
samples = {}
for mode in ('off', 'serial', 'parallel'):
    cmds.evaluationManager(mode=mode)
    cmds.currentTime(40)
    samples[mode] = snapshot()
report['evaluation_errors'] = {m: error(samples['off'],v) for m,v in samples.items()}
cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
scene_evaluation.apply()
cmds.select(clear=True)
cmds.playblast(format='image', completeFilename=str(base/'validation/flower_neutral.png'),
                compression='png', widthHeight=(1100, 1100), showOrnaments=False,
                viewer=False, frame=1, offScreen=True, forceOverwrite=True, percent=100)
(base/'validation/initial_checks_20261016.json').write_text(json.dumps(report, indent=2))
result = report
