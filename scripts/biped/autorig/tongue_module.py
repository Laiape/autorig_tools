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

class TongueModule(object):

    def __init__(self):

        """
        Initialize the tongueModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        self.head_guide = data_manager.DataExportBiped().get_data("neck_module", "head_guide")

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
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)

        cmds.addAttr(self.face_ctl, longName="Tongue", attributeType="long", defaultValue=0, max=1, min=0, keyable=True)
        condition_tongue = cmds.createNode("condition", name=f"{self.module_name}Controllers_COND", ss=True)
        cmds.setAttr(f"{condition_tongue}.operation", 0)  # Equal
        cmds.setAttr(f"{condition_tongue}.secondTerm", 1)
        cmds.setAttr(f"{condition_tongue}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_tongue}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Tongue", f"{condition_tongue}.firstTerm")
        cmds.connectAttr(f"{condition_tongue}.outColorR", f"{self.controllers_grp}.visibility")

        self.load_guides()
        self.create_controllers()

    def _lock_attributes(self, ctl, attrs):

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
        self.tongue_guides = guides_manager.get_guides(f"{self.side}_tongue00_JNT")

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
    
    def create_controllers(self):

        """
        Create controllers for the tongue module.
        """
        de_boors_selection = []
        tongue_ctrls = []

        for i, jnt in enumerate(self.tongue_guides):

            grp, ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP", "ANM"], parent=self.controllers_grp)
            self._lock_attributes(ctl, ["v"])
            cmds.connectAttr(f"{self.head_guide}.worldInverseMatrix[0]", f"{grp[0]}.offsetParentMatrix")
            local_grp, mmx = self.local_mmx(ctl, grp[0])
            
            if tongue_ctrls:
                cmds.parent(grp[0], tongue_ctrls[-1])
                cmds.connectAttr(f"{tongue_ctrls[-1]}.matrix", f"{mmx}.matrixIn[2]")

            de_boors_selection.append(local_grp)
            tongue_ctrls.append(ctl)
            cmds.matchTransform(grp[0], jnt, pos=True, rot=True)
            cmds.matchTransform(local_grp, jnt, pos=True, rot=True) 

        # De Boor Tongue Ribbon
        skinning_jnts, temp = ribbon.de_boor_ribbon(de_boors_selection, name=f"{self.side}_tongueSkinning", aim_axis="x", up_axis="y", num_joints=len(self.tongue_guides), skeleton_grp=self.skeleton_grp)

        for t in temp:
            cmds.delete(t)

        cmds.delete(self.tongue_guides)
        
