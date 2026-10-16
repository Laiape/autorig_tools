from pathlib import Path
from importlib import reload
from maya import cmds
from maya_tools.scripts.tools import eyelid_rotation
action=TRIAL_ARGUMENTS.get('action','snapshot')
if action in ('snapshot','save'):
    filename='eyelids_before_roll_20261016_v001.mb' if action=='snapshot' else 'Edward_eyelids_roll_20261016_v001.mb'
    path=Path('C:/proyectos/auto-rig/recovery')/filename
    if path.exists():raise RuntimeError('Snapshot exists')
    original=cmds.file(q=True,sn=True)
    modified=cmds.file(q=True,modified=True)
    selection=cmds.ls(sl=True,long=True)
    try:
        cmds.file(rename=str(path));cmds.file(save=True,type='mayaBinary',force=True)
    finally:
        cmds.file(rename=original);cmds.file(modified=modified)
        cmds.select(selection,r=True) if selection else cmds.select(clear=True)
    result={'scene':str(path),'bytes':path.stat().st_size}
elif action=='install':
    reload(eyelid_rotation)
    cmds.undoInfo(openChunk=True,chunkName='Whole eyelid Z rotation')
    try:
        changed=[]
        for prefix in ('L','R'):changed+=eyelid_rotation.install(prefix)
    except Exception:
        cmds.undoInfo(closeChunk=True);cmds.undo();raise
    else:
        cmds.undoInfo(closeChunk=True)
    result={'changed':changed}
