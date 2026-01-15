# Python libraries import
import glob
import os
import json
from importlib import reload
import re
import pathlib

# Maya commands import
from maya.api import OpenMaya as om
import json

import maya.cmds as cmds
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except:
    from PySide2 import QtWidgets, QtCore, QtGui
# Ui import
from biped.ui import auto_rig_UI
# Utils import
from biped.utils import data_manager
from biped.utils import rig_manager

reload(data_manager)
reload(rig_manager)
reload(auto_rig_UI)
reload(om)
reload(glob)
reload(pathlib)

def import_rig_properties_from_json(self):

    """
    Imports rig properties from a JSON file and populates the UI elements accordingly.
    Args:
    """
    character_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")

    try:
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        path = os.path.join(relative_path, "assets")
        character_path = os.path.join(path, character_name)
        TEMPLATE_PATH = os.path.join(character_path, "build")
        file_path = rig_manager.get_latest_version(TEMPLATE_PATH, character_name)
    
    except:
        relative_path = r"H:\GIT\biped_autorig"
        path = os.path.join(relative_path, "assets")
        character_path = os.path.join(path, character_name)
        TEMPLATE_PATH = os.path.join(character_path, "build")
        file_path = rig_manager.get_latest_version(TEMPLATE_PATH, character_name)

    with open(file_path, 'r') as f:
            data = json.load(f)

    rig_attributes = data.get("rig_attributes", {})

    for section, attrs in rig_attributes.items():
        for key, value in attrs.items():
            # Safely set widget values if they exist
            widget = getattr(self, key, None)
            if widget:
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(value)
                elif hasattr(widget, "setValue"):
                    widget.setValue(value)


def get_latest_version(folder):
    """
    Get the latest version number of a file in a given folder.
    Args:
        folder (str): Full path to the folder to search in.
        base_name (str): The base name of the file (without version and extension).
    Returns:
        int: The latest version number, or None if no versions are found or folder is invalid.
    """

    folder = pathlib.Path(folder)

    if not folder.is_dir():
        return None
    
    # Get all files (any extension)
    files = [f for f in folder.glob("*") if f.is_file()]

    if not files:
        om.MGlobal.displayInfo("No files found in the specified folder.")
        return None
    else:
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        return latest_file

def create_new_scene():

    """
    Creates a new Maya scene.
    """

    cmds.file(new=True, force=True)
    

def get_character_name_from_scene(avoid=None):
    """
    Extracts the character name from the current Maya scene filename.
    Returns:
        str: The character name extracted from the scene filename.
    """

    char_name = "asset"
    
    all_assemblies = cmds.ls(assemblies=True)
    
    scene_assemblies = [
        obj for obj in all_assemblies 
        if not cmds.listRelatives(obj, type='camera')
    ]

    for obj in scene_assemblies:
        
        if avoid and obj == avoid:
            continue
        
        char_name = obj
        break
    print(f"Final character name: {char_name}")
    return char_name

def get_character_name_from_build():

    """
    Extracts the character name from the build file name in the current Maya scene.
    Returns:
        str: The character name extracted from the build file name.
    """

    char_name = "asset"

    char_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")

    return char_name

def get_next_version_name(folder):

    """
    Get the next version name for a file in a given folder.
    Args:
        folder (str): The folder to search in.
        base_name (str): The base name of the file.
    Returns:
        str: The next version name.
    """
    latest_version  = get_latest_version(folder=folder)
    base_name = latest_version.stem.split("_v")[0].split("/")[-1]
    next_version = 1 if base_name is None else base_name + 1
    ext = latest_version.split(".")[-1]
    
    return f"{base_name}_v{next_version:03d}.{ext}"

def create_assets_folders(asset_name):

    """
    Create necessary asset folders if they do not exist.
    """

    # Set up main asset folder and subfolders
    complete_path = os.path.realpath(__file__)
    sep_token = os.sep + "scripts"
    if sep_token in complete_path:
        relative_path = complete_path.split(sep_token)[0]
    else:
        # fallback to parent directory if "scripts" is not found
        relative_path = os.path.dirname(os.path.dirname(complete_path))

    base_path = os.path.join(relative_path, "assets")
    main_folder = os.path.join(base_path, asset_name)
    os.makedirs(main_folder, exist_ok=True)

    subfolders = ["models", "build", "cache", "curves", "guides", "skin_clusters"]

    for subfolder in subfolders:
        folder_path = os.path.join(main_folder, subfolder)
        os.makedirs(folder_path, exist_ok=True)

import maya.cmds as cmds
import os

def create_new_asset():
    """
    Muestra una ventana para ingresar el nombre del asset y crea la estructura de carpetas.
    """
    window_id = "createAssetWindow"
    
    # 1. Limpiar ventana si ya existe
    if cmds.window(window_id, exists=True):
        cmds.deleteUI(window_id)
        
    # 2. Crear ventana
    cmds.window(window_id, title="Create New Asset", widthHeight=(300, 100), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnOffset=['both', 10])
    
    cmds.text(label="Enter Asset Name:", align='left', height=25)
    asset_name_field = cmds.textField(placeholderText="e.g. character_laia")
    
    # Botón que ejecuta la lógica interna
    cmds.button(label="Create Folders", height=30, 
                command=lambda x: execute_folder_creation(cmds.textField(asset_name_field, q=True, text=True), window_id))
    
    cmds.showWindow(window_id)

    return asset_name_field

