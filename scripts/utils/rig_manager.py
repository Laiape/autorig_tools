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

def create_new_folder(path):

    """
    Creates a new folder if it does not exist.
    Args:
        path (str): The path of the folder to create.
    """

    if not os.path.exists(path):
        os.makedirs(path)
        return path
    else:
        return path
    
def asset_path(character_name, path):

    """
    Returns the asset path for a given character name.
    Args:
        character_name (str): The name of the character.
    Returns:
        str: The full path to the asset folder.
    """

    complete_path = os.path.realpath(__file__)
    sep_token = os.sep + "scripts"
    if sep_token in complete_path:
        relative_path = complete_path.split(sep_token)[0]
    else:
        relative_path = os.path.dirname(os.path.dirname(complete_path))

    base_path = os.path.join(relative_path, "assets")
    if character_name == "":
        return base_path
    if path == "":
        full_path = os.path.join(base_path, character_name)
    else:
        full_path = os.path.join(base_path, character_name, path)

    create_new_folder(full_path)
    return full_path

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
    avoid_always = "_GRP"
    
    scene_assemblies = get_main_assembly_nodes()

    for obj in scene_assemblies:
        if avoid and obj == avoid:
            continue
        
        char_name = obj

        if avoid_always in char_name:
            char_name = char_name.replace(avoid_always, "")
        
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

    main_folder = asset_path(asset_name, "")
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

    main_folder = asset_path(asset_name, asset_name)
    
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

    models_dir = asset_path(character_name, "models")

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

    models_path = asset_path(character_name, "models")

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


def build_rig(character_name):

    """
    Función principal de construcción del Rig.

    """
    reload(guides_manager)
    all_guides_data = guides_manager.read_guides_info(character_name)
    
    if not all_guides_data:
        print(f"[ERROR] No se pudieron cargar las guías para: {character_name}")
        return 

    def check(guide_name):
        return guide_name in all_guides_data
    
    # =========================================================================
    # LOAD RIG SETTINGS
    # =========================================================================
    rig_settings = build_rig_from_data(character_name)
    
    if not rig_settings:
        om.MGlobal.displayError(f"No se encontró configuración de atributos para: {character_name}")
        return

    # --- Acceso a los datos del diccionario ---
    rig_type            = rig_settings.get("Rig_Type", 0)
    spine_skinning_jnts = rig_settings.get("spine_skinning_jnts", 8)
    spine_controllers   = rig_settings.get("spine_controllers", 5)
    neck_skinning_jnts  = rig_settings.get("neck_skinning_jnts", 5)
    neck_controllers   = rig_settings.get("neck_controllers", 2)
    arm_skinning_jnts   = rig_settings.get("arm_skinning_jnts", 5)
    leg_skinning_jnts   = rig_settings.get("leg_skinning_jnts", 5)
    tail_skinning_jnts  = rig_settings.get("tail_skinning_jnts", 5)
    tail_controllers    = rig_settings.get("tail_controllers", 5)
    print(f"--- Iniciando Build: {character_name} (Tipo: {'Biped' if rig_type == 0 else 'Quadruped'}) ---")

    # CREATE MODULES BASED ON GUIDES
    # =========================================================================
    # BUILD: BODY
    # =========================================================================

    # --- Spine ---
    if check("C_spine00_JNT"):
        if rig_type == 0:
            reload(biped_spine_module)
            biped_spine_module.SpineModule().make("C", spine_skinning_jnts, spine_controllers)
        else:
            reload(quad_spine_module)
            quad_spine_module.SpineModule().make("C", spine_skinning_jnts, spine_controllers)

    # --- Neck ---
    if check("C_neck00_JNT"):
        if rig_type == 0:
            reload(neck_module)
            neck_module.NeckModule().make("C", neck_skinning_jnts, neck_controllers)
        else:
            reload(neck_module_quad)
            neck_module_quad.NeckModule().make("C", neck_skinning_jnts, neck_controllers)

    # --- Legs (Solo Biped) ---
    if rig_type == 0:
        if check("L_hip_JNT") and check("R_hip_JNT"):
            reload(leg_module)
            leg_module.LegModule().make("L", leg_skinning_jnts)
            leg_module.LegModule().make("R", leg_skinning_jnts)

    # --- Limbs (Solo Quadruped) ---
    if rig_type == 1:
        # Patas Delanteras
        if check("L_frontLeg_JNT") and check("R_frontLeg_JNT"):
            reload(limb_module)
            limb_module.LimbModule().make("L", leg_skinning_jnts)
            limb_module.LimbModule().make("R", leg_skinning_jnts)
        
        # Patas Traseras
        if check("L_backLeg_JNT") and check("R_backLeg_JNT"):
            reload(limb_module)
            limb_module.LimbModule().make("L", leg_skinning_jnts)
            limb_module.LimbModule().make("R", leg_skinning_jnts)

    # --- Arms / Clavicles ---
    if check("L_clavicle_JNT") and check("R_clavicle_JNT"):
        reload(clavicle_module)
        clavicle_module.ClavicleModule().make("L")
        clavicle_module.ClavicleModule().make("R") 

    if check("L_shoulder_JNT") and check("R_shoulder_JNT"):
        reload(arm_module)
        arm_module.ArmModule().make("L", arm_skinning_jnts)
        arm_module.ArmModule().make("R", arm_skinning_jnts)
    
    if check("L_thumb00_JNT") and check("R_thumb00_JNT"):
        reload(fingers_module)
        fingers_module.FingersModule().make("L")
        fingers_module.FingersModule().make("R")

    # --- Tail ---
    if check("C_tail00_JNT"):
        reload(tail_module)
        tail_module.TailModule().make("C", tail_skinning_jnts, tail_controllers)

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


