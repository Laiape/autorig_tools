from pathlib import Path
from maya import cmds
path='C:/proyectos/auto-rig/recovery/Edward_eyelids_rotation_fixed_20261016_v001.mb'
if Path(path).exists():raise RuntimeError('Corrected snapshot already exists')
scene=cmds.file(q=True,sn=True);modified=cmds.file(q=True,modified=True);selection=cmds.ls(sl=True,long=True)
try:
    cmds.file(rename=path);cmds.file(save=True,type='mayaBinary',force=True)
finally:
    cmds.file(rename=scene);cmds.file(modified=modified)
    cmds.select(selection,r=True) if selection else cmds.select(clear=True)
result={'saved':path,'artist_filename':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'bytes':Path(path).stat().st_size}
