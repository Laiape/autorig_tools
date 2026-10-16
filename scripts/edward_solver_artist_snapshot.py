"""Read and preserve the artist scene before isolated solver comparisons."""
import json
import os
from pathlib import Path
from maya import cmds

assert os.getpid() == 23404
FOLDER = Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001')
FOLDER.mkdir(parents=True, exist_ok=True)
before = {'scene': cmds.file(q=True, sn=True), 'modified': cmds.file(q=True, modified=True),
          'frame': cmds.currentTime(q=True), 'selection': cmds.ls(sl=True, long=True)}
keys = {}
for node in cmds.ls('*_CTL', type='transform'):
    for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
        plug = node + '.' + attr
        times = cmds.keyframe(plug, q=True, timeChange=True) or []
        if times:
            keys[plug] = {'times': times, 'values': cmds.keyframe(plug, q=True, valueChange=True)}
target = FOLDER / 'Edward_artist_before_solver_trial.ma'
assert not target.exists()
cmds.file(str(target), exportAll=True, type='mayaAscii', force=False, options='v=0;', preserveReferences=True)
after = {'scene': cmds.file(q=True, sn=True), 'modified': cmds.file(q=True, modified=True),
         'frame': cmds.currentTime(q=True), 'selection': cmds.ls(sl=True, long=True)}
assert before == after
data = {'artist': before, 'snapshot': str(target), 'animation': keys,
        'ik_handles': cmds.ls(type='ikHandle'), 'skins': len(cmds.ls(type='skinCluster'))}
(FOLDER / 'artist_snapshot.json').write_text(json.dumps(data, indent=2))
result = {'snapshot': str(target), 'artist_unchanged': True, 'animated_control_channels': len(keys), 'skins': data['skins']}
