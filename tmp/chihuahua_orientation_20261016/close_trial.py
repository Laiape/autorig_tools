import os
import maya.cmds as cmds
assert os.getpid() == 46680
result = {'closing_owned_trial': os.getpid()}
cmds.evalDeferred('import maya.cmds as cmds; cmds.quit(force=True)')
