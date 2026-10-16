import os
import maya.cmds as cmds
assert os.getpid()==43636
result={'closing_owned_trial':os.getpid()}
cmds.evalDeferred('import maya.cmds as cmds; cmds.quit(force=True)')
