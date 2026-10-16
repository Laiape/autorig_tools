from pathlib import Path
from maya import cmds
path = Path('C:/proyectos/auto-rig/recovery/Edward_eyelids_fixed_20261016_v001.mb')
if path.exists():
    raise RuntimeError('Fixed scene copy already exists')
original = cmds.file(q=True, sn=True)
modified = cmds.file(q=True, modified=True)
try:
    cmds.file(rename=str(path))
    cmds.file(save=True, type='mayaBinary', force=True)
finally:
    cmds.file(rename=original)
    cmds.file(modified=modified)
result = {'fixed_scene': str(path), 'bytes': path.stat().st_size}
