import maya.utils as mu
import maya.cmds as cmds

if not cmds.commandPort(":4434", query=True):
    cmds.commandPort(name=":4434")
if not cmds.commandPort("localhost:7001", query=True):
    cmds.commandPort(name="localhost:7001")

mu.executeDeferred("from scripts.ui import option_menu; option_menu.LaiaUI.make_ui()")