# Python libraries import
import glob
import os
import json
from importlib import reload
import re
import pathlib

from numpy import character
from utils import matrix_manager
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
from biped.autorig import arm_module as arm_module
from biped.autorig import spine_module as biped_spine_module
from biped.autorig import clavicle_module
from biped.autorig import leg_module as leg_module
from biped.autorig import neck_module_de_boor as neck_module
from biped.autorig import fingers_module

from quadruped.autorig import tail_module
from quadruped.autorig import limb_module
from quadruped.autorig import leg_module as quad_leg_module
from quadruped.autorig import spine_module as quad_spine_module
from quadruped.autorig import neck_module as neck_module_quad

# Facial
from biped.autorig import eyebrow_module
from biped.autorig import eyelid_module
from biped.autorig import ear_module
from biped.autorig import nose_module
from biped.autorig import jaw_module_nurbs as jaw_module_nurbs
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
reload(quad_leg_module)
reload(quad_spine_module)
reload(neck_module_quad)
reload(eyebrow_module)
reload(eyelid_module)
reload(ear_module)
reload(nose_module)
reload(jaw_module_nurbs)
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
    Busca en los assemblies de la escena y retorna el nombre del personaje,
    ignorando el grupo de guías y cámaras.
    """
    all_assemblies = cmds.ls(assemblies=True, transforms=True, dagObjects=True)
    ignore_list = ["C_guides_GRP", "Mechanic_sets_grp", "defaultLightSet", "defaultObjectSet"]
    for obj in all_assemblies:
        if obj in ignore_list:
            continue
        if cmds.listRelatives(obj, type='camera', noIntermediate=True):
            continue
        return [obj]

    return None
    

def get_character_name_from_scene(avoid=None):
    """
    Extracts the character name from the current Maya scene filename.
    Returns:
        str: The character name extracted from the scene filename.
    """

    asset_name = cmds.optionVar(q="currentAssetRigName")
    return asset_name

def get_character_name_from_build():

    """
    Extracts the character name from the build file name in the current Maya scene.
    Returns:
        str: The character name extracted from the build file name.
    """

    asset_name = cmds.optionVar(q="currentAssetRigName")
    return asset_name

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

    subfolders = ["models", "build", "cache", "curves", "guides", "skin_clusters", "corrective_blendshapes"]

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

    main_folder = asset_path(asset_name, "")
    
    # Crear carpeta principal y subcarpetas
    subfolders = ["models", "build", "cache", "curves", "guides", "skin_clusters", "corrective_blendshapes"]

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
    
    character_name = cmds.optionVar(q="currentAssetRigName")

    cmds.file(new=True, force=True)
    
    scene_name = f"CHAR_{character_name}_v001.ma"
    cmds.file(rename=scene_name)
    
    om.MGlobal.displayInfo(f"Nueva escena creada y renombrada como: {scene_name}")

    scene_to_open, scene_assemblies = open_model_scene(character_name)
    
    if not scene_to_open:
        cmds.warning(f"No se encontraron mallas para importar en la carpeta de {character_name}")

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


def build_rig(character_name, on_step=None):

    """
    Función principal de construcción del Rig.
    on_step(label, current, total) — optional callback for progress reporting.
    """
    _step = [0]
    _TOTAL = 20

    def step(label):
        _step[0] += 1
        if on_step:
            on_step(label, _step[0], _TOTAL)

    reload(guides_manager)
    guides_manager.clear_guides_cache()  # empieza con cache limpio (guías quizá re-exportadas)
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

    step("Loading rig settings…")

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
    mGear_integration   = rig_settings.get("mGear_integration", 0)

    data_manager.DataExportBiped().append_data("rig_settings",
                            {
                                "mGear_integration" : mGear_integration,
                            })

    # --- Spine ---
    if check("C_spine00_JNT"):
        step("Building spine…")
        if rig_type == 0:
            reload(biped_spine_module)
            biped_spine_module.SpineModule().make("C", spine_skinning_jnts, spine_controllers)
        else:
            reload(quad_spine_module)
            quad_spine_module.SpineModule().make("C", spine_skinning_jnts, spine_controllers)

    

    # --- Legs (Solo Biped) ---
    if rig_type == 0:
        if check("L_hip_JNT") and check("R_hip_JNT"):
            step("Building legs…")
            reload(leg_module)
            leg_module.LegModule().make("L", leg_skinning_jnts)
            leg_module.LegModule().make("R", leg_skinning_jnts)

    # --- Legs (Solo Quadruped) ---
    if rig_type == 1:
        leg_solver = rig_settings.get("leg_solver", "spring")

        # Patas Delanteras (módulo de pierna nuevo)
        if check("L_frontLegShoulder_JNT") and check("R_frontLegShoulder_JNT"):
            step("Building front legs…")
            reload(quad_leg_module)
            quad_leg_module.FrontLegModule().make("L", solver=leg_solver, skinning_jnts=leg_skinning_jnts)
            quad_leg_module.FrontLegModule().make("R", solver=leg_solver, skinning_jnts=leg_skinning_jnts)

        # Fallback: limb genérico con el naming antiguo
        elif check("L_frontLeg_JNT") and check("R_frontLeg_JNT"):
            step("Building front limbs…")
            reload(limb_module)

            data_manager.DataExportBiped().append_data("limb_module",
                            {
                                "guides_data" : ["L_frontLeg_JNT", "R_frontLeg_JNT"],
                            })

            limb_module.LimbModule().make("L", leg_skinning_jnts)
            limb_module.LimbModule().make("R", leg_skinning_jnts)

        # Patas Traseras (módulo de pierna nuevo)
        if check("L_backLegHip_JNT") and check("R_backLegHip_JNT"):
            step("Building back legs…")
            reload(quad_leg_module)
            quad_leg_module.BackLegModule().make("L", solver=leg_solver, skinning_jnts=leg_skinning_jnts)
            quad_leg_module.BackLegModule().make("R", solver=leg_solver, skinning_jnts=leg_skinning_jnts)

    # --- Arms / Clavicles ---
    if check("L_clavicle_JNT") and check("R_clavicle_JNT"):
        step("Building clavicles…")
        reload(clavicle_module)
        clavicle_module.ClavicleModule().make("L")
        clavicle_module.ClavicleModule().make("R")

    if check("L_shoulder_JNT") and check("R_shoulder_JNT"):
        step("Building arms…")
        reload(arm_module)
        arm_module.ArmModule().make("L", arm_skinning_jnts)
        arm_module.ArmModule().make("R", arm_skinning_jnts)

    if check("L_thumb00_JNT") and check("R_thumb00_JNT"):
        step("Building fingers…")
        reload(fingers_module)
        fingers_module.FingersModule().make("L")
        fingers_module.FingersModule().make("R")

    # --- Tail ---
    if check("C_tail00_JNT"):
        step("Building tail…")
        reload(tail_module)
        tail_module.TailModule().make("C", tail_skinning_jnts, tail_controllers)

    # --- Neck ---
    if check("C_neck00_JNT"):
        step("Building neck…")
        if rig_type == 0:
            if mGear_integration:
                reload(neck_module)
                neck_module.NeckModule().make("C", neck_skinning_jnts, neck_controllers, mGear_integration=True)
            else:
                reload(neck_module)
                neck_module.NeckModule().make("C", neck_skinning_jnts, neck_controllers)
        else:
            reload(neck_module_quad)
            neck_module_quad.NeckModule().make("C", neck_skinning_jnts, neck_controllers)

    # =========================================================================
    # BUILD: FACIAL
    # =========================================================================

    if check("C_jaw_JNT"):
        step("Building jaw…")
        reload(jaw_module_nurbs)
        jaw_module_nurbs.JawModule().make("C")

    if (check("L_eyebrowMain_JNT") and check("R_eyebrowMain_JNT")) or \
       (check("L_eyebrow_CRVShape") and check("R_eyebrow_CRVShape")):
        step("Building eyebrows…")
        reload(eyebrow_module)
        eyebrow_module.EyebrowModule().make("L")
        eyebrow_module.EyebrowModule().make("R")

    if check("L_eye_JNT") and check("R_eye_JNT"):
        step("Building eyelids…")
        reload(eyelid_module)
        build_sockets = (rig_type == 0)

        EYELID_SURFACE_CHARS = {"thaiz", "mechanic", "freya", "maui"}
        eyelid_surface = (rig_type != 0) or (str(character_name).lower() in EYELID_SURFACE_CHARS)
        eyelid_module.EyelidModule().make("L", sockets=build_sockets, surface=eyelid_surface)
        eyelid_module.EyelidModule().make("R", sockets=build_sockets, surface=eyelid_surface)

    if check("C_tongue00_JNT"):
        step("Building tongue…")
        reload(tongue_module)
        tongue_module.TongueModule().make("C")

    if check("C_upperTeeth_JNT"):
        step("Building teeth…")
        reload(teeth_module)
        teeth_module.TeethModule().make("C")

    if check("L_ear00_JNT") and check("R_ear00_JNT"):
        step("Building ears…")
        reload(ear_module)
        ear_module.EarModule().make("L")
        ear_module.EarModule().make("R")

    if check("C_nose_JNT"):
        step("Building nose…")
        reload(nose_module)
        nose_module.NoseModule().make("L")
        nose_module.NoseModule().make("R")

    if check("L_cheekbone_JNT") and check("R_cheekbone_JNT"):
        step("Building cheekbones…")
        reload(cheekbone_module)
        cheekbone_module.CheekboneModule().make("L")
        cheekbone_module.CheekboneModule().make("R")

    if rig_type == 0 and mGear_integration == 0:
        biped_space_switches()
    elif rig_type == 1:
        quadruped_space_switches()
    
    skeleton_hierarchy()


def apply_character_extras(rig_settings):
    """
    Applies character-specific extras defined in the 'character_extras' block
    of the .build JSON.

    Supported operations
    --------------------
    add_attrs: list of dicts with keys:
        node    — "module/key" (resolved via data_manager) or a literal Maya name
        name    — attribute long name
        type    — "float" | "int" | "bool"  (default: "float")
        min     — optional minimum value
        max     — optional maximum value
        default — optional default value (default: 0.0)
    """
    extras = rig_settings.get("character_extras", {})
    if not extras:
        return

    for attr_def in extras.get("add_attrs", []):
        node_path = attr_def.get("node", "")

        if "/" in node_path:
            module, key = node_path.split("/", 1)
            node = data_manager.DataExportBiped().get_data(module, key)
        else:
            node = node_path

        if not node or not cmds.objExists(node):
            om.MGlobal.displayWarning(f"character_extras: node not found → '{node_path}'")
            continue

        attr_name = attr_def.get("name")
        attr_type = attr_def.get("type", "float")
        default   = attr_def.get("default", 0.0)
        min_val   = attr_def.get("min")
        max_val   = attr_def.get("max")

        if cmds.attributeQuery(attr_name, node=node, exists=True):
            continue

        kwargs = {"longName": attr_name, "keyable": True, "defaultValue": default}
        if attr_type == "int":
            kwargs["attributeType"] = "long"
        elif attr_type == "bool":
            kwargs["attributeType"] = "bool"
        else:
            kwargs["attributeType"] = "float"

        if min_val is not None:
            kwargs["minValue"] = min_val
        if max_val is not None:
            kwargs["maxValue"] = max_val

        cmds.addAttr(node, **kwargs)
        om.MGlobal.displayInfo(f"character_extras: added '{attr_name}' → '{node}'")

def biped_space_switches():

        """
        Crea los space switches para el Rig Biped.
        """

        # ---- Drivers ----
        chest = data_manager.DataExportBiped().get_data("spine_module", "local_chest_ctl")
        body = data_manager.DataExportBiped().get_data("spine_module", "body_ctl")
        local_hip = data_manager.DataExportBiped().get_data("spine_module", "local_hip_ctl")
        head = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        neck = data_manager.DataExportBiped().get_data("neck_module", "neck_ctl")

        # ---- Space switches ----
        matrix_manager.space_switches(target=neck, sources=[chest, body], default_rotate=1, default_translate=1) # Neck
        matrix_manager.space_switches(target=local_hip, sources=[body], default_rotate=1, default_translate=1) # Local hip

        for side in ["L", "R"]:

            # ---- Drivers ----
            arm_ik = data_manager.DataExportBiped().get_data("arm_module", f"{side}_armIk")
            arm_pv = data_manager.DataExportBiped().get_data("arm_module", f"{side}_armPv")
            leg_ik = data_manager.DataExportBiped().get_data("leg_module", f"{side}_legIk")
            leg_pv = data_manager.DataExportBiped().get_data("leg_module", f"{side}_legPv")
            shoulder_fk = data_manager.DataExportBiped().get_data("arm_module", f"{side}_shoulderFk")
            hip_fk = data_manager.DataExportBiped().get_data("leg_module", f"{side}_hipFk")
            clavicle = data_manager.DataExportBiped().get_data("clavicle_module", f"{side}_clavicle")
            root_ik = data_manager.DataExportBiped().get_data("leg_module", f"{side}_rootIk")
            arm_ik_root = data_manager.DataExportBiped().get_data("arm_module", f"{side}_armIkRoot")

            # ---- Space switches ----
            matrix_manager.space_switches(target=arm_ik, sources=[body, clavicle, chest, local_hip, head], default_rotate=1, default_translate=1) # Arm ik
            matrix_manager.space_switches(target=arm_pv, sources=[body, arm_ik, clavicle, chest], default_rotate=1, default_translate=1, pv=True) # Arm pv
            matrix_manager.space_switches(target=leg_ik, sources=[local_hip, body], default_rotate=0, default_translate=0) # Leg ik
            matrix_manager.space_switches(target=leg_pv, sources=[body, leg_ik], default_rotate=1, default_translate=1, pv=True) # Leg pv
            matrix_manager.space_switches(target=shoulder_fk, sources=[clavicle, chest, body], default_rotate=1, default_translate=1) # Shoulder fk
            matrix_manager.space_switches(target=hip_fk, sources=[body, local_hip], default_rotate=1, default_translate=1) # Hip fk
            matrix_manager.space_switches(target=root_ik, sources=[local_hip], default_rotate=1, default_translate=1) # Root ik
            matrix_manager.space_switches(target=clavicle, sources=[chest, body], default_rotate=1, default_translate=1) # Clavicle
            matrix_manager.space_switches(target=arm_ik_root, sources=[clavicle, chest], default_rotate=1, default_translate=1) # Arm ik root


def quadruped_space_switches():

        """
        Crea los space switches para el Rig Quadruped: patas traseras y delanteras (con escápula)
        contra spine/neck. Cada switch usa las keys que exportan los módulos:
            - backLeg_module / frontLeg_module: {side}_legIk, {side}_legPv,
              {side}_hipFk, {side}_rootIk (+ scapula_ctl / scapula_master_ctl).
            - spine_module: local_hip_ctl, body_ctl, local_chest_ctl.
            - neck_module: neck_ctl.
        """

        data = data_manager.DataExportBiped()

        def _node(x):
            # get_data puede devolver lista (p.ej. fk_ctls) o string; normaliza
            if isinstance(x, (list, tuple)):
                x = x[0] if x else None
            return x if (x and cmds.objExists(x)) else None

        def _ss(target, sources, **kwargs):
            # No-op si falta el target o todos los sources (módulo no construido)
            target = _node(target)
            sources = [s for s in (_node(s) for s in sources) if s]
            if not target or not sources:
                return
            matrix_manager.space_switches(target=target, sources=sources, **kwargs)

        # ---- Drivers de spine / neck ----
        body = data.get_data("spine_module", "body_ctl")
        local_hip = data.get_data("spine_module", "local_hip_ctl")
        local_chest = data.get_data("spine_module", "local_chest_ctl")
        neck = data.get_data("neck_module", "neck_ctl")
        tail = data.get_data("tail_module", "tail_ctl")

        # ---- Spine / Neck / Tail ----
        _ss(local_hip, [body], default_rotate=1, default_translate=1)          # Local hip
        _ss(neck, [local_chest, body], default_rotate=1, default_translate=1)  # Neck
        _ss(tail, [local_hip, body], default_rotate=1, default_translate=1)    # Tail
        for side in ["L", "R"]:

            # =========================== BACK LEG ===========================
            bl_ik   = data.get_data("backLeg_module", f"{side}_legIk")
            bl_pv   = data.get_data("backLeg_module", f"{side}_legPv")
            bl_fk   = data.get_data("backLeg_module", f"{side}_hipFk")
            bl_root = data.get_data("backLeg_module", f"{side}_rootIk")

            _ss(bl_ik, [local_hip, body], default_rotate=0, default_translate=0)        # Back leg ik
            _ss(bl_pv, [bl_ik, local_hip, body], default_rotate=1, default_translate=1, pv=True)  # Back leg pv
            _ss(bl_fk, [local_hip, body], default_rotate=1, default_translate=1)        # Back hip fk
            _ss(bl_root, [local_hip, body], default_rotate=1, default_translate=1)      # Back root ik

            # =========================== FRONT LEG ==========================
            fl_ik       = data.get_data("frontLeg_module", f"{side}_legIk")
            fl_pv       = data.get_data("frontLeg_module", f"{side}_legPv")
            fl_fk       = data.get_data("frontLeg_module", f"{side}_hipFk")
            fl_root     = data.get_data("frontLeg_module", f"{side}_rootIk")
            scapula_mst = data.get_data("frontLeg_module", f"{side}_scapula_master_ctl")

            _ss(scapula_mst, [local_chest, body], default_rotate=1, default_translate=1)            # Scapula master
            _ss(fl_fk, [scapula_mst, local_chest, body], default_rotate=1, default_translate=1)     # Front fk
            _ss(fl_root, [scapula_mst, local_chest, body], default_rotate=1, default_translate=1)   # Front root ik
            _ss(fl_ik, [local_chest, body], default_rotate=0, default_translate=0)                  # Front leg ik
            _ss(fl_pv, [fl_ik, local_chest, body], default_rotate=1, default_translate=1, pv=True)  # Front leg pv


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
        "tail_skinning_jnts": 5, "tail_controllers": 5,
        "mGear_integration": 0
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
        "tail_controllers": defaults["tail_controllers"],
        "mGear_integration": ("disabled", "enabled")
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
    
    for key, value in rig_settings_config.items():
        attr_path = f"{guides_transform}.{key}"
        
        # Evitar duplicados
        if cmds.objExists(attr_path):
            continue

        # Crear separadores visuales (Header) si es necesario
        header_name = key.split('_')[0].upper()
        header_path = f"{guides_transform}.{header_name}_SEP"
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

def parented_chain(skinning_joints, parent=None, hand_value=False):

    skel_grp = "skeletonHierarchy_GRP"
    if parent and cmds.objExists(parent.replace("_JNT", "_ENV")):
        parent = parent.replace("_JNT", "_ENV")
    root_parent = parent if parent else skel_grp

    jnts = list(skinning_joints)
    jnt_set = set(jnts)
    has_hierarchy = any(
        ((cmds.listRelatives(j, parent=True, type="joint", fullPath=True) or [None])[0] in jnt_set)
        for j in jnts
    )

    def _env_name(jnt):
        return jnt.split("|")[-1].replace("Skinning_JNT", "_ENV").replace("_JNT", "_ENV")

    def _make(jnt, parent_node):
        env = cmds.createNode("joint", name=_env_name(jnt), parent=parent_node)
        inv = cmds.listConnections(f"{env}.inverseScale", destination=False, source=True, plugs=True)
        if inv:
            cmds.disconnectAttr(inv[0], f"{env}.inverseScale")
        return env

    created = []
    if has_hierarchy:
        jnts.sort(key=lambda j: j.count("|"))
        jnt_to_env = {}
        for jnt in jnts:
            jp = cmds.listRelatives(jnt, parent=True, type="joint", fullPath=True)
            parent_node = jnt_to_env[jp[0]] if (jp and jp[0] in jnt_to_env) else root_parent
            env = _make(jnt, parent_node)
            jnt_to_env[jnt] = env
            created.append((jnt, env))
    else:
        sides = {}
        for jnt in jnts:
            sides.setdefault(jnt.split("|")[-1].split("_")[0], []).append(jnt)
        for chain in sides.values():
            prev = None
            for jnt in chain:
                env = _make(jnt, root_parent if prev is None else prev)
                created.append((jnt, env))
                prev = env
    for jnt, env in created:
        env_parent = cmds.listRelatives(env, parent=True, fullPath=True)
        negate = env_parent[0] if env_parent else None
        if negate and negate.split("|")[-1] != skel_grp:
            mmx = cmds.createNode("multMatrix", name=env.split("|")[-1].replace("_ENV", "Env_MMX"), ss=True)
            cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{mmx}.matrixIn[0]", force=True)
            cmds.connectAttr(f"{negate}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]", force=True)
            cmds.connectAttr(f"{mmx}.matrixSum", f"{env}.offsetParentMatrix", force=True)
        else:
            cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{env}.offsetParentMatrix", force=True)
        cmds.setAttr(f"{env}.jointOrient", 0, 0, 0, type="double3")

    return [env for _, env in created]


def skeleton_hierarchy():

    """
    Construye el esqueleto de export (_ENV) a partir de los _JNT de skinning.
    Modelado en puiastreTools.autorig.skeleton_hierarchy: duplica la jerarquía de
    cada módulo (vía parented_chain), parentea las raíces según reglas, y conecta
    cada _ENV a su _JNT negando el padre.

    Reglas de parent del joint raíz de cada módulo:
      - spine                      -> C_freeze_ENV (joint raíz, padre de todo)
      - faciales                   -> cabeza (*head_ENV)
      - arm / fingers (mismo lado) -> L/R clavicle / L/R wrist
      - leg                        -> localHip
      - clavicle / neck            -> localChest
      - resto                      -> último joint del módulo anterior (o C_freeze_ENV)
    """

    if not cmds.objExists("skeletonHierarchy_GRP"):
        skel_grp = cmds.group(empty=True, name="skeletonHierarchy_GRP")
        cmds.parent("skeletonHierarchy_GRP", "rig_GRP")
    else:
        skel_grp = "skeletonHierarchy_GRP"

    if not cmds.objExists("skel_GRP"):
        return

    # Joint "freeze": raíz / padre de TODO el esqueleto _ENV.
    if cmds.objExists("C_freeze_ENV"):
        freeze_jnt = cmds.ls("C_freeze_ENV", long=True)[0]
    else:
        freeze_jnt = cmds.createNode("joint", name="C_freeze_ENV", parent=skel_grp)

    facial_modules = {"jaw", "eyelid", "eyebrow", "nose", "cheekbone", "ear", "tongue", "teeth", "eye"}
    parent_same_side = {"arm": "clavicle", "fingers": "wrist"}
    child_to_parent_jnt = {"leg": "localHip", "clavicle": "localChest", "neck": "localChest"}

    module_grps = cmds.listRelatives("skel_GRP", type="transform", fullPath=True) or []
    modules = []
    for grp in module_grps:
        parts = grp.split("|")[-1].split("_")
        side = parts[0]
        clean = parts[1].replace("Skinning", "")
        jnts = cmds.listRelatives(grp, allDescendents=True, type="joint", fullPath=True) or []
        if jnts:
            modules.append((side, clean, jnts))

    def phase(clean):
        if clean == "spine":            return 0
        if clean in facial_modules:     return 4
        if clean == "fingers":          return 3
        if clean == "arm":              return 2
        return 1
    modules.sort(key=lambda m: phase(m[1]))

    def find_env(pattern):
        f = cmds.ls(pattern, type="joint", long=True) or []
        return f[0] if f else None

    def _is_corrective(j):
        n = j.split("|")[-1].lower()
        return "corrective" in n or "ring" in n

    last_module_end = None
    for side, clean, jnts in modules:
        # Las joints correctivas (pushers/anillos) NO entran en el encadenado del
        # módulo: se preservan aparte como hijas de su joint padre, así no rompen la
        # detección plano/jerárquico de la cadena principal.
        correctives = [j for j in jnts if _is_corrective(j)]
        main = [j for j in jnts if j not in set(correctives)]

        if clean == "spine":
            parent = freeze_jnt
        elif clean in facial_modules:
            parent = find_env("*head_ENV")
        elif clean in parent_same_side:
            parent = find_env(f"{side}_{parent_same_side[clean]}*_ENV")
        elif clean in child_to_parent_jnt:
            parent = find_env(f"*{child_to_parent_jnt[clean]}*_ENV")
        else:
            parent = last_module_end or freeze_jnt

        ends = parented_chain(main, parent) if main else []
        if ends:
            last_module_end = ends[-1]

        # Correctivas: cada una cuelga del _ENV de su joint padre (preservadas).
        for cj in correctives:
            jp = cmds.listRelatives(cj, parent=True, type="joint", fullPath=True)
            if not jp:
                continue
            p_env_name = jp[0].split("|")[-1].replace("Skinning_JNT", "_ENV").replace("_JNT", "_ENV")
            p_env = find_env(p_env_name)
            if p_env:
                parented_chain([cj], p_env)

def corrective_joints(joint, shape="square"):

    """
    Crea un joint correctivo para el joint dado.
    El joint correctivo se crea como hijo del joint original y se conecta
    a su worldMatrix para que siga la transformación del joint padre.
    """
    if not cmds.objExists(joint):
        om.MGlobal.displayError(f"El joint '{joint}' no existe.")
        return None

    joint_name = joint.split("|")[-1]
    joint_name_base = joint_name.split("_")[1]
    joint_up_axys = "y"
    joint_up_axys_vector = (0,1,0)
    axys = {"x": (3, 0, 0), "y": (0, 3, 0), "z": (0, 0, 3), joint_up_axys: joint_up_axys_vector}
    identity_matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

    # Crear shape cuadrada desde el joint original
    for ax, vec in axys.items():
        corrective_joint = cmds.createNode("joint", name=f"{joint_name_base}_CRT", parent=joint)
        corrective_matrix = om.MMatrix(identity_matrix) * om.MMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, vec[0], vec[1], vec[2], 1])
        cmds.setAttr(f"{corrective_joint}.offsetParentMatrix", list(corrective_matrix), type="matrix")



    
    
