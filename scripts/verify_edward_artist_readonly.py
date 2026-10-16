"""Read-only final state receipt; never restore stale artist UI values."""
import os
from maya import cmds
from maya_tools.scripts.utils import scene_evaluation
assert os.getpid()==35132,'This receipt belongs to the original artist Maya only.'
result={'pid':os.getpid(),'scene':cmds.file(query=True,sceneName=True),
        'modified':cmds.file(query=True,modified=True),'frame':cmds.currentTime(query=True),
        'selection':cmds.ls(selection=True,long=True) or [],'evaluation':scene_evaluation.capture(),
        'node_count':len(cmds.ls()),'read_only':True,
        'note':'User UI/frame/selection may have changed since the snapshot; no stale values are forced back.'}
