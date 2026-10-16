"""Read artist state or close only the explicitly owned solver trial Maya."""
import json
import os
from pathlib import Path
from maya import cmds

FOLDER = Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001')
action = globals().get('TRIAL_ARGUMENTS', {}).get('action', 'artist')
if action == 'artist':
    assert os.getpid() == 23404
    before = json.loads((FOLDER / 'artist_snapshot.json').read_text())['artist']
    after = {'scene': cmds.file(q=True, sn=True), 'modified': cmds.file(q=True, modified=True),
             'frame': cmds.currentTime(q=True), 'selection': cmds.ls(sl=True, long=True)}
    result = {'pid': os.getpid(), 'before': before, 'after': after,
              'same_recorded_state': before == after, 'read_only': True}
else:
    settings = json.loads((FOLDER / 'launch.json').read_text())
    assert os.getpid() == settings['pid'] == 31084
    assert (FOLDER / 'summary.json').exists()
    result = {'pid': os.getpid(), 'quit_requested': True}
    cmds.evalDeferred("__import__('maya.cmds', fromlist=['']).quit(force=True)", lowestPriority=True)
