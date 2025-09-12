import maya.cmds as cmds
import json
import os
from biped.utils import data_manager
import maya.api.OpenMaya as om

CHARACTER_NAME = data_manager.DataExport().get_data("basic_structure", "character_name")

def export_weights():

    """Export skin weights of selected mesh to a file."""
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("No mesh selected.")
        return

    mesh = selected[0]
    skin_cluster = cmds.ls(cmds.listHistory(mesh), type='skinCluster')
    if not skin_cluster:
        cmds.warning("Selected mesh has no skin cluster.")
        return

    skin_cluster = skin_cluster[0]

    answer = cmds.promptDialog(
                title="INPUT DIALOG",
                message="INSERT FILE NAME",
                button=["OK", "Cancel"],
                defaultButton="OK",
                cancelButton="Cancel",
                dismissString="Cancel")
    
    if answer == "Cancel":
        om.MGlobal.displayInfo("Operation cancelled by user.")
        return


    file_path = file_path[0]
    skin_data = {CHARACTER_NAME: {}}
    try:
        cmds.deformerWeights(file_path, export=True, deformer=skin_cluster, format='json')
        with open(os.path.join(final_path, f"{CHARACTER_NAME}.skin"), "w") as output_file:
            json.dump(skin_data, output_file, indent=4)
        om.MGlobal.displayInfo("Weights exported to {}".format(file_path))
    except Exception as e:
        om.MGlobal.displayError("Failed to export weights: {}".format(e))