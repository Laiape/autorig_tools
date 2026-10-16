from pathlib import Path
from maya import cmds
path=Path('C:/proyectos/auto-rig/recovery/eyelids_large_roll_before_20261016_v001.mb')
if path.exists():raise RuntimeError('Snapshot exists')
original=cmds.file(q=True,sn=True);modified=cmds.file(q=True,modified=True)
selection=cmds.ls(sl=True,long=True)
try:
    cmds.file(rename=str(path));cmds.file(save=True,type='mayaBinary',force=True)
finally:
    cmds.file(rename=original);cmds.file(modified=modified)
    cmds.select(selection,r=True) if selection else cmds.select(clear=True)
result={'snapshot':str(path),'controls':{ctl:cmds.getAttr(ctl+'.rotate') for ctl in cmds.ls('*eyelid*CTL')}}
