import maya.utils as mu
import maya.cmds as cmds

if not cmds.commandPort(":4434", query=True):
    cmds.commandPort(name=":4434")
if not cmds.commandPort("localhost:7001", query=True):
    cmds.commandPort(name="localhost:7001")

<<<<<<< HEAD
mu.executeDeferred("from scripts.ui import option_menu; option_menu.LaiaUI.make_ui()")
=======
mu.executeDeferred("from scripts.ui import option_menu; option_menu.UI().make_ui()")
>>>>>>> 26b521417e4bbe8bce532416d58ab9636969d418
