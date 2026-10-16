from pathlib import Path
import maya.cmds as cmds
path=Path('C:/proyectos/auto-rig/recovery/chihuahua_guides_orientation_before_20261016_v001.mb')
if path.exists():raise RuntimeError('Backup path already exists')
path.parent.mkdir(parents=True,exist_ok=True)
old=cmds.file(q=True,sn=True);modified=cmds.file(q=True,modified=True);selection=cmds.ls(sl=True,long=True) or []
cmds.file(str(path),exportAll=True,type='mayaBinary',options='v=0;')
cmds.file(modified=modified)
result={'backup':str(path),'bytes':path.stat().st_size,'original_scene':old,'current_scene':cmds.file(q=True,sn=True),'selection_preserved':selection==(cmds.ls(sl=True,long=True) or [])}
