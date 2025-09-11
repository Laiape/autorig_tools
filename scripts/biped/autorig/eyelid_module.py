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

class EyelidModule(object):

    def __init__(self):

        """
        Initialize the eyelidModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExport().get_data("neck_module", "head_ctl")

    def make(self, side):

        """ 
        Create the eyelid module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyelid module.
        Args:
            side (str): The side of the eyelid ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_eyelid"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

        self.load_guides()
        self.create_controllers()
        self.create_main_eye_setup()
        self.attributes()
        self.create_blink_setup()

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
        Load the guide locators for the eyelid module.
        """

        self.locators = []
        for guide in ["In", "UpIn", "Up", "UpOut",  "DownIn", "Down", "DownOut", "Out"]:
            loc = guides_manager.get_guides(f"{self.side}_eyelid{guide}_LOCShape")
            self.locators.append(loc)
            cmds.parent(loc, self.module_trn)

        self.eye_joint = guides_manager.get_guides(f"{self.side}_eye_JNT")
        cmds.parent(self.eye_joint[0], self.module_trn)


    def create_main_eye_setup(self):

        """
        Create the main eye setup for the eyelid module.
        """
        if self.side == "L":
            self.main_aim_nodes, self.main_aim_ctl = curve_tool.create_controller(name=f"C_eyeMain", offset=["GRP"])
            cmds.parent(self.main_aim_nodes[0], self.head_ctl)
            self.lock_attributes(self.main_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
            before_translate = cmds.xform(self.eye_joint[0], q=True, t=True, ws=True)
            cmds.setAttr(f"{self.eye_joint[0]}.tx", 0)
            cmds.matchTransform(self.main_aim_nodes[0], self.eye_joint[0])
            cmds.select(self.main_aim_nodes[0])
            cmds.move(0, 0, 10, relative=True, objectSpace=True, worldSpaceDistance=True)
            cmds.xform(self.eye_joint[0], t=before_translate, ws=True)

        side_aim_nodes, self.side_aim_ctl = curve_tool.create_controller(name=f"{self.side}_eye", offset=["GRP"])
        cmds.parent(side_aim_nodes[0], self.controllers_grp)
        cmds.matchTransform(side_aim_nodes[0], self.eye_joint[0])
        cmds.select(side_aim_nodes[0])
        cmds.move(0, 0, 10, relative=True, objectSpace=True, worldSpaceDistance=True)
        self.lock_attributes(self.side_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
        cmds.parent(side_aim_nodes[0], "C_eyeMain_CTL")

        # Aim setup
        self.eye_jnt_matrix = cmds.xform(self.eye_joint[0], q=True, m=True, ws=True)
        self.aim = cmds.createNode("aimMatrix", name=f"{self.side}_eye_AIM", ss=True)
        cmds.setAttr(f"{self.aim}.primaryInputAxis", 0, 0, 1)
        cmds.setAttr(f"{self.aim}.secondaryInputAxis", 0, 1, 0)
        cmds.setAttr(f"{self.aim}.secondaryTargetVector", 0, 1, 0)
        cmds.setAttr(f"{self.aim}.secondaryMode", 2) # Align
        cmds.setAttr(f"{self.aim}.inputMatrix", self.eye_jnt_matrix, type="matrix")
        cmds.connectAttr(f"{self.side_aim_ctl}.worldMatrix[0]", f"{self.aim}.primaryTargetMatrix")
        cmds.connectAttr(f"{self.head_ctl}.worldMatrix[0]", f"{self.aim}.secondaryTargetMatrix")
        cmds.connectAttr(f"{self.aim}.outputMatrix", f"{self.eye_joint[0]}.offsetParentMatrix")
        cmds.xform(self.eye_joint[0], m=om.MMatrix.kIdentity)

    def create_controllers(self):

        """
        Create controllers for the eyelid module.
        """

        self.upper_local_trn = []
        self.lower_local_trn = []

        self.controllers = []

        for i, loc in enumerate(self.locators):

            node, ctl = curve_tool.create_controller(name=loc.replace("_LOC", ""), offset=["GRP"])
            local_grp, local_trn = self.local(ctl)
            if "eyelidIn_" in loc or "eyelidOut_" in loc or "eyelidDown_" in loc or "eyelidUp_" in loc:
                node_01, ctl_01 = curve_tool.create_controller(name=loc.replace("_LOC", "01"), offset=["GRP"])
                local_grp_01, local_trn_01 = self.local(ctl_01)
                cmds.parent(local_grp_01, local_trn)
                cmds.parent(node_01, ctl)
            cmds.parent(node, self.controllers_grp)
            if "Up" in loc:
                self.upper_local_trn.append(local_trn)
            elif "Down" in loc:
                self.lower_local_trn.append(local_trn)
            else:
                self.upper_local_trn.append(local_trn)
                self.lower_local_trn.append(local_trn)
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"]) 
            
            cmds.matchTransform(node[0], loc)
            cmds.matchTransform(local_grp, loc)
            self.controllers.append(ctl)

        

        sel_upper = [ctl for ctl in self.upper_local_trn]
        self.upper_skinning_jnt_trn, temp = ribbon.de_boor_ribbon(cvs=sel_upper, name=f"{self.side}_eyelidUpper", aim_axis='x', up_axis='y', num_joints=18)

        sel_lower = [ctl_low for ctl_low in self.lower_local_trn]
        self.lower_skinning_jnt_trn, temp_down = ribbon.de_boor_ribbon(cvs=sel_lower, name=f"{self.side}_eyelidLower", aim_axis="x", up_axis="y", num_joints=18)

        cmds.parent(self.upper_skinning_jnt_trn, self.skeleton_grp)
        cmds.parent(self.lower_skinning_jnt_trn, self.skeleton_grp)
        cmds.delete(temp, temp_down)

    def attributes(self):

        """
        Add custom attributes to the eyelid controllers.
        """

        self.eye_direct_nodes, self.eye_direct_ctl = curve_tool.create_controller(name=f"{self.side}_eyeDirect", offset=["GRP"])
        cmds.parent(self.eye_direct_nodes[0], self.head_ctl)
        cmds.matchTransform(self.eye_direct_nodes[0], self.eye_joint[0])
        cmds.select(self.eye_direct_nodes[0])
        cmds.move(0, 0, 3, relative=True, objectSpace=True, worldSpaceDistance=True)
        self.lock_attributes(self.eye_direct_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])

        cmds.addAttr(self.eye_direct_ctl, ln="EYE_ATTRIBUTES", at="enum", en="____", k=True)
        cmds.setAttr(f"{self.eye_direct_ctl}.EYE_ATTRIBUTES", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Upper_Blink", at="float", min=0, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Lower_Blink", at="float", min=0, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Blink_Height", at="float", min=0, max=1, dv=0.6, k=True)

        # Connect the aim matrix to the eye direct controller and orient constrain the eye joint to it
        eye_direct_matrix = cmds.xform(self.eye_direct_nodes, q=True, m=True, ws=True)
        cmds.setAttr(f"{self.aim}.inputMatrix", eye_direct_matrix, type="matrix")
        cmds.connectAttr(f"{self.aim}.outputMatrix", f"{self.eye_direct_nodes[0]}.offsetParentMatrix", force=True)
        cmds.xform(self.eye_direct_nodes[0], m=om.MMatrix.kIdentity)
        cmds.setAttr(f"{self.eye_direct_nodes[0]}.inheritsTransform", 0)
        pick_matrix_rotation = cmds.createNode("pickMatrix", name=f"{self.side}_eye_PMK", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.worldMatrix[0]", f"{pick_matrix_rotation}.inputMatrix")
        cmds.setAttr(f"{pick_matrix_rotation}.useTranslate", 0)
        cmds.setAttr(f"{pick_matrix_rotation}.useScale", 0)
        cmds.connectAttr(f"{pick_matrix_rotation}.outputMatrix", f"{self.eye_joint[0]}.offsetParentMatrix", force=True)
        cmds.xform(self.eye_joint[0], m=self.eye_jnt_matrix)
        

    def create_blink_setup(self):

        """
        Create the blink setup for the eyelid module.
        """
        up_locators = [loc for loc in self.locators if "Up" in loc]
        down_locators = [loc for loc in self.locators if "Down" in loc]

        up_controllers = [ctl for ctl in self.controllers if "Up" in ctl]
        down_controllers = [ctl for ctl in self.controllers if "Down" in ctl]

        up_local_trns = [trn for trn in self.upper_local_trn if "Up" in trn]
        down_local_trns = [trn for trn in self.lower_local_trn if "Down" in trn]

        blink_locators = []

        for i in range(3):

            loc = cmds.spaceLocator(name=f"{self.side}_blink{i+1}_LOC")[0]
            cmds.parent(loc, self.module_trn)

            blend_matrix = cmds.createNode("blendMatrix", name=loc.replace("_LOC", "Blink_BMT"), ss=True) # Create blendMatrix node to blend between original position and blink position
            cmds.setAttr(f"{blend_matrix}.target[0].translateWeight", 0.6)
            cmds.setAttr(f"{blend_matrix}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].shearWeight", 0)

            cmds.connectAttr(f"{up_locators[i]}.worldMatrix[0]", f"{blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{down_locators[i]}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{blend_matrix}.target[0].translateWeight")
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{loc}.offsetParentMatrix")

            blink_locators.append(loc)

                


    def get_offset_matrix(self, child, parent):

        """
        Calculate the offset matrix between a child and parent transform in Maya.
        Args:
            child (str): The name of the child transform.
            parent (str): The name of the parent transform. 
        Returns:
            om.MMatrix: The offset matrix that transforms the child into the parent's space.
        """
        child_dag = om.MSelectionList().add(child).getDagPath(0)
        parent_dag = om.MSelectionList().add(parent).getDagPath(0)

        child_world_matrix = child_dag.inclusiveMatrix()
        parent_world_matrix = parent_dag.inclusiveMatrix()
        
        offset_matrix = child_world_matrix * parent_world_matrix.inverse()

        
        return offset_matrix
    


            

