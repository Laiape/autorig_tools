import maya.cmds as cmds
import json
import os
from biped.utils import data_manager
import maya.api.OpenMaya as om
from biped.utils import rig_manager


def export_joint_weights_json():

    """
    Export joint weights of the selected skinned mesh to a JSON file.
    """



    CHARACTER_NAME = cmds.ls(assemblies=True)[-1] # Get the last as others are cameras. Gets the master node
    CHARACTER_NAME = CHARACTER_NAME.lower()
    
    meshes_in_scene = cmds.ls(type='mesh', long=True)
    skinned_meshes = []
    for mesh in meshes_in_scene:
        mesh = mesh.split("|")[-2]
        print(f"Checking mesh: {mesh}")
        skin_clusters = cmds.ls(cmds.listHistory(mesh), type='skinCluster')
        for sc in skin_clusters:
            if sc.endswith("_SKC"):
                skinned_meshes.append(mesh)


    if not skinned_meshes:
        om.MGlobal.displayError("No skinned meshes found in the scene.")
        return

    for mesh in skinned_meshes:
        skin_clusters = cmds.ls(cmds.listHistory(mesh), type='skinCluster')
        for sc in skin_clusters:
            if sc.endswith("_SKC"):
                print(f"Exporting weights for skinCluster: {sc}")
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
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "skin_clusters")
    TEMPLATE_FILE = os.path.join(TEMPLATE_PATH, f"{CHARACTER_NAME}_v001.weights")

    with open(TEMPLATE_FILE, 'w') as f:
        json.dump(result, f, indent=4)

    print(f"Export complete! Weights saved to: {TEMPLATE_FILE}")

def create_skin_clusters():

    """
    Import joint weights from a JSON file and apply them to the selected skinned mesh.
    """

    CHARACTER_NAME = cmds.ls(assemblies=True)[-1] # Get the last as others are cameras. Gets the master node
    CHARACTER_NAME = CHARACTER_NAME.lower()
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "skin_clusters")
    last_version = rig_manager.get_latest_version(TEMPLATE_PATH)

    TEMPLATE_FILE = os.path.join(TEMPLATE_PATH, f"{CHARACTER_NAME}_v001.weights")

    if not TEMPLATE_FILE:
        om.MGlobal.displayError("No file selected.")
        return None
    
    with open(TEMPLATE_FILE, 'r') as f:
        data = json.load(f)


    # Apply weights to the selected mesh
    
    meshes_in_scene = cmds.ls(type='mesh', long=True)

    created_skin_clusters = []
    mesh_skinned = []
    for mesh in data[CHARACTER_NAME]:
        print(f"Processing mesh: {mesh}")
        for msh in meshes_in_scene:
            msh = msh.split("|")[-2] # Get the actual mesh name [-1] would be the shape node
            if msh not in data[CHARACTER_NAME]:
                om.MGlobal.displayWarning(f"Mesh {msh} not found in the weight data.")
                continue

        for sc in data[CHARACTER_NAME][mesh]:
            print(f"Creating skinCluster: {sc} for mesh: {mesh}")
            influences = list(data[CHARACTER_NAME][mesh][sc].keys())
            # Create skin cluster
            new_skin_cluster = cmds.skinCluster(influences, mesh, toSelectedBones=True, name=sc)[0]
            mesh_skinned.append(mesh)

            # Apply weights
            for jnt in data[CHARACTER_NAME][mesh][sc]:
                for vtx, weight in data[CHARACTER_NAME][mesh][sc][jnt].items():
                    cmds.skinPercent(new_skin_cluster, vtx, transformValue=[(jnt, weight)])
            created_skin_clusters.append(new_skin_cluster)



def build_serial_skinclusters(character_name, template_file):
    with open(template_file, 'r') as f:
        data = json.load(f)

    for mesh in data[character_name]:
        mesh_shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True)
        if not mesh_shapes:
            continue
        shape = mesh_shapes[0]

        sc_names = list(data[character_name][mesh].keys())
        body_scs = [sc for sc in sc_names if "body" in sc.lower()]
        other_scs = [sc for sc in sc_names if "body" not in sc.lower()]
        ordered_scs = sorted(other_scs) + body_scs

        prev_output = shape
        created_skin_clusters = []

        for sc in ordered_scs:
            influences = list(data[character_name][mesh][sc].keys())

            new_sc = cmds.skinCluster(
                influences, mesh,
                toSelectedBones=True,
                name=sc
            )[0]

            try:
                cmds.disconnectAttr(f"{shape}.inMesh", f"{new_sc}.inputGeometry")
            except:
                pass

            cmds.connectAttr(f"{prev_output}.worldMesh[0]",
                             f"{new_sc}.inputGeometry", force=True)
            prev_output = f"{new_sc}.outputGeometry[0]"

            for jnt in data[character_name][mesh][sc]:
                for vtx, weight in data[character_name][mesh][sc][jnt].items():
                    cmds.skinPercent(new_sc, vtx, transformValue=[(jnt, weight)])

            created_skin_clusters.append(new_sc)

        cmds.connectAttr(prev_output, f"{shape}.inMesh", force=True)

    return created_skin_clusters



