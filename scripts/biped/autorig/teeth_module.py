import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager

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
        self.head_guide = data_manager.DataExportBiped().get_data("neck_module", "head_guide")

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
        upper_teeth_guide = guides_manager.get_guides(f"{self.side}_upperTeeth_JNT")[0]
        cmds.select(cl=True)
        lower_teeth_guide = guides_manager.get_guides(f"{self.side}_lowerTeeth_JNT")[0]

        self.upper_teeth_guide = cmds.createNode("transform", name=upper_teeth_guide.replace("JNT", "GUIDE"), ss=True, p=self.module_trn)
        self.lower_teeth_guide = cmds.createNode("transform", name=lower_teeth_guide.replace("JNT", "GUIDE"), ss=True, p=self.module_trn)
        cmds.matchTransform(self.upper_teeth_guide, upper_teeth_guide)
        cmds.matchTransform(self.lower_teeth_guide, lower_teeth_guide)
        cmds.connectAttr(f"{self.head_guide}.worldInverseMatrix[0]", f"{self.upper_teeth_guide}.offsetParentMatrix")
        cmds.connectAttr(f"{self.head_guide}.worldInverseMatrix[0]", f"{self.lower_teeth_guide}.offsetParentMatrix")

        cmds.delete(upper_teeth_guide, lower_teeth_guide)

    def create_controllers(self):

        """
        Docstring for create_controllers
        
        :param self: Description
        """
        # Upper Teeth Controller
        upper_teeth_nodes, upper_teeth_ctl = curve_tool.create_controller(name=f"{self.side}_upperTeeth", offset=["GRP", "ANM"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.upper_teeth_guide}.worldMatrix[0]", f"{upper_teeth_nodes[0]}.offsetParentMatrix")
        upper_local_mmx = matrix_manager.local_mmx(upper_teeth_ctl, upper_teeth_nodes[0])
        self._lock_attributes(upper_teeth_ctl, ["v"])
        

        upper_teeth_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_upperTeeth_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{upper_local_mmx}.matrixSum", f"{upper_teeth_skinning_jnt}.offsetParentMatrix")
        upper_jaw = data_manager.DataExportBiped().get_data("jaw_module", "local_upper_jaw_mmx")
        cmds.connectAttr(f"{upper_jaw}.matrixSum", f"{upper_local_mmx}.matrixIn[3]")

        # Lower Teeth Controller
        lower_teeth_nodes, lower_teeth_ctl = curve_tool.create_controller(name=f"{self.side}_lowerTeeth", offset=["GRP", "ANM"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.lower_teeth_guide}.worldMatrix[0]", f"{lower_teeth_nodes[0]}.offsetParentMatrix")
        lower_local_mmx = matrix_manager.local_mmx(lower_teeth_ctl, lower_teeth_nodes[0])
        self._lock_attributes(lower_teeth_ctl, ["v"])
        

        lower_teeth_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_lowerTeeth_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{lower_local_mmx}.matrixSum", f"{lower_teeth_skinning_jnt}.offsetParentMatrix")
        jaw = data_manager.DataExportBiped().get_data("jaw_module", "local_jaw_mmx")
        cmds.connectAttr(f"{jaw}.matrixSum", f"{lower_local_mmx}.matrixIn[3]")

        cmds.xform(upper_teeth_nodes[0], m=om.MMatrix.kIdentity)
        cmds.xform(lower_teeth_nodes[0], m=om.MMatrix.kIdentity)

        