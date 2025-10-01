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
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    def make(self, side):

        """ 
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_ear"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

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
        mult_matrixs = []

        for guide in self.ear_guides:
            nodes, ctl = curve_tool.create_controller(name=guide.replace("_JNT", ""), offset=["GRP", "ANM"])
            cmds.matchTransform(nodes[0], guide)
            local_grp, local_trn = self.local(ctl)
            jnt = cmds.createNode("joint", name=guide.replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp) # Create skinning joint
            if ear_controllers:
                cmds.parent(nodes[0], ear_controllers[-1])
                mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "_MMT"))
                cmds.connectAttr(f"{mult_matrixs[-1]}.matrixSum", f"{mult_matrix}.matrixIn[0]")
                cmds.connectAttr(f"{local_trn}.worldMatrix[0]", f"{mult_matrix}.matrixIn[1]")
                cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{jnt}.offsetParentMatrix") # Connect controller to skinning joint
            else:
                cmds.parent(nodes[0], self.controllers_grp)
                cmds.connectAttr(f"{local_trn}.worldMatrix[0]", f"{jnt}.offsetParentMatrix") # Connect controller to skinning joint
            
            
            
            
            ear_controllers.append(ctl)
            mult_matrixs.append(mult_matrix)

