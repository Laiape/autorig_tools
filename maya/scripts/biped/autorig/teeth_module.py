import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya.scripts.utils import data_manager
from maya.scripts.utils import guides_manager
from maya.scripts.utils import curve_tool
from maya.scripts.utils import matrix_manager

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
        self.head_guide_matrix = data_manager.DataExportBiped().get_data("neck_module", "head_guide_matrix")

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

    def load_guides(self):

        """ 
        Load the guides for the teeth module.
        """
        upper_teeth_guide = guides_manager.get_guides(f"{self.side}_upperTeeth_JNT")[0]
        cmds.select(cl=True)
        lower_teeth_guide = guides_manager.get_guides(f"{self.side}_lowerTeeth_JNT")[0]

        # Matrices horneadas (guía * inversa de la cabeza), sin transforms _GUIDE vivos
        head_inverse = om.MMatrix(self.head_guide_matrix).inverse()
        self.upper_teeth_matrix = om.MMatrix(cmds.getAttr(f"{upper_teeth_guide}.worldMatrix[0]")) * head_inverse
        self.lower_teeth_matrix = om.MMatrix(cmds.getAttr(f"{lower_teeth_guide}.worldMatrix[0]")) * head_inverse

        cmds.delete(upper_teeth_guide, lower_teeth_guide)

    def create_controllers(self):

        """
        Docstring for create_controllers
        
        :param self: Description
        """
        # Upper Teeth Controller
        upper_jaw = data_manager.DataExportBiped().get_data("jaw_module", "local_upper_jaw_mmx")
        upper_jaw_ctl_wm = cmds.listConnections(f"{upper_jaw}.matrixIn[0]", plugs=True, source=True)[0]
        upper_jaw_grp_inv_wm = cmds.listConnections(f"{upper_jaw}.matrixIn[1]", plugs=True, source=True)[0]

        upper_teeth_nodes, upper_teeth_ctl = curve_tool.create_controller(name=f"{self.side}_upperTeeth", offset=["GRP", "ANM"], parent=self.controllers_grp)
        upper_teeth_mmx = cmds.createNode("multMatrix", name=f"{self.side}_upperTeeth_MMX", ss=True)
        cmds.setAttr(f"{upper_teeth_mmx}.matrixIn[0]", list(self.upper_teeth_matrix), type="matrix")
        cmds.connectAttr(upper_jaw_ctl_wm, f"{upper_teeth_mmx}.matrixIn[1]")
        cmds.connectAttr(upper_jaw_grp_inv_wm, f"{upper_teeth_mmx}.matrixIn[2]")
        cmds.connectAttr(f"{upper_teeth_mmx}.matrixSum", f"{upper_teeth_nodes[0]}.offsetParentMatrix")
        upper_local_mmx = matrix_manager.local_mmx(upper_teeth_ctl, upper_teeth_nodes[0])
        curve_tool.lock_attributes(upper_teeth_ctl, ["v"])

        upper_bind_wm = om.MMatrix(self.upper_teeth_matrix)
        upper_jaw_grp_wm_baked = om.MMatrix(cmds.getAttr(f"{upper_jaw}.matrixIn[2]"))
        cmds.setAttr(f"{upper_local_mmx}.matrixIn[2]", list(upper_bind_wm * upper_jaw_grp_wm_baked.inverse()), type="matrix")

        upper_teeth_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_upperTeeth_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{upper_local_mmx}.matrixSum", f"{upper_teeth_skinning_jnt}.offsetParentMatrix")
        cmds.connectAttr(f"{upper_jaw}.matrixSum", f"{upper_local_mmx}.matrixIn[3]")

        # Lower Teeth Controller
        jaw = data_manager.DataExportBiped().get_data("jaw_module", "local_jaw_mmx")
        jaw_ctl_wm = cmds.listConnections(f"{jaw}.matrixIn[0]", plugs=True, source=True)[0]
        jaw_grp_inv_wm = cmds.listConnections(f"{jaw}.matrixIn[1]", plugs=True, source=True)[0]

        lower_teeth_nodes, lower_teeth_ctl = curve_tool.create_controller(name=f"{self.side}_lowerTeeth", offset=["GRP", "ANM"], parent=self.controllers_grp)
        lower_teeth_mmx = cmds.createNode("multMatrix", name=f"{self.side}_lowerTeeth_MMX", ss=True)
        cmds.setAttr(f"{lower_teeth_mmx}.matrixIn[0]", list(self.lower_teeth_matrix), type="matrix")
        cmds.connectAttr(jaw_ctl_wm, f"{lower_teeth_mmx}.matrixIn[1]")
        cmds.connectAttr(jaw_grp_inv_wm, f"{lower_teeth_mmx}.matrixIn[2]")
        cmds.connectAttr(f"{lower_teeth_mmx}.matrixSum", f"{lower_teeth_nodes[0]}.offsetParentMatrix")
        lower_local_mmx = matrix_manager.local_mmx(lower_teeth_ctl, lower_teeth_nodes[0])
        curve_tool.lock_attributes(lower_teeth_ctl, ["v"])

        lower_bind_wm = om.MMatrix(self.lower_teeth_matrix)
        jaw_grp_wm_baked = om.MMatrix(cmds.getAttr(f"{jaw}.matrixIn[2]"))
        cmds.setAttr(f"{lower_local_mmx}.matrixIn[2]", list(lower_bind_wm * jaw_grp_wm_baked.inverse()), type="matrix")

        lower_teeth_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_lowerTeeth_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{lower_local_mmx}.matrixSum", f"{lower_teeth_skinning_jnt}.offsetParentMatrix")
        cmds.connectAttr(f"{jaw}.matrixSum", f"{lower_local_mmx}.matrixIn[3]")

        cmds.xform(upper_teeth_nodes[0], m=om.MMatrix.kIdentity)
        cmds.xform(lower_teeth_nodes[0], m=om.MMatrix.kIdentity)

        