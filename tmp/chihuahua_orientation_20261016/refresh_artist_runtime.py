from importlib import reload
import maya.cmds as cmds
from maya_tools.scripts.utils import create_rig
before = cmds.file(query=True, sceneName=True)
modified = cmds.file(query=True, modified=True)
selection = cmds.ls(selection=True, long=True)
reload(create_rig)
assert cmds.file(query=True, sceneName=True) == before
assert cmds.file(query=True, modified=True) == modified
assert cmds.ls(selection=True, long=True) == selection
result = {'runtime': create_rig.__file__, 'artist_scene_preserved': True}
