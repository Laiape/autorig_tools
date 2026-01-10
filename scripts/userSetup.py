import sys
import maya.utils as mu
import maya.cmds as cmds

# --- TUS PUERTOS VS CODE (Igual que antes) ---
def vs_code_ports():
    if not cmds.commandPort(":4434", query=True):
        cmds.commandPort(name=":4434")
    if not cmds.commandPort("localhost:7001", query=True):
        cmds.commandPort(name="localhost:7001")

def init_auto_rig_UI():
    try:
        # 1. ELIMINAR MÓDULOS DE LA MEMORIA
        # Buscamos todos los módulos cargados que empiecen por tu paquete "biped"
        # y los borramos de sys.modules. Esto obliga a Python a leerlos 
        # desde el disco de nuevo como si fuera la primera vez.
        modules_to_delete = [key for key in sys.modules.keys() if key.startswith("biped")]
        
        for module in modules_to_delete:
            del sys.modules[module]
            print(f"Removed module: {module}")

        # 2. IMPORTAR DE CERO
        # Ahora hacemos el import limpio. No hace falta reload porque ya no existen en memoria.
        from biped.ui import auto_rig_UI
        
        # 3. CREAR MENÚ
        auto_rig_UI.create_custom_menu()
        print("Auto Rig UI initialized successfully.")

    except Exception as e:
        cmds.warning("Could not load auto_rig_UI: {}".format(e))
        import traceback
        traceback.print_exc() # Esto te ayudará a ver errores más detallados

# Ejecución
vs_code_ports()
mu.executeDeferred(init_auto_rig_UI)