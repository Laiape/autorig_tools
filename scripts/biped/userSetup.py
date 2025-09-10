import maya.utils as mu
import maya.cmds as cmds

def vs_code_ports():
    if not cmds.commandPort(":4434", query=True):
        cmds.commandPort(name=":4434")
    if not cmds.commandPort("localhost:7001", query=True):
        cmds.commandPort(name="localhost:7001")

def init_auto_rig_UI():
    try:
        from ui import auto_rig_UI
        auto_rig_UI()
    except Exception as e:
        cmds.warning("Could not load auto_rig_UI: {}".format(e))
mu.executeDeferred(init_auto_rig_UI)
