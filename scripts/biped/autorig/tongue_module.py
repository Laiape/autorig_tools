import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager
from utils import ribbon

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
        self.guides_matrices, self.guides_trns = guides_manager.orient_guides(self.tongue_guides, primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, 1, 0))
        cmds.delete(self.tongue_guides[0])
        cmds.parent(self.guides_trns[0], self.module_trn)

    def local_mmx(self, ctl, grp):

        """
        Create a local matrix manager for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            matrix_manager.MatrixManager: The local matrix manager.
        """

        mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
        grp_wm = cmds.getAttr(f"{grp}.worldMatrix[0]")
        cmds.setAttr(f"{mmx}.matrixIn[2]", grp_wm, type="matrix")

        return mmx
    
    def create_controllers(self):

        """
        Create controllers for the tongue module.
        """
        tongue_controllers = []
        skinning_jnts = []
        local_matrices = []
        
        for i, matrix in enumerate(self.guides_matrices):
            
            ctl_name = f"{self.side}_tongue0{i}"

            nodes, ctl = curve_tool.create_controller(name=ctl_name, offset=["GRP", "ANM"], parent=self.controllers_grp, locked_attrs=["v"])
            mmx = cmds.createNode("multMatrix", name=f"{ctl_name}_MMX", ss=True)

            if i == 0:
                
                cmds.connectAttr(matrix, f"{mmx}.matrixIn[0]")
                cmds.connectAttr(f"{self.head_guide}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
            
            else:
                cmds.parent(nodes[0], tongue_controllers[-1])
                cmds.connectAttr(matrix, f"{mmx}.matrixIn[0]")
                inverse_matrix = cmds.createNode("inverseMatrix", name=f"{ctl_name}_IVM", ss=True)
                cmds.connectAttr(self.guides_matrices[i-1], f"{inverse_matrix}.inputMatrix")
                cmds.connectAttr(f"{inverse_matrix}.outputMatrix", f"{mmx}.matrixIn[1]")

            cmds.connectAttr(f"{mmx}.matrixSum", f"{nodes[0]}.offsetParentMatrix")

            cmds.xform(nodes[0], m=om.MMatrix.kIdentity)
            local_mmx = self.local_mmx(ctl, nodes[0])
            skinning_jnt = cmds.createNode("joint", name=f"{ctl_name}Skinning_JNT", ss=True, p=self.skeleton_grp)

            if i != 0:
                cmds.parent(skinning_jnt, skinning_jnts[-1])
                cmds.connectAttr(f"{inverse_matrix}.outputMatrix", f"{local_mmx}.matrixIn[3]")
            
            cmds.connectAttr(f"{local_mmx}.matrixSum", f"{skinning_jnt}.offsetParentMatrix")
            cmds.xform(skinning_jnt, m=om.MMatrix.kIdentity)
            
            tongue_controllers.append(ctl)
            local_matrices.append(local_mmx)
            skinning_jnts.append(skinning_jnt)