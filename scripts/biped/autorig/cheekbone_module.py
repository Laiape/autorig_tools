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

class CheekboneModule(object):

    def __init__(self):

        """
        Initialize the CheekboneModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.head_guide = data_manager.DataExportBiped().get_data("neck_module", "head_guide")

    def make(self, side):

        """ 
        Create the cheekbone module structure and controllers. Call this method with the side ('L' or 'R') to create the respective cheekbone module.
        Args:
            side (str): The side of the cheekbone ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_cheekbone"
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
        Load cheekbone guides from the guide manager.
        """
        self.cheekbone_guides = guides_manager.get_guides(f"{self.side}_cheekbone_JNT")
        # self.cheekbone_guides.sort()
        cmds.select(clear=True)
        self.cheek_guide = guides_manager.get_guides(f"{self.side}_cheek_JNT")

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
        Create controllers for the cheekbone module.
        """
        
        cheeckbones_ctls = []
        cheeckbones_grps = []
        local_trns = []
        skinning_jnts = []

        for i, guide in enumerate(self.cheekbone_guides):

            name = guide.replace("_JNT", "")

            if i == 0:
                grp, ctl = curve_tool.create_controller(name=name, parent=self.controllers_grp, offset=["GRP", "OFF"])
                cheeckbones_ctls.append(ctl)
                cheeckbones_grps.append(grp)
                self.lock_attributes(ctl, ["v"])
            else:
                grp, ctl = curve_tool.create_controller(name=name, parent=cheeckbones_ctls[0], offset=["GRP", "OFF"])
                cheeckbones_ctls.append(ctl)
                cheeckbones_grps.append(grp)
                self.lock_attributes(ctl, ["rx", "ry", "rz", "v"])    

            cmds.matchTransform(grp[0], guide)
            trn, mmx = self.local_mmx(ctl, grp[0])
            skinning_jnt = cmds.createNode("joint", name=guide.replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp)
            cmds.connectAttr(f"{trn}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")

            if i == 0:
                local_trns.append(trn)
                skinning_jnts.append(skinning_jnt)
            else:
                # cmds.connectAttr(f"{cheeckbones_ctls[0]}.matrix", f"{mmx}.matrixIn[3]")
                cmds.parent(trn, local_trns[0])
                # cmds.parent(skinning_jnt, skinning_jnts[0])
                local_trns.append(trn)
                skinning_jnts.append(skinning_jnt)

            
        cmds.delete(self.cheekbone_guides)
            
        # Cheek 
        grp, ctl = curve_tool.create_controller(name=self.cheek_guide[0].replace("_JNT", ""), parent=self.controllers_grp, offset=["GRP", ])
        self.lock_attributes(ctl, ["rx", "ry", "rz", "v"])
        trn, mmx = self.local_mmx(ctl, grp[0])
        cheek_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "_GUIDE"), ss=True, p=self.module_trn)
        cmds.matchTransform(cheek_trn, self.cheek_guide[0])

        if self.side == "L":
            mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "_MMX"), ss=True)
            cmds.connectAttr(f"{cheek_trn}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
            cmds.connectAttr(f"{self.head_guide}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")

        if self.side == "R":
            mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Flip_MMX"), ss=True)
            four_by_four = cmds.createNode("fourByFourMatrix", name=ctl.replace("_CTL", "Flip_FFM"), ss=True)
            cmds.setAttr(f"{four_by_four}.in00", -1)
            cmds.connectAttr(f"{four_by_four}.output", f"{mult_matrix}.matrixIn[0]")
            cmds.connectAttr(f"{cheek_trn}.worldMatrix[0]", f"{mult_matrix}.matrixIn[1]")
            cmds.connectAttr(f"{self.head_guide}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[2]")

        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{grp[0]}.offsetParentMatrix")
        cmds.xform(grp[0], m=om.MMatrix.kIdentity)

        

        if self.side == "R":
            four_by_four = cmds.createNode("fourByFourMatrix", name=ctl.replace("_CTL", "Flip_MMX"), ss=True)
            cmds.setAttr(f"{four_by_four}.in00", -1)
            cmds.connectAttr(f"{four_by_four}.output", f"{mmx}.matrixIn[3]")

        cmds.matchTransform(trn, self.cheek_guide[0])
            
        skinning_jnt = cmds.createNode("joint", name=self.cheek_guide[0].replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{trn}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")
        cmds.delete(self.cheek_guide)