def create_rig_settings(guides_transform, load=False):
    """
    Crea los atributos de configuración del Rig en el transform de las guías.
    """
    # Inicializamos valores por defecto
    defaults = {
        "Rig_Type": 0,
        "spine_skinning_jnts": 8, "spine_controllers": 5,
        "neck_skinning_jnts": 5, "neck_controllers": 2,
        "arm_skinning_jnts": 5, "leg_skinning_jnts": 5,
        "tail_skinning_jnts": 5, "tail_controllers": 5
    }

    # Si load es True, intentamos obtener los valores existentes
    if load:
        loaded_values = load_rig_settings(guides_transform)
        if loaded_values:
            defaults.update(loaded_values)

    rig_settings_config = {
        "Rig_Type": ("biped", "quadruped"),
        "spine_skinning_jnts": defaults["spine_skinning_jnts"],
        "spine_controllers": defaults["spine_controllers"],
        "neck_skinning_jnts": defaults["neck_skinning_jnts"],
        "neck_controllers": defaults["neck_controllers"],
        "arm_skinning_jnts": defaults["arm_skinning_jnts"],
        "leg_skinning_jnts": defaults["leg_skinning_jnts"],
        "tail_skinning_jnts": defaults["tail_skinning_jnts"],
        "tail_controllers": defaults["tail_controllers"]
    }

    if not cmds.objExists(guides_transform):
        om.MGlobal.displayError(f"No existe el objeto: {guides_transform}")
        return
    
    # Bloquear atributos básicos de transformación
    lock_attrs = ["translate", "rotate", "scale", "visibility"]
    for attr in lock_attrs:
        if attr == "visibility":
            cmds.setAttr(f"{guides_transform}.{attr}", lock=True, keyable=False, channelBox=False)
        else:
            for axis in ['X', 'Y', 'Z']:
                cmds.setAttr(f"{guides_transform}.{attr}{axis}", lock=True, keyable=False, channelBox=False)

    print("--- Creando/Actualizando ajustes del Rig ---")
    
    for key, value in rig_settings_config.items():
        attr_path = f"{guides_transform}.{key}"
        
        # Evitar duplicados
        if cmds.objExists(attr_path):
            continue

        # Crear separadores visuales (Header) si es necesario
        header_name = key.split('_')[0].upper()
        header_path = f"{guides_transform}.{header_name}_SEP" # Sufijo para evitar conflicto con el attr real
        if not cmds.objExists(header_path):
            cmds.addAttr(guides_transform, longName=f"{header_name}_SEP", niceName=f"--- {header_name} ---", attributeType='enum', enumName="-", keyable=True)
            cmds.setAttr(header_path, lock=True)

        # Crear Atributos
        if isinstance(value, tuple): # Enums
            enum_options = ":".join(value)
            cmds.addAttr(guides_transform, longName=key, attributeType='enum', enumName=enum_options, keyable=True)
        elif isinstance(value, int): # Integers
            cmds.addAttr(guides_transform, longName=key, attributeType='long', defaultValue=value, minValue=1, maxValue=20, keyable=True)

    return rig_settings_config

def load_rig_settings(guides_transform):
    """
    Lee los atributos actuales del objeto en Maya y los devuelve en un diccionario.
    """
    if not cmds.objExists(guides_transform):
        return None

    # Lista de atributos que queremos intentar leer
    attrs_to_read = [
        "Rig_Type", "spine_skinning_jnts", "spine_controllers", 
        "neck_skinning_jnts", "neck_controllers", "arm_skinning_jnts", 
        "leg_skinning_jnts", "tail_skinning_jnts", "tail_controllers"
    ]
    
    data = {}
    for attr in attrs_to_read:
        if cmds.attributeQuery(attr, node=guides_transform, exists=True):
            data[attr] = cmds.getAttr(f"{guides_transform}.{attr}")
            
    return data if data else None

def get_rig_data(character_name, guides_transform):
    """
    Exporta la data del rig a un archivo JSON en la carpeta 'build' del asset.
    """
    # Asumimos que asset_path es una función externa ya definida
    build_path = asset_path(character_name, "build") 
    if not os.path.exists(build_path):
        os.makedirs(build_path, exist_ok=True)

    rig_data = {}
    custom_attrs = cmds.listAttr(guides_transform, userDefined=True) or []

    for attr in custom_attrs:
        if attr.endswith("_SEP"):
            continue
            
        value = cmds.getAttr(f"{guides_transform}.{attr}")
        rig_data[attr] = value

    json_path = os.path.join(build_path, f"{character_name}_v001.build")

    try:
        with open(json_path, 'w') as json_file:
            json.dump(rig_data, json_file, indent=4)
        om.MGlobal.displayInfo(f"Rig data exported: {json_path}")
    except Exception as e:
        om.MGlobal.displayError(f"Error al guardar el archivo: {str(e)}")

    return json_path

def build_rig_from_data(character_name):
    """
    Carga la data desde el JSON más reciente.
    """
    build_path = asset_path(character_name, "build")
    build_file = get_latest_version(build_path) 

    if not build_file or not os.path.exists(build_file):
        om.MGlobal.displayError(f"No se encontró build para: {character_name}")
        return None
    
    try:
        with open(build_file, 'r') as json_file:
            rig_data = json.load(json_file)
        return rig_data
    except Exception as e:
        om.MGlobal.displayError(f"Error leyendo JSON: {str(e)}")
        return None
    



    
    
