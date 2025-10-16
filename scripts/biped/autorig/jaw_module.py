import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from biped.utils import data_manager
from biped.utils import guides_manager
from biped.utils import curve_tool

from biped.autorig.utilities import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)

class JawModule(object):

    def __init__(self):

        """
        Initialize the jawModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    
    def make(self, side):

        """ 
        Create the jaw module structure and controllers. Call this method with the side ('L' or 'R') to create the respective jaw module.
        Args:
            side (str): The side of the jaw ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_jaw"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

        self.load_guides()
        self.create_controllers()
        self.collision_setup()

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    def local(self, ctl):

        """
        Create a local transform node for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            str: The name of the local transform node.
        """

        local_grp = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_GRP"), ss=True, p=self.module_trn)
        local_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=local_grp)
        cmds.matchTransform(local_grp, ctl)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_trn}.offsetParentMatrix")
        
        return local_grp, local_trn
    
    def load_guides(self):

        """
        Load the guide positions for the jaw module.
        Returns:
            dict: A dictionary containing the guide positions.
        """

        self.jaw_guides = guides_manager.get_guides("C_jaw_JNT") # Jaw father, l_jaw_JNT, r_jaw_JNT and c_chin_JNT

        # self.jaw_guides = 
        
        for guide in self.jaw_guides:
            cmds.parent(guide, self.module_trn)

    def create_controllers(self):
        
        """
        Create the controllers for the jaw module.  
        """
    

        self.jaw_nodes, self.jaw_ctl = curve_tool.create_controller("C_jaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.matchTransform(self.jaw_nodes[0], self.jaw_guides[0])
        self.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])

        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.matchTransform(self.upper_jaw_nodes[0], self.jaw_guides[0])
        self.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])

        self.chin_nodes, self.chin_ctl = curve_tool.create_controller("C_chin", offset=["GRP", "OFF"], parent=self.jaw_ctl)
        cmds.matchTransform(self.chin_nodes[0], self.jaw_guides[-1])
        self.lock_attributes(self.chin_ctl, ["v"])

        for side in ["L", "R"]:
            self.side_jaw_nodes, self.side_jaw_ctl = curve_tool.create_controller(f"{side}_sideJaw", offset=["GRP", "OFF"], parent=self.jaw_ctl)
            cmds.matchTransform(self.side_jaw_nodes[0], self.jaw_guides[1 if side == "L" else 2])
            self.lock_attributes(self.side_jaw_ctl, ["sx", "sy", "sz", "v"])

    def collision_setup(self):

        """
        Set up collision detection for the jaw module.
        """

        # Add attribute to the jaw controller
        cmds.addAttr(self.jaw_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
        cmds.setAttr(f"{self.jaw_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
        cmds.addAttr(self.jaw_ctl, longName="Collision", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)

        # Create nodes for collision detection
        row_from_matrix_jaw = cmds.createNode("decomposeMatrix", name=f"{self.module_name}_collisionJaw_DCM")
        row_from_matrix_upper_jaw = cmds.createNode("decomposeMatrix", name=f"{self.module_name}_collisionUpperJaw_DCM")

        cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{row_from_matrix_jaw}.inputMatrix")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.matrix", f"{row_from_matrix_upper_jaw}.inputMatrix")

        plus_minus_jaw = cmds.createNode("plusMinusAverage", name=f"{self.module_name}_collisionJaw_PMA", ss=True)
        cmds.setAttr(f"{plus_minus_jaw}.operation", 2) # Subtraction
        cmds.connectAttr(f"{row_from_matrix_jaw}.outputRotateX", f"{plus_minus_jaw}.input1D[0]")
        cmds.connectAttr(f"{row_from_matrix_upper_jaw}.outputRotateX", f"{plus_minus_jaw}.input1D[1]")

        clamp_jaw = cmds.createNode("clamp", name=f"{self.module_name}_collisionJaw_CLP")
        cmds.setAttr(f"{clamp_jaw}.minR", -360)
        cmds.connectAttr(f"{plus_minus_jaw}.output1D", f"{clamp_jaw}.inputR") # Connect the output of the plusMinusAverage to the input of the clamp node
        cmds.connectAttr(f"{row_from_matrix_upper_jaw}.outputRotateX", f"{clamp_jaw}.maxR") # Connect the output of the rowFromMatrix to the input of the clamp node


        float_constant_0 = cmds.createNode("floatConstant", name=f"{self.module_name}_collisionJaw_FC0")
        cmds.setAttr(f"{float_constant_0}.inFloat", 0)

        attribute_blender = cmds.createNode("blendTwoAttr", name=f"{self.module_name}_collisionJaw_BTA")
        cmds.connectAttr(f"{self.jaw_ctl}.Collision", f"{attribute_blender}.attributesBlender")
        cmds.connectAttr(f"{float_constant_0}.outFloat", f"{attribute_blender}.input[0]")
        cmds.connectAttr(f"{clamp_jaw}.outputR", f"{attribute_blender}.input[1]")
        cmds.connectAttr(f"{attribute_blender}.output", f"{self.upper_jaw_nodes[1]}.rotateX")  # Connect the output of the blendTwoAttr to the rotateX of the upper jaw controller
