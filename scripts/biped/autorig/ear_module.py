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

class EarModule(object):

    def __init__(self):

        """
        Initialize the EarModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    def make(self, side):

        """ 
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_ear"
        if cmds.objExists(f"{self.module_name}Module_GRP"):
            self.module_trn = f"{self.module_name}Module_GRP"
            self.skeleton_grp = f"{self.module_name}Skinning_GRP"
            self.controllers_grp = f"{self.module_name}Controllers_GRP"
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.settings_ctl)

        self.load_guides()
        self.create_controllers()

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
        grp = ctl.replace("_CTL", "_GRP")
        mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMT"))
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{local_trn}.offsetParentMatrix")
        cmds.matchTransform(local_grp, ctl)

        return local_grp, local_trn

    def load_guides(self):

        """
        Load the ear guides and create controllers based on them.
        """

        self.ear_guides = guides_manager.get_guides(f"{self.side}_ear00_JNT")
        cmds.parent(self.ear_guides[0], self.module_trn)
 

    def create_controllers(self):

        """
        Create controllers for the ear module based on the loaded guides.
        """
        ear_controllers = []
        skinning_joints = []
        local_trns = []

        cmds.select(clear=True)

        for i, guide in enumerate(self.ear_guides):
            
            nodes, ctl = curve_tool.create_controller(name=guide.replace("_JNT", ""), offset=["GRP", "ANM"])
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            cmds.matchTransform(nodes[0], guide)
            local_grp = cmds.createNode("transform", name=guide.replace("_JNT", "Local_GRP"), ss=True, p=self.module_trn)
            local_trn = cmds.createNode("transform", name=guide.replace("_JNT", "Local_TRN"), ss=True, p=local_grp)
            cmds.matchTransform(local_grp, ctl)
            jnt = cmds.createNode("joint", name=guide.replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp) # Create skinning joint
            cmds.parent(nodes[0], self.controllers_grp)

            mult_matrix_local = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMT"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mult_matrix_local}.matrixIn[0]")
            cmds.connectAttr(f"{nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_local}.matrixIn[1]")
            cmds.connectAttr(f"{mult_matrix_local}.matrixSum", f"{local_trn}.offsetParentMatrix")

            if i > 0:
                cmds.parent(nodes[0], ear_controllers[i-1]) # Parent controller to previous controller
                mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Parent_MMT"))
                cmds.connectAttr(f"{local_trn}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
                cmds.connectAttr(f"{local_trns[i-1]}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
                cmds.connectAttr(f"{ear_controllers[i-1]}.matrix", f"{mult_matrix}.matrixIn[2]")
                cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{jnt}.offsetParentMatrix")
                cmds.parent(jnt, skinning_joints[i-1]) # Parent skinning joint to previous skinning joint
                
            else:
                cmds.connectAttr(f"{local_trn}.worldMatrix[0]", f"{jnt}.offsetParentMatrix") # Connect controller to skinning joint

            cmds.xform(jnt, m=om.MMatrix.kIdentity) # Reset joint transformations

            ear_controllers.append(ctl)
            skinning_joints.append(jnt)
            local_trns.append(local_trn)

        for i, jnt in enumerate(skinning_joints): # Reset joint transformations
            
            cmds.xform(jnt, m=om.MMatrix.kIdentity)
            cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)
            cmds.setAttr(f"{jnt}.translate", 0, 0, 0)
            cmds.setAttr(f"{jnt}.rotate", 0, 0, 0)

# ear = EarModule().make("L")
# ear = EarModule().make("R")