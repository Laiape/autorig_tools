from pathlib import Path
from maya import cmds
path='C:/proyectos/auto-rig/recovery/Edward_eyelids_soft_ends_20261016_v001.mb'
if Path(path).exists():raise RuntimeError('Corrected copy already exists')
scene=cmds.file(q=True,sn=True);selection=cmds.ls(sl=True,long=True)
cmds.file(path,exportAll=True,type='mayaBinary',preserveReferences=True,force=True)
cmds.select(selection,r=True) if selection else cmds.select(clear=True)
assert cmds.file(q=True,sn=True)==scene
result={'saved':path,'artist_filename':scene,'bytes':Path(path).stat().st_size}
