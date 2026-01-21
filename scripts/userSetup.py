from importlib import reload
import maya.utils as mu
import maya.cmds as cmds

def vs_code_ports():
    # Abrir puertos para comunicación con VS Code
    if not cmds.commandPort(":4434", query=True):
        cmds.commandPort(name=":4434")
    if not cmds.commandPort("localhost:7001", query=True):
        cmds.commandPort(name="localhost:7001")

def init_auto_rig_UI():
    try:
        from ui import auto_rig_UI
        reload(auto_rig_UI) 
        auto_rig_UI.create_custom_menu()
        
    except Exception as e:
        cmds.warning(f"Could not load auto_rig_UI: {e}")
    vs_code_ports()

mu.executeDeferred(init_auto_rig_UI)