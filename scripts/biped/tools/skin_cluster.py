import maya.cmds as cmds
import json
import os
from biped.utils import data_manager
import maya.api.OpenMaya as om


def export_joint_weights_json():

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

    CHARACTER_NAME = cmds.promptDialog(query=True, text=True)

    guides_name = cmds.promptDialog(query=True, text=True)

    # Get selected mesh
    sel = cmds.ls(sl=True, long=True)
    if not sel:
        cmds.error("Please select a skinned mesh first.")
        return

    mesh = sel[0]

    # Find skinCluster
    skin_clusters = cmds.ls(cmds.listHistory(mesh), type='skinCluster')
    if not skin_clusters:
        cmds.error("No skinCluster found on selected mesh.")
        return

    sc = skin_clusters[0]

    # Get all influences (joints)
    influences = cmds.skinCluster(sc, q=True, inf=True)

    vtx_count = cmds.polyEvaluate(mesh, v=True)

    # Build data structure
    result = {CHARACTER_NAME: {mesh: {sc : {}}}}

    # Initialize joint dictionaries
    for jnt in influences:
        result[CHARACTER_NAME][mesh][sc][jnt] = {}

    # Collect weights
    for i in range(vtx_count):
        vtx = f"{mesh}.vtx[{i}]"
        weights = cmds.skinPercent(sc, vtx, q=True, v=True)
        for jnt, w in zip(influences, weights):
            if w > 0.0:
                result[CHARACTER_NAME][mesh][sc][jnt][f"vtx[{i}]"] = w

    # Write JSON
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    final_path = os.path.join(relative_path, "skin_cluster")
    path = os.path.join(final_path, f"{CHARACTER_NAME}.weights")

    with open(path, 'w') as f:
        json.dump(result, f, indent=4)

    print(f"Export complete! Weights saved to: {path}")

def import_joint_weights_json(filePath=None):

    """
    Import joint weights from a JSON file and apply them to the selected skinned mesh.
    """

    if not filePath:
        
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        path = os.path.join(relative_path, "skin_cluster")
        guides_path = os.path.join(path, "guides")

        final_path = cmds.fileDialog2(fileMode=1, caption="Select a file", dir=guides_path, fileFilter="*.weights")[0]
       
        if not final_path:
            om.MGlobal.displayError("No file selected.")
            return None
        
    else:

        final_path = os.path.normpath(filePath)[0]

    if not final_path:
        om.MGlobal.displayError("No file selected.")
        return None
    
    with open(final_path, 'r') as f:
        data = json.load(f)
        mesh = list(data.keys())[-1] # Get the last key which is the mesh name
        print(mesh)

    # Apply weights to the selected mesh
    
    try:
        sel = cmds.ls(mesh, sl=True, long=True)
    except:
        om.MGlobal.displayError(f"Mesh {mesh} not found in the scene.")
        return

    # mesh = sel[0]

    if mesh not in data:
        cmds.error(f"No weight data found for mesh: {mesh}")
        return

    # Create a new skinCluster if one doesn't exist
    skin_clusters = cmds.ls(cmds.listHistory(mesh), type='skinCluster')
    if not skin_clusters:
        joints = list(data[mesh].keys())
        skin_joints = []
        for jnt in joints:
            if not cmds.objExists(jnt):
                new_jnt = cmds.createNode('joint', name=jnt) # Add missing joints
                skin_joints.append(new_jnt) # Create missing joints in the 0,0,0 position
            skin_joints.append(jnt) # Add existing joints as well

        sc = cmds.skinCluster(skin_joints, mesh, toSelectedBones=True)[0]
    else:
        sc = skin_clusters[0]

    # Apply weights from JSON data
    for joint, weights in data[mesh].items():
        for vtx, weight in weights.items():
            cmds.skinPercent(sc, f"{mesh}.{vtx}", tv=[(joint, weight)])

    print(f"Import complete! Weights loaded from: {final_path}")

def create_skin_cluster(joints=None, mesh=None):
    """
    Create a skin cluster for the given mesh and joints.
    If no joints or mesh are provided, use the current selection.
    """
    if not joints or not mesh:
        sel = cmds.ls(sl=True, long=True)
        if len(sel) < 2:
            cmds.error("Please select at least one joint and one mesh.")
            return

        joints = sel[:-1]
        mesh = sel[-1]

    sc = cmds.skinCluster(joints, mesh, toSelectedBones=True)[0]
    print(f"Skin cluster '{sc}' created for mesh '{mesh}' with joints: {joints}")
    return sc