def execute_folder_creation(asset_name, window_id):
    """
    Lógica de sistema de archivos para crear las carpetas.
    """
    # Validación básica
    if not asset_name or asset_name.strip() == "":
        cmds.warning("Asset name cannot be empty!")
        return

    # Limpiar el nombre de posibles espacios
    asset_name = asset_name.strip()

    # --- Lógica de Rutas ---
    complete_path = os.path.realpath(__file__)
    sep_token = os.sep + "scripts"
    
    if sep_token in complete_path:
        relative_path = complete_path.split(sep_token)[0]
    else:
        relative_path = os.path.dirname(os.path.dirname(complete_path))

    # Carpeta base 'assets'
    base_path = os.path.join(relative_path, "assets")
    main_folder = os.path.join(base_path, asset_name)
    
    # Crear carpeta principal y subcarpetas
    subfolders = ["models", "build", "cache", "curves", "guides", "skin_clusters"]
    
    try:
        os.makedirs(main_folder, exist_ok=True)
        for subfolder in subfolders:
            folder_path = os.path.join(main_folder, subfolder)
            os.makedirs(folder_path, exist_ok=True)
            
        cmds.deleteUI(window_id)
        cmds.confirmDialog(title='Success', message=f'Folder structure created for: {asset_name}', button=['OK'])
        print(f"Asset created at: {main_folder}")
        
    except Exception as e:
        cmds.error(f"Failed to create folders: {e}")

def prepare_rig_scene():
    """
    1. Crea una nueva escena.
    2. Renombra la escena a CHAR_"character_name"_v001.
    3. Importa las mallas del asset actual.
    4. Ejecuta el proceso de construcción del Rig.
    """
    
    character_name = cmds.promptDialog(
                title="INPUT CHARACTER NAME",
                message="INSERT CHARACTER NAME",
                button=["OK", "Cancel"],
                defaultButton="OK",
                cancelButton="Cancel",
                dismissString="Cancel")
    
    if character_name == "Cancel":
        om.MGlobal.displayInfo("Proceso cancelado por el usuario.")
        return
    
    character_name = cmds.promptDialog(query=True, text=True)

    # 1. Nueva escena forzada
    cmds.file(new=True, force=True)
    
    # 2. Definir nombre y renombrar escena
    # Formato: C_NombrePersonaje_v001
    scene_name = f"CHAR_{character_name}_v001.ma"
    cmds.file(rename=scene_name)
    
    om.MGlobal.displayInfo("Nueva escena creada y renombrada como: {}".format(scene_name))

    # 3. Importar Meshes
    # Usamos tu función existente
    imported_files = import_meshes(character_name)
    
    if not imported_files:
        cmds.warning("No se encontraron mallas para importar en la carpeta de {}".format(character_name))
    else:
        om.MGlobal.displayInfo("Mallas importadas correctamente en {}".format(scene_name))

    return character_name, imported_files



def import_meshes(character_name=None):
    """
    Importa meshes y devuelve una lista de los transforms raíz (main transforms)
    importados en la escena.
    """
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, character_name)
    models_path = os.path.join(character_path, "models")

    mesh_files = glob.glob(os.path.join(models_path, "*.mb")) + glob.glob(os.path.join(models_path, "*.ma"))
    
    imported_main_transforms = []

    for mesh_file in mesh_files:
        try:
            # returnNewNodes=True devuelve todos los nodos creados por la importación
            new_nodes = cmds.file(
                mesh_file, 
                i=True, 
                type="mayaBinary" if mesh_file.endswith(".mb") else "mayaAscii", 
                ignoreVersion=True, 
                mergeNamespacesOnClash=False, 
                namespace=":",
                returnNewNodes=True
            )

            if new_nodes:
                # Filtramos para obtener solo nodos de tipo 'transform' que sean RAÍZ (sin padre)
                # Esto evita que devuelva shapes, joints o transforms hijos.
                roots = [
                    node for node in cmds.ls(new_nodes, type="transform") 
                    if not cmds.listRelatives(node, parent=True)
                ]
                imported_main_transforms.extend(roots)

        except Exception as e:
            import maya.api.OpenMaya as om
            om.MGlobal.displayError(f"Failed to import {os.path.basename(mesh_file)}: {str(e)}")

    # Devolvemos la lista de transforms principales (ej: ['maui_body_GEO', 'geo_GRP', etc.])
    return imported_main_transforms


def import_meshes_for_guides(character_name):

    """
    Import meshes when guides are imported to.
    """

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, character_name)
    models_path = os.path.join(character_path, "models")

    mesh_files = glob.glob(os.path.join(models_path, "*.mb")) + glob.glob(os.path.join(models_path, "*.ma"))

    for mesh_file in mesh_files:
        try:
            cmds.file(mesh_file, i=True, type="mayaBinary" if mesh_file.endswith(".mb") else "mayaAscii", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=":")
            om.MGlobal.displayInfo(f"Imported mesh: {os.path.basename(mesh_file)}")
        except Exception as e:
            om.MGlobal.displayError(f"Failed to import {os.path.basename(mesh_file)}: {str(e)}")

    return mesh_files
