from maya import cmds
from ngSkinTools2.ui.mainwindow import DOCK_NAME
result={'exists':cmds.workspaceControl(DOCK_NAME,q=True,exists=True),'visible':cmds.workspaceControl(DOCK_NAME,q=True,visible=True)}
