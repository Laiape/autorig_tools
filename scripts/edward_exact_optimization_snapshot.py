"""Snapshot current artist data without opening/replacing the live scene."""
import hashlib
import json
import os
from pathlib import Path
import time
from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles
from maya_tools.scripts.utils import scene_evaluation

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
FOLDER.mkdir(parents=True, exist_ok=True)
path = FOLDER / 'Edward_artist_baseline.mb'
if path.exists():
    raise ValueError('The immutable optimization snapshot already exists.')
before = {'scene': cmds.file(query=True, sceneName=True), 'modified': cmds.file(query=True, modified=True),
          'frame': cmds.currentTime(query=True), 'selection': cmds.ls(selection=True, long=True) or [],
          'evaluation': scene_evaluation.capture()}
if not cmds.objExists('Edward'):
    raise ValueError('The current scene does not contain Edward.')
started = time.perf_counter()
cmds.file(path.as_posix(), exportAll=True, type='mayaBinary', force=False, preserveReferences=True)
after = {'scene': cmds.file(query=True, sceneName=True), 'modified': cmds.file(query=True, modified=True),
         'frame': cmds.currentTime(query=True), 'selection': cmds.ls(selection=True, long=True) or [],
         'evaluation': scene_evaluation.capture()}
assert before == after, (before, after)
metadata = {'version': 1, 'pid': os.getpid(), 'artist_state': before, 'snapshot': str(path),
            'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'export_seconds': time.perf_counter()-started,
            'node_count': len(cmds.ls()), 'native_plugin_version': cmds.about(apiVersion=True),
            'time_unit': cmds.currentUnit(query=True, time=True), 'linear_unit': cmds.currentUnit(query=True, linear=True),
            'loaded_wrinkle_code': bifrost_wrinkles.__file__,
            'scene_saved_over_original': False, 'artist_state_unchanged': True,
            'contract': 'Preserve all authored rig behavior, deformation, clothing, wrinkles, targets, weights and controls. No approximate replacement.'}
(FOLDER / 'snapshot.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding='utf-8')
result = metadata
