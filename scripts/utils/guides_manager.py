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

        left_guides = []
        right_guides = []

        for jnt in joint_guides:

            if jnt.startswith("L_"):
                side = jnt.split("_")[0]
                left_guides.append(jnt)

            if jnt.startswith("R_"):
                side = jnt.split("_")[0]
                right_guides.append(jnt)

            name = jnt.split("_")[1]
            joint_matrices.append(cmds.xform(jnt, q=True, ws=True, m=True))
            joint_parents = cmds.listRelatives(jnt, parent=True)
            joint_prefered_angles = cmds.getAttr(jnt + ".preferredAngle")


            if len(left_guides) != len(right_guides):
                om.MGlobal.displayError("The number of left and right guides are not the same.")
                return

            for left_guide in left_guides:
                for right_guide in right_guides:
                    if name in left_guide and name in right_guide:
                        left_world_position = [round(coord, 3) for coord in cmds.xform(left_guide, q=True, ws=True, t=True)]
                        right_world_position = [round(coord, 3) for coord in cmds.xform(right_guide, q=True, ws=True, t=True)]

                        left_world_position[0] = right_world_position[0] * -1       
                                 
    else:
        om.MGlobal.displayError("No joint guides found.")
        return None
    
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    final_path = os.path.join(relative_path, "guides")
    guides_data = {guides_name: {}}
    
    print(joint_matrices)


    if locator_guides:

        locator_positions = []

        for loc in locator_guides:
            side = loc.split("_")[0]
            locator_positions.append(cmds.xform(loc, q=True, ws=True, t=True))

    else:
        om.MGlobal.displayInfo("No locator guides found.")

    print(locator_positions)

    for info_jnt, info_loc in zip(joint_matrices, locator_positions):
        
        pass