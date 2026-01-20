# Python libraries import
import glob
import os
import json
from importlib import reload
import re
import pathlib

from numpy import character
import maya.api.OpenMaya as om

# Maya commands import
from maya.api import OpenMaya as om
import json

import maya.cmds as cmds
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except:
    from PySide2 import QtWidgets, QtCore, QtGui

from utils import guides_manager
from ui import auto_rig_UI

from utils import data_manager
from utils import rig_manager

reload(data_manager)
reload(rig_manager)
reload(guides_manager)
reload(auto_rig_UI)
reload(om)
reload(glob)
reload(pathlib)


# Body mechanics
from biped.autorig import arm_module_de_boor as arm_module
from biped.autorig import spine_module as biped_spine_module
from biped.autorig import clavicle_module
from biped.autorig import leg_module_de_boor as leg_module
from biped.autorig import neck_module_de_boor as neck_module
from biped.autorig import fingers_module

from quadruped.autorig import tail_module
from quadruped.autorig import limb_module
from quadruped.autorig import spine_module as quad_spine_module
from quadruped.autorig import neck_module as neck_module_quad

# Facial
from biped.autorig import eyebrow_module
from biped.autorig import eyelid_module
from biped.autorig import ear_module
from biped.autorig import nose_module
from biped.autorig import jaw_module
from biped.autorig import cheekbone_module
from biped.autorig import tongue_module
from biped.autorig import teeth_module


reload(arm_module)
reload(biped_spine_module)
reload(clavicle_module)
reload(leg_module)
reload(neck_module)
reload(fingers_module)
reload(tail_module)
reload(limb_module)
reload(quad_spine_module)
reload(neck_module_quad)
reload(eyebrow_module)
reload(eyelid_module)
reload(ear_module)
reload(nose_module)
reload(jaw_module)
reload(cheekbone_module)
reload(tongue_module)
reload(teeth_module)


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

def get_main_assembly_nodes():

    """
    Retrieves all main assembly nodes in the current Maya scene, excluding cameras.
    Returns:
        list: A list of main assembly node names.
    """

    all_assemblies = cmds.ls(assemblies=True)
    
    scene_assemblies = [
        obj for obj in all_assemblies 
        if not cmds.listRelatives(obj, type='camera')
    ]

    return scene_assemblies
    

def get_character_name_from_scene(avoid=None):
    """
    Extracts the character name from the current Maya scene filename.
    Returns:
        str: The character name extracted from the scene filename.
    """

    char_name = "asset"
    
    scene_assemblies = get_main_assembly_nodes()

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

    cmds.file(new=True, force=True)
    
    scene_name = f"CHAR_{character_name}_v001.ma"
    cmds.file(rename=scene_name)
    
    om.MGlobal.displayInfo("Nueva escena creada y renombrada como: {}".format(scene_name))

    scene_to_open, scene_assemblies = open_model_scene(character_name)
    
    if not scene_to_open:
        cmds.warning("No se encontraron mallas para importar en la carpeta de {}".format(character_name))

    return character_name, scene_assemblies


def open_model_scene(character_name):

    """
    Busca el archivo .ma o .mb en la carpeta 'models' del asset actual y lo abre.
    """

    script_path = os.path.realpath(__file__)
    root_github = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path))))
    models_dir = os.path.join(root_github, "autorig_tools", "assets", character_name, "models")
    models_dir = os.path.normpath(models_dir)

    if not os.path.exists(models_dir):
        cmds.error(f"No se encontró la carpeta de modelos en: {models_dir}")
        return

    files = [f for f in os.listdir(models_dir) if f.endswith(".ma") or f.endswith(".mb")]
    
    if not files:
        cmds.warning(f"No se encontraron escenas de Maya en {models_dir}")
        return

    files.sort()
    scene_to_open = os.path.join(models_dir, files[-1]).replace("\\", "/")

    # 4. Abrir la escena encontrada
    try:
        cmds.file(scene_to_open, open=True, force=True)
    except Exception as e:
        cmds.error(f"No se pudo abrir la escena: {e}")

    scene_assemblies = get_main_assembly_nodes()

    return scene_to_open, scene_assemblies


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

def get_character_data(character_name):
    """
    Carga la data completa del personaje una sola vez.
    Retorna un diccionario con todas las guías existentes.
    """
    full_data = guides_manager.read_guides_info(character_name, return_all=True) 
    return full_data if full_data else {}

