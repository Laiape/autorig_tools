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
            cmds.loadPlugin(r"C:/GIT/autorig_tools/scripts/tools/proxy_locator.py")
    except Exception as e:
        cmds.warning(f"No se ha podido cargar proxy_locator: {e}")


def init_auto_rig_UI():
    try:
        from ui import auto_rig_UI
        reload(auto_rig_UI) 
        auto_rig_UI.create_custom_menu()
        
    except Exception as e:
        cmds.warning(f"No se ha podido cargar auto_rig_UI: {e}")
    vs_code_ports()
    install_numpy()
    init_proxy_locator()

mu.executeDeferred(init_auto_rig_UI)