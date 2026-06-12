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

class NoseModule(object):

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
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_nose"
        if cmds.objExists(f"{self.module_name}Module_GRP"):
            self.module_trn = f"{self.module_name}Module_GRP"
            self.skeleton_grp = f"{self.module_name}Skinning_GRP"
            self.controllers_grp = f"{self.module_name}Controllers_GRP"
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)
            cmds.addAttr(self.face_ctl, longName="Nose", attributeType="long", defaultValue=1, max=1, min=0, keyable=True)
            
            condition_nose = cmds.createNode("condition", name="C_noseControllers_COND", ss=True)
            cmds.setAttr(f"{condition_nose}.operation", 0)  # Equal
            cmds.setAttr(f"{condition_nose}.secondTerm", 1)
            cmds.setAttr(f"{condition_nose}.colorIfTrueR", 1)
            cmds.setAttr(f"{condition_nose}.colorIfFalseR", 0)
            cmds.connectAttr(f"{self.face_ctl}.Nose", f"{condition_nose}.firstTerm")
            cmds.connectAttr(f"{condition_nose}.outColorR", f"{self.controllers_grp}.visibility")

        

        self.load_guides()
        self.create_controllers()

        if self.side == "R":
            for guide in [self.nose_main_guide, self.nose_tip_guide, self.side_nose_guide, self.nostrils_guide]:
                if cmds.objExists(guide):
                    cmds.delete(guide)


    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    def local(self, ctl, parent_ctl=None):

        """
        Create the local matrix network for a controller WITHOUT transforms:
        ctl.matrix * baked bind matrix (* parent local matrixSum when parent_ctl
        is given). Equivalent to the old Local_GRP/Local_TRN pair, with the
        parenting expressed as a baked offset + the parent's Local_MMX chain.
        Args:
            ctl (str): The name of the controller.
            parent_ctl (str): The controller whose local network acts as parent.
        Returns:
            str: The Local_MMX multMatrix node.
        """

        local_mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_mmx}.matrixIn[0]")
        ctl_world = om.MMatrix(cmds.getAttr(f"{ctl}.worldMatrix[0]"))
        if parent_ctl is None:
            cmds.setAttr(f"{local_mmx}.matrixIn[1]", list(ctl_world), type="matrix")
        else:
            parent_world = om.MMatrix(cmds.getAttr(f"{parent_ctl}.worldMatrix[0]"))
            cmds.setAttr(f"{local_mmx}.matrixIn[1]", list(ctl_world * parent_world.inverse()), type="matrix")
            cmds.connectAttr(f"{parent_ctl.replace('_CTL', 'Local_MMX')}.matrixSum", f"{local_mmx}.matrixIn[2]")

        return local_mmx

    def load_guides(self):

        """
        Load the nose guides and create controllers based on them.
        """
        cmds.select(clear=True)
        self.nose_main_guide = guides_manager.get_guides("C_noseMain_JNT")[0]
        cmds.select(clear=True)
        self.nose_tip_guide = guides_manager.get_guides("C_noseTip_JNT")[0]
        cmds.select(clear=True)
        self.side_nose_guide = guides_manager.get_guides(f"{self.side}_nose_JNT")[0]
        cmds.select(clear=True)
        self.nostrils_guide = guides_manager.get_guides(f"{self.side}_nosetril_JNT")[0]
        cmds.select(clear=True)
        self.nose_guide = guides_manager.get_guides(f"C_nose_JNT")[0]

        if self.side == "L":
            self.nose_guides = [
            self.nose_main_guide,
            self.nose_tip_guide,
            self.nostrils_guide,
            self.side_nose_guide
            ]
        elif self.side == "R":
            self.nose_guides = [
            self.nostrils_guide,
            self.side_nose_guide,
            ]

 

    def create_controllers(self):

        """
        Create controllers for the nose module based on the loaded guides.
        """
        nose_controllers = []
        skinning_joints = []

        cmds.select(clear=True)
        if self.side == "L":
            base_nodes, base_ctl = curve_tool.create_controller(name="C_baseNose", offset=["GRP"], parent=self.controllers_grp) # Base nose controller
            cmds.matchTransform(base_nodes[0], self.nose_guide)
            base_local_mmx = self.local(base_ctl)
        cmds.delete(self.nose_guide)

        for i, guide in enumerate(self.nose_guides):
            nodes, ctl = curve_tool.create_controller(name=guide.replace("_JNT", ""), offset=["GRP"], parent=self.controllers_grp)

            if "tril" not in guide:
                self.lock_attributes(ctl, ["v"])
            else:
                self.lock_attributes(ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "v"])
            cmds.matchTransform(nodes[0], guide)

            parent_ctl = None
            if self.side == "L":
                if i != 0:
                    parent_ctl = "C_baseNose_CTL"
                    if guide == f"{self.side}_nose_JNT":
                        parent_ctl = f"{self.side}_nosetril_CTL"
            else:
                parent_ctl = "C_baseNose_CTL"
                if guide == f"{self.side}_nose_JNT":
                    parent_ctl = f"{self.side}_nosetril_CTL"

            if parent_ctl is not None:
                cmds.parent(nodes[0], parent_ctl)
            local_mmx = self.local(ctl, parent_ctl)

            nose_controllers.append(ctl)

            jnt = cmds.createNode("joint", name=guide.replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp) # Create skinning joint
            cmds.connectAttr(f"{local_mmx}.matrixSum", f"{jnt}.offsetParentMatrix") # Connect controller to skinning joint
            skinning_joints.append(jnt)
            cmds.delete(guide)
        
        

