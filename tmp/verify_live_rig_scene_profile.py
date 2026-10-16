import json
import time
from pathlib import Path
from maya import cmds
from maya_tools.scripts.utils import scene_evaluation

expected = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/utils/scene_evaluation.py')
assert Path(scene_evaluation.__file__).resolve() == expected.resolve()
before = {'scene': cmds.file(query=True, sceneName=True), 'modified': cmds.file(query=True, modified=True),
          'frame': cmds.currentTime(query=True), 'selection': cmds.ls(selection=True, long=True)}
prior = scene_evaluation.capture()
try:
    measured = []
    for _ in range(3):
        measured.append(scene_evaluation.apply())
    scene_evaluation.install_callbacks(apply_current=False)
except Exception:
    scene_evaluation.restore(prior)
    raise
after = {'scene': cmds.file(query=True, sceneName=True), 'modified': cmds.file(query=True, modified=True),
         'frame': cmds.currentTime(query=True), 'selection': cmds.ls(selection=True, long=True)}
assert before == after
result = {'loaded_helper': str(expected), 'before': before, 'artist_state_unchanged': before == after,
          'configuration_samples': measured, 'callbacks': len(scene_evaluation._CALLBACKS),
          'geometry_queries': False, 'scene_saved': False, 'root_marker_added_to_artist_scene': False}
