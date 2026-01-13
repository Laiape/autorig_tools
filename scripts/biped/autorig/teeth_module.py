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

class TeethModule(object):
    def __init__(self):

        """
        Initialize the noseModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    def make(self, side):

        """
        Docstring for make
        
        :param self: Description
        """

        self.side = side
        self.module_name = f"{self.side}_teeth"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)
        cmds.addAttr(self.face_ctl, longName="Teeth", attributeType="long", defaultValue=0, max=1, min=0, keyable=True)
        condition_teeth = cmds.createNode("condition", name=f"{self.module_name}Controllers_COND", ss=True)
        cmds.setAttr(f"{condition_teeth}.operation", 0)  # Equal
        cmds.setAttr(f"{condition_teeth}.secondTerm", 1)
        cmds.setAttr(f"{condition_teeth}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_teeth}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Teeth", f"{condition_teeth}.firstTerm")
        cmds.connectAttr(f"{condition_teeth}.outColorR", f"{self.controllers_grp}.visibility")

        self.load_guides()
        self.create_controllers()

    def _local_mmx(self, ctl, grp):

        """
        Create a local matrix manager for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            matrix_manager.MatrixManager: The local matrix manager.
        """

        mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        local_grp = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_GRP"), ss=True, p=self.module_trn)
        local_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=local_grp)
        
        # Create fourByFourMatrix for translation
        row_from_matrix = cmds.createNode("rowFromMatrix", name=ctl.replace("_CTL", "RFM"), ss=True)
        cmds.setAttr(f"{row_from_matrix}.input", 3)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{row_from_matrix}.matrix")
    
        fbf = cmds.createNode("fourByFourMatrix", name=ctl.replace("_CTL", "FBF"), ss=True)
        cmds.connectAttr(f"{row_from_matrix}.outputX", f"{fbf}.in30")
        cmds.connectAttr(f"{row_from_matrix}.outputY", f"{fbf}.in31")
        cmds.connectAttr(f"{row_from_matrix}.outputZ", f"{fbf}.in32")
        cmds.connectAttr(f"{fbf}.output", f"{local_grp}.offsetParentMatrix")

        # Connect to multMatrix
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
        cmds.connectAttr(f"{mmx}.matrixSum", f"{local_trn}.offsetParentMatrix")

        cmds.disconnectAttr(f"{ctl}.worldMatrix[0]", f"{row_from_matrix}.matrix")

        return local_trn, mmx

    def _lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def load_guides(self):

        """ 
        Load the guides for the teeth module.
        """
        self.upper_teeth_guide = guides_manager.get_guides(f"{self.side}_upperTeeth_JNT")[0]
        cmds.select(cl=True)
        self.lower_teeth_guide = guides_manager.get_guides(f"{self.side}_lowerTeeth_JNT")[0]

    def create_controllers(self):

        """
        Docstring for create_controllers
        
        :param self: Description
        """
        # Upper Teeth Controller
        upper_teeth_nodes, upper_teeth_ctl = curve_tool.create_controller(name=f"{self.side}_upperTeeth", offset=["GRP", "ANM"], parent=self.controllers_grp)
        self._lock_attributes(upper_teeth_ctl, ["v"])
        cmds.matchTransform(upper_teeth_nodes[0], self.upper_teeth_guide)
        cmds.delete(self.upper_teeth_guide)
        upper_local_trn, upper_mmx = self._local_mmx(upper_teeth_ctl, upper_teeth_nodes[0])
        upper_teeth_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_upperTeeth_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{upper_local_trn}.worldMatrix[0]", f"{upper_teeth_skinning_jnt}.offsetParentMatrix")
        upper_jaw = data_manager.DataExportBiped().get_data("jaw_module", "upper_jaw_ctl")
        matrix_manager.space_switches(target=upper_teeth_ctl, sources=[upper_jaw, self.masterwalk_ctl], default_value=1) # Upper teeth

        # Lower Teeth Controller
        lower_teeth_nodes, lower_teeth_ctl = curve_tool.create_controller(name=f"{self.side}_lowerTeeth", offset=["GRP", "ANM"], parent=self.controllers_grp)
        self._lock_attributes(lower_teeth_ctl, ["v"])
        cmds.matchTransform(lower_teeth_nodes[0], self.lower_teeth_guide)
        cmds.delete(self.lower_teeth_guide)
        lower_local_trn, lower_mmx = self._local_mmx(lower_teeth_ctl, lower_teeth_nodes[0])
        lower_teeth_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_lowerTeeth_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{lower_local_trn}.worldMatrix[0]", f"{lower_teeth_skinning_jnt}.offsetParentMatrix")
        jaw = data_manager.DataExportBiped().get_data("jaw_module", "jaw_ctl")
        matrix_manager.space_switches(target=lower_teeth_ctl, sources=[jaw, self.masterwalk_ctl], default_value=1) # Lower teeth

        