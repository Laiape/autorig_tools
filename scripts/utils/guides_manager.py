import maya.cmds as cmds
import maya.api.OpenMaya as om
import json

def get_guides_info():

    """
    Get the guides transform and take the information from the joints and locators.

    """

    guides_transform = cmds.ls(selection=True, type="transform")[0]

    if not guides_transform:
        om.MGlobal.displayError("Please select a guide transform.")
        return None
    
    joint_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="joint")
    locator_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="locator")

    if joint_guides:
        for jnt in joint_guides:

            side = jnt.split("_")[0]
            jnt_name = side + "_" + jnt.split("_")[1]
            jnt_pos = om.MMatrix(jnt_pos)
        
    else:
        om.MGlobal.displayError("No joint guides found.")
        return None