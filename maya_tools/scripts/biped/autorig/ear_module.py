import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class EarModule(object):

    def __init__(self):

        """
        Initialize the EarModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

        self.primaryInputAxis = 0, 1, 0
        self.secondaryInputAxis = 0, 0, 1

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
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)

            cmds.addAttr(self.face_ctl, longName="Ears", attributeType="long", defaultValue=1, max=1, min=0, keyable=True)
            condition_node = cmds.createNode("condition", name=f"{self.face_ctl}_Ears_COND")
            cmds.connectAttr(f"{self.face_ctl}.Ears", f"{condition_node}.firstTerm")
            cmds.setAttr(f"{condition_node}.secondTerm", 1)
            cmds.setAttr(f"{condition_node}.operation", 3)  # Greater Than or Equal
            cmds.setAttr(f"{condition_node}.colorIfTrueR", 1)
            cmds.setAttr(f"{condition_node}.colorIfFalseR", 0)
            cmds.connectAttr(f"{condition_node}.outColorR", f"{self.controllers_grp}.visibility")

        self.load_guides()
        self.create_controllers()

        # Clean up
        cmds.delete(self.ear_guides[0])

    def local(self, ctl):

        """
        Create the local matrix network for a controller WITHOUT transforms:
        ctl.worldMatrix * GRP.worldInverseMatrix * baked bind matrix (what the old
        Local_TRN worldMatrix was). See matrix_manager.local_mmx.
        Args:
            ctl (str): The name of the controller.
        Returns:
            str: The Local_MMX multMatrix node.
        """

        return matrix_manager.local_mmx(ctl, ctl.replace("_CTL", "_GRP"))

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
        local_mmxs = []

        cmds.select(clear=True)

        for i, guide in enumerate(self.ear_guides):

            nodes, ctl = curve_tool.create_controller(name=guide.replace("_JNT", ""), offset=["GRP", "ANM"])
            curve_tool.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            cmds.matchTransform(nodes[0], guide)
            jnt = cmds.createNode("joint", name=guide.replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp) # Create skinning joint
            cmds.parent(nodes[0], self.controllers_grp)

            # Local network without transforms: ctl.worldMatrix * GRP.worldInverseMatrix * baked bind matrix
            local_mmx = matrix_manager.local_mmx(ctl, nodes[0])

            if i > 0:
                cmds.parent(nodes[0], ear_controllers[i-1]) # Parent controller to previous controller
                inverse_prev_local = cmds.createNode("inverseMatrix", name=ctl.replace("_CTL", "LocalPrev_INV"), ss=True)
                cmds.connectAttr(f"{local_mmxs[i-1]}.matrixSum", f"{inverse_prev_local}.inputMatrix")
                mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Parent_MMT"))
                cmds.connectAttr(f"{local_mmx}.matrixSum", f"{mult_matrix}.matrixIn[0]")
                cmds.connectAttr(f"{inverse_prev_local}.outputMatrix", f"{mult_matrix}.matrixIn[1]")
                cmds.connectAttr(f"{ear_controllers[i-1]}.matrix", f"{mult_matrix}.matrixIn[2]")
                cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{jnt}.offsetParentMatrix")
                cmds.parent(jnt, skinning_joints[i-1]) # Parent skinning joint to previous skinning joint

            else:
                cmds.connectAttr(f"{local_mmx}.matrixSum", f"{jnt}.offsetParentMatrix") # Connect controller to skinning joint

            cmds.xform(jnt, m=om.MMatrix.kIdentity) # Reset joint transformations

            ear_controllers.append(ctl)
            skinning_joints.append(jnt)
            local_mmxs.append(local_mmx)

        for i, jnt in enumerate(skinning_joints): # Reset joint transformations

            cmds.xform(jnt, m=om.MMatrix.kIdentity)
            cmds.setAttr(f"{jnt}.jointOrient", 0, 0, 0)
            cmds.setAttr(f"{jnt}.translate", 0, 0, 0)
            cmds.setAttr(f"{jnt}.rotate", 0, 0, 0)