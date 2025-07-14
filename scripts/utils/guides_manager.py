import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os

GUIDES_PATH = "C:\GITHUB\guides"

def get_guides_info():

    """
    Get the guides transform and take the information from the joints and locators.

    """

    guides_transform = cmds.ls(selection=True, type="transform")[0]

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
    
    guides_name = cmds.promptDialog(query=True, text=True)

    if not guides_transform:
        om.MGlobal.displayError("Please select a guide transform.")
        return None
    
    joint_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="joint")
    locator_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="locator")

    if joint_guides:

        joint_matrices = []
        joint_parents = []
        joint_prefered_angles = []
        joint_joint_orient = []

        left_guides = []
        right_guides = []

        for jnt in joint_guides:

            if jnt.startswith("L_"):
                left_guides.append(jnt)

            if jnt.startswith("R_"):
                right_guides.append(jnt)

            name = jnt.split("_")[1]
            joint_matrices.append(cmds.xform(jnt, q=True, ws=True, m=True))
            joint_parent = cmds.listRelatives(jnt, parent=True)[0]
            joint_parents.append(joint_parent)
 

        if len(left_guides) != len(right_guides):
            om.MGlobal.displayInfo("The number of left and right guides are not the same.")


            for left_guide in left_guides:
                for right_guide in right_guides:
                    if name in left_guide and name in right_guide:
                        left_world_position = [round(coord, 3) for coord in cmds.xform(left_guide, q=True, ws=True, t=True)]
                        right_world_position = [round(coord, 3) for coord in cmds.xform(right_guide, q=True, ws=True, t=True)]

                        left_world_position[0] = right_world_position[0] * -1       
                                 
    else:
        om.MGlobal.displayError("No joint guides found.")
        return None

    if locator_guides:

        locator_positions = []

        for loc in locator_guides:
            side = loc.split("_")[0]

            parent_transform = cmds.listRelatives(loc, parent=True)[0]
            locator_positions.append(cmds.xform(parent_transform, q=True, ws=True, m=True))

    else:
        om.MGlobal.displayInfo("No locator guides found.")


    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    final_path = os.path.join(relative_path, "guides")
    guides_data = {guides_name: {}}
    

    for i, guide in enumerate(joint_guides):
        key = guide[0] if isinstance(guide, list) else guide
        guides_data[guides_name][key] = {
            "joint_matrix": joint_matrices[i],
            "parent": joint_parents[i],
            "isLocator": False,                     
    }

        
    if locator_guides:
        for i, loc in enumerate(locator_guides):
            guides_data[guides_name][loc] = {
                "locator_position": locator_positions[i],
                "isLocator": True,
            }

    if not os.path.exists(final_path):
        os.makedirs(final_path)
    
    with open(os.path.join(final_path, f"{guides_name}.guides"), "w") as output_file:
        json.dump(guides_data, output_file, indent=4)

    om.MGlobal.displayInfo(f"Guides data saved to {os.path.join(final_path, f'{guides_name}.guides')}")



def load_guides_info(filePath=None):

    """ Load guides information from a JSON file and create the guides in the scene."""

    
    if not filePath:
        
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        guides_path = os.path.join(relative_path, "guides")

        final_path = cmds.fileDialog2(fileMode=1, caption="Select a file", dir=guides_path, fileFilter="*.guides")[0]
       
        if not final_path:
            om.MGlobal.displayError("No file selected.")
            return None
        
    else:

        final_path = os.path.normpath(filePath)[0]

    name = os.path.basename(final_path).split(".")[0]

    with open(final_path, "r") as input_file:
        guides_data = json.load(input_file)

    
    
    if not cmds.ls("C_guides_GRP"):

        guides_node = "C_guides_GRP"

        guides_node = cmds.createNode("transform", name=guides_node, ss=True)

        for guide, data in reversed(list(guides_data[name].items())):
                
                if "isLocator" in data and data["isLocator"]:
                        locator = cmds.spaceLocator(name=guide.replace("Shape", "_LOC"))[0]
                        cmds.xform(locator, ws=True, m=data["locator_position"])
                        cmds.parent(locator, guides_node)

                else:

                    cmds.select(clear=True)
                    imported_joint = cmds.joint(name=guide, r=5)
                    cmds.xform(imported_joint, ws=True, m=data["joint_matrix"])
                    cmds.makeIdentity(imported_joint, apply=True, r=True)

                    if data["parent"] == "C_root_JNT":
                        cmds.parent(imported_joint, guides_node)
                    else:
                        cmds.parent(imported_joint, data["parent"])
            
    else:

        om.MGlobal.displayError("Guides group 'C_guides_GRP' already exists. Please delete it before loading new guides.")


def delete_guides():

    """ Deletes the guides group and all its children."""

    guides_group = "C_guides_GRP"

    if cmds.objExists(guides_group):
        cmds.delete(guides_group)
        om.MGlobal.displayInfo(f"Deleted guides group: {guides_group}")
    else:
        om.MGlobal.displayError(f"Guides group '{guides_group}' does not exist.")

        

