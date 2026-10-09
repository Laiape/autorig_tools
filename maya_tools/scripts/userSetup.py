from importlib import reload
import maya.utils as mu
import maya.cmds as cmds
import sys
import os
import subprocess

def vs_code_ports():

    try:
        if not cmds.commandPort(":4434", query=True):
            cmds.commandPort(name=":4434")
        if not cmds.commandPort("localhost:7001", query=True):
            cmds.commandPort(name="localhost:7001", sourceType="mel", echoOutput=True)
        if not cmds.commandPort(":7002", query=True):
            cmds.commandPort(name=":7002", sourceType="python", echoOutput=True)
    except Exception as e:
        cmds.warning(f"Error al abrir puertos para VS Code: {e}")

def install_numpy():
    """
    Verifica si numpy está instalado. Si no, lo instala usando mayapy.
    """
    try:
        import numpy
        version = numpy.__version__
        return 
    except ImportError:
        print("--- Numpy no detectado. Iniciando proceso de instalación... ---")
    mayapy_exe = os.path.join(os.path.dirname(sys.executable), "mayapy.exe")
    
    if not os.path.exists(mayapy_exe):
        cmds.error("No se encontró mayapy.exe. Verifica tu instalación de Maya.")
        return
    command = [mayapy_exe, "-m", "pip", "install", "--user", "numpy"]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            print(stdout.decode())
            cmds.confirmDialog(
                title='Éxito', 
                message='Numpy se instaló correctamente.\n\nIMPORTANTE: Debes reiniciar Maya para que los cambios surtan efecto.', 
                button=['Entendido']
            )
        else:
            print(stderr.decode())
            cmds.error("Error durante la instalación de Pip. Revisa el Script Editor.")

    except Exception as e:
        cmds.error(f"Fallo crítico en el proceso de instalación: {e}")

def init_proxy_locator():
    try:
        if not cmds.pluginInfo("proxy_locator", q=True, loaded=True):
            # userSetup.py no tiene __file__ fiable: buscar en sys.path,
            # que ya incluye <repo>/maya_tools/scripts via self_module.mod
            for path in sys.path:
                plugin_path = os.path.join(path, "tools", "proxy_locator.py")
                if os.path.isfile(plugin_path):
                    cmds.loadPlugin(plugin_path)
                    break
            else:
                cmds.warning("proxy_locator.py no encontrado en sys.path")
    except Exception as e:
        cmds.warning(f"No se ha podido cargar proxy_locator: {e}")


def init_auto_rig_UI(_open_ports=vs_code_ports):
    # Maya ejecuta todos los userSetup en __main__; imports locales evitan
    # que otro script de arranque cambie nuestras referencias diferidas.
    from importlib import reload
    import maya.cmds as cmds
    import traceback

    if cmds.about(batch=True):
        return

    try:
        from maya_tools.scripts.ui import auto_rig_UI
        reload(auto_rig_UI) 
        auto_rig_UI.create_custom_menu()
    except Exception as e:
        traceback.print_exc()
        cmds.warning(f"No se ha podido cargar el menú AutoRig: {e}")

    try:
        from maya_tools.scripts.ui import auto_rig_shelf
        reload(auto_rig_shelf)
        auto_rig_shelf.create_shelf()
    except Exception as e:
        traceback.print_exc()
        cmds.warning(f"No se ha podido cargar el shelf AutoRig: {e}")
    _open_ports()
    #install_numpy()
    #init_proxy_locator()
    #init_mcp_listener()


def init_mcp_listener():
    try:
        import importlib
        importlib.invalidate_caches()  # los finders pueden estar frios en pleno arranque
        from tools import mcp_listener
        mcp_listener.start()
    except Exception as e:
        import traceback
        traceback.print_exc()
        cmds.warning(f"No se ha podido iniciar el listener MCP: {e}")

def _schedule_auto_rig_ui(_initialize=init_auto_rig_UI):
    import maya.cmds as cmds
    if not cmds.about(batch=True):
        # Esperar también a la construcción del menú principal y los shelves.
        cmds.evalDeferred(_initialize, lowestPriority=True)


mu.executeDeferred(_schedule_auto_rig_ui)
