from pathlib import Path
import maya.cmds as cmds
path='C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016/revision_preview.png'
cmds.playblast(frame=cmds.currentTime(q=True),format='image',compression='png',completeFilename=path,
               forceOverwrite=True,viewer=False,showOrnaments=False,offScreen=True,widthHeight=(1400,900),percent=100)
result=dict(path=path,exists=Path(path).exists())
