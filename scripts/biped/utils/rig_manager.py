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


def import_meshes():

    """
    Import meshes from the asset's models folder.
    """
    character_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")

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



def import_skin_clusters():

    """
    Import skin clusters from the asset's skin_clusters folder.
    """
    character_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, character_name)
    skin_clusters_path = os.path.join(character_path, "skin_clusters")

class CustomBuild(object):
    """
    Custom build class for different character rigging operations.
    """

    def __init__(self):
        pass


    def jamal(self):
        """
        System for Jamal character rigging.
        """
        pass