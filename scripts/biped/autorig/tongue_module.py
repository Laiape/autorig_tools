import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from biped.utils import data_manager
from biped.utils import guides_manager
from biped.utils import curve_tool

from biped.autorig.utilities import matrix_manager
from biped.autorig.utilities import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)
reload(ribbon)

class tongueModule(object):

    def __init__(self):

        """
        Initialize the tongueModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.head_grp = self.head_ctl.replace("_CTL", "_GRP")

    def make(self, side):

        """ 
        Create the tongue module structure and controllers. Call this method with the side ('L' or 'R') to create the respective tongue module.
        Args:
            side (str): The side of the tongue ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_tongue"
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
            attrs (list): List of attributes to lock and hide.
        """
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    def load_guides(self):

        """
        Load tongue guides from the guide manager.
        """
        self.tongue_guides = guides_manager.get_guides(f"{self.side}_tongue_JNT")
        # self.tongue_guides.sort()
        cmds.select(clear=True)

    def local_mmx(self, ctl, grp):

        """
        Create a local matrix manager for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            matrix_manager.MatrixManager: The local matrix manager.
        """

        mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        local_grp = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=self.module_trn)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
        grp_wm = cmds.getAttr(f"{grp}.worldMatrix[0]")
        cmds.setAttr(f"{mmx}.matrixIn[2]", grp_wm, type="matrix")
        cmds.connectAttr(f"{mmx}.matrixSum", f"{local_grp}.offsetParentMatrix")

        return local_grp, mmx