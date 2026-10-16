from pathlib import Path
from maya import cmds
path = Path('C:/proyectos/auto-rig/recovery/eyelids_before_20261016_v001.mb')
if path.exists():
    raise RuntimeError('Snapshot already exists')
original = cmds.file(q=True, sn=True)
modified = cmds.file(q=True, modified=True)
try:
    cmds.file(rename=str(path))
    cmds.file(save=True, type='mayaBinary', force=True)
finally:
    cmds.file(rename=original)
    cmds.file(modified=modified)
result = {'snapshot': str(path), 'original': original, 'bytes': path.stat().st_size}