def define_biped_or_quadruped(guides_data):
    """
    Determina si es biped o quadruped basándose en qué guías existen en el diccionario.
    """
    if not guides_data:
        return "biped"

    if "L_frontLegHip_JNT" in guides_data or "R_frontLegHip_JNT" in guides_data or "L_backLegHip_JNT" in guides_data or "R_backLegHip_JNT" in guides_data:
        return "quadruped"
    
    return "biped"

def build_rig(character_name):
    """
    Función principal de construcción del Rig.
    Optimizado para leer el JSON una sola vez.
    """
    reload(guides_manager)
    
    all_guides_data = guides_manager.read_guides_info(character_name)
    
    if not all_guides_data:
        print(f"[ERROR] No se pudieron cargar las guías para: {character_name}")
        return 

    def check(guide_name):
        return guide_name in all_guides_data

    rig_type = define_biped_or_quadruped(all_guides_data)
    print(f"--- Iniciando Build: {character_name} (Tipo: {rig_type.upper()}) ---")

    # =========================================================================
    # BUILD: BODY
    # =========================================================================

    # --- Spine ---
    if check("C_spine00_JNT"):
        if rig_type == "biped":
            reload(biped_spine_module)
            biped_spine_module.SpineModule().make("C")
        elif rig_type == "quadruped":
            reload(quad_spine_module)
            quad_spine_module.SpineModule().make("C")

    # --- Neck ---
    if check("C_neck00_JNT"):
        if rig_type == "biped":
            reload(neck_module)
            neck_module.NeckModule().make("C")
        elif rig_type == "quadruped":
            reload(neck_module_quad)
            neck_module_quad.NeckModule().make("C")

    # --- Legs (Solo Biped) ---
    if rig_type == "biped":
        if check("L_hip_JNT") and check("R_hip_JNT"):
            reload(leg_module)
            leg_module.LegModule().make("L")
            leg_module.LegModule().make("R")

    # --- Limbs (Solo Quadruped) ---
    if rig_type == "quadruped":
        # Patas Delanteras
        if check("L_frontLeg_JNT") and check("R_frontLeg_JNT"):
            reload(limb_module)
            limb_module.LimbModule().make("L")
            limb_module.LimbModule().make("R")
        
        # Patas Traseras
        if check("L_backLeg_JNT") and check("R_backLeg_JNT"):
            reload(limb_module)
            limb_module.LimbModule().make("L") 
            limb_module.LimbModule().make("R")

    # --- Arms / Clavicles ---
    if check("L_clavicle_JNT") and check("R_clavicle_JNT"):
        reload(clavicle_module)
        clavicle_module.ClavicleModule().make("L")
        clavicle_module.ClavicleModule().make("R") 

    if check("L_shoulder_JNT") and check("R_shoulder_JNT"):
        reload(arm_module)
        arm_module.ArmModule().make("L")
        arm_module.ArmModule().make("R")
    
    if check("L_thumb00_JNT") and check("R_thumb00_JNT"):
        reload(fingers_module)
        fingers_module.FingersModule().make("L")
        fingers_module.FingersModule().make("R")

    # --- Tail ---
    if check("C_tail00_JNT"):
        reload(tail_module)
        tail_module.TailModule().make("C")

    # =========================================================================
    # BUILD: FACIAL
    # =========================================================================
    
    if check("C_jaw_JNT"):
        reload(jaw_module)
        jaw_module.JawModule().make("C")
    
    if check("L_eyebrow_JNT") and check("R_eyebrow_JNT"):
        reload(eyebrow_module)
        eyebrow_module.EyebrowModule().make("L")
        eyebrow_module.EyebrowModule().make("R")
    
    if check("L_eye_JNT") and check("R_eye_JNT"):
        reload(eyelid_module)
        eyelid_module.EyelidModule().make("L")
        eyelid_module.EyelidModule().make("R")

    if check("C_tongue00_JNT"):
        reload(tongue_module)
        tongue_module.TongueModule().make("C")

    if check("C_upperTeeth_JNT"):
        reload(teeth_module)
        teeth_module.TeethModule().make("C")

    if check("L_ear00_JNT") and check("R_ear00_JNT"):
        reload(ear_module)
        ear_module.EarModule().make("L")
        ear_module.EarModule().make("R")

    if check("C_nose_JNT"):
        reload(nose_module)
        nose_module.NoseModule().make("L")
        nose_module.NoseModule().make("R")

    if check("L_cheekbone_JNT") and check("R_cheekbone_JNT"):
        reload(cheekbone_module)
        cheekbone_module.CheekboneModule().make("L")
        cheekbone_module.CheekboneModule().make("R")