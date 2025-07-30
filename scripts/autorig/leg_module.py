import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool

from autorig.utilities import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)

class LegModule(object):

    def __init__(self):

        """
        Initialize the LegModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the leg module structure and controllers. Call this method with the side ('L' or 'R') to create the respective leg module.
        Args:
            side (str): The side of the leg ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_legModule_GRP", ss=True, p=self.modules)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleX")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleY")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleZ")
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_legSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_legControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.foot_attributes()


    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def load_guides(self):

        self.leg_chain = guides_manager.get_guides(f"{self.side}_hip_JNT")
        cmds.parent(self.leg_chain[0], self.module_trn)
        self.settings_loc = guides_manager.get_guides(f"{self.side}_legSettings_LOCShape")
        self.bank_out_loc = guides_manager.get_guides(f"{self.side}_bankOut_LOCShape")
        self.bank_in_loc = guides_manager.get_guides(f"{self.side}_bankIn_LOCShape")
        self.heel_loc = guides_manager.get_guides(f"{self.side}_heel_LOCShape")


    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_legSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        self.pair_blends = []
        self.fk_chain = []
        self.ik_chain = []

        for joint in self.leg_chain:

            pair_blend = cmds.createNode("pairBlend", name=joint.replace("JNT", "PBL"), ss=True)
            cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{pair_blend}.weight")

            cmds.select(clear=True)
            fk_joint = cmds.joint(name=joint.replace("_JNT", "Fk_JNT"))
            cmds.makeIdentity(fk_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)
            cmds.parent(fk_joint, self.module_trn)

            cmds.select(clear=True)
            ik_joint = cmds.joint(name=joint.replace("_JNT", "Ik_JNT"))
            cmds.matchTransform(ik_joint, joint, pos=True, rot=True)
            cmds.makeIdentity(ik_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)

            if self.ik_chain:
                cmds.parent(ik_joint, self.ik_chain[-1])

            self.fk_chain.append(fk_joint)
            self.ik_chain.append(ik_joint)
            self.pair_blends.append(pair_blend)

            cmds.connectAttr(f"{fk_joint}.translate", f"{pair_blend}.inTranslate2")
            cmds.connectAttr(f"{ik_joint}.translate", f"{pair_blend}.inTranslate1")
            cmds.connectAttr(f"{fk_joint}.rotate", f"{pair_blend}.inRotate2")
            cmds.connectAttr(f"{ik_joint}.rotate", f"{pair_blend}.inRotate1")
            cmds.connectAttr(f"{pair_blend}.outTranslate", f"{joint}.translate")
            cmds.connectAttr(f"{pair_blend}.outRotate", f"{joint}.rotate")

        cmds.parent(self.ik_chain[0], self.module_trn)

    def controllers_creation(self):

        """
        Create controllers for the leg module.
        """
        self.fk_nodes = []
        self.fk_controllers = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_legFkControllers_GRP", ss=True, p=self.controllers_grp)
        

        for i, joint in enumerate(self.fk_chain):

            fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", ""), offset=["GRP"]) # create FK controllers
            self.lock_attributes(fk_ctl, ["translateX", "translateY", "translateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
            
            cmds.matchTransform(fk_node[0], self.leg_chain[i], pos=True, rot=True)

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            if i == 0:
                matrix_manager.fk_constraint(joint, "None", self.pair_blends[i])
            else:
                matrix_manager.fk_constraint(joint, self.fk_chain[i-1], self.pair_blends[i])

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)

        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_legIkControllers_GRP", ss=True, p=self.controllers_grp)
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_legIkFkReverse", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{ik_controllers_trn}.visibility")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{fk_controllers_trn}.visibility")
        
        ik_controller_dict = {

            "ankleIk": self.leg_chain[2],
            "bankOut": self.bank_out_loc,
            "bankIn": self.bank_in_loc,
            "heel": self.heel_loc,
            "ballIk": self.leg_chain[3],
            "toeIk": self.leg_chain[4]
        }

        self.ik_nodes = []
        self.ik_sdk_nodes = []
        self.ik_controllers = []

        for name, guide in ik_controller_dict.items():

            ik_node, ik_ctl = curve_tool.create_controller(name=f"{self.side}_{name}", offset=["GRP", "SDK"])
            self.lock_attributes(ik_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])

            cmds.matchTransform(ik_node[0], guide, pos=True, rot=True)
            child = cmds.listRelatives(guide, children=True, type="locator")
            if child:
                    cmds.delete(guide) # Delete the locator guide

            if self.ik_controllers:
                cmds.parent(ik_node[0], self.ik_controllers[-1])
            self.ik_nodes.append(ik_node[0])
            self.ik_sdk_nodes.append(ik_node[1])
            self.ik_controllers.append(ik_ctl)

        cmds.parent(self.ik_nodes[0], ik_controllers_trn)

        self.root_ik_nodes, self.root_ik_ctl = curve_tool.create_controller(name=f"{self.side}_legRootIk", offset=["GRP"])
        self.lock_attributes(self.root_ik_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.matchTransform(self.root_ik_nodes[0], self.leg_chain[0], pos=True, rot=True)
        cmds.parentConstraint(self.root_ik_ctl, self.ik_chain[0], maintainOffset=True)
        cmds.parent(self.root_ik_nodes[0], ik_controllers_trn)

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_legPv", offset=["GRP"])
        self.lock_attributes(self.pv_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        cmds.matchTransform(self.pv_nodes[0], self.leg_chain[1], pos=True, rot=True)
        
        cmds.select(self.pv_nodes[0])
        if self.side == "L":
            cmds.move(0, -20, 0, relative=True, objectSpace=True, worldSpaceDistance=True)
        else:
            cmds.move(0, 20, 0, relative=True, objectSpace=True, worldSpaceDistance=True)

        
    def ik_setup(self):

        """
        Set up the IK handle for the leg module.
        """
        ik_handle = cmds.ikHandle(name=f"{self.side}_legIk_HDL", startJoint=self.ik_chain[0], endEffector=self.ik_chain[-3], solver="ikRPsolver")[0]
        ball_handle = cmds.ikHandle(name=f"{self.side}_ballIk_HDL", startJoint=self.ik_chain[-3], endEffector=self.ik_chain[-2], solver="ikSCsolver")[0]
        toe_handle = cmds.ikHandle(name=f"{self.side}_toeIk_HDL", startJoint=self.ik_chain[-2], endEffector=self.ik_chain[-1], solver="ikSCsolver")[0]
        cmds.parent(ik_handle, self.module_trn)
        cmds.parent(ball_handle, self.module_trn)
        cmds.parent(toe_handle, self.module_trn)

        cmds.connectAttr(f"{self.ik_controllers[-2]}.worldMatrix[0]", f"{ik_handle}.offsetParentMatrix") # If it doesnt work change for parentConstraint
        cmds.xform(ik_handle, t=(0, 0, 0), ro=(0, 0, 0))
        # cmds.parentConstraint(self.ik_controllers[-2], ik_handle, maintainOffset=True)

        cmds.connectAttr(f"{self.ik_controllers[-2]}.worldMatrix[0]", f"{ball_handle}.offsetParentMatrix") # If it doesnt work change for parentConstraint
        cmds.xform(ball_handle, t=(0, 0, 0), ro=(0, 0, 0))

        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{toe_handle}.offsetParentMatrix") # If it doesnt work change for parentConstraint
        cmds.xform(toe_handle, t=(0, 0, 0), ro=(0, 0, 0))
        cmds.poleVectorConstraint(self.pv_ctl, ik_handle)

    def foot_attributes(self):

        """
        Add foot attributes to the leg module.
        """
        cmds.addAttr(self.ik_controllers[0], longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
        cmds.setAttr(f"{self.ik_controllers[0]}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
        
        attr_list = [
            "Ankle_Twist",
            "Ball_Twist",
            "Toe_Twist",
            "Heel_Twist",
            "Bank",
            "Roll"
        ]

        for attr in attr_list:
            cmds.addAttr(self.ik_controllers[0], longName=attr, attributeType="float", defaultValue=0, keyable=True)
        
        cmds.addAttr(self.ik_controllers[0], longName="Roll_Break_Angle", attributeType="float", defaultValue=45, keyable=True)
        cmds.addAttr(self.ik_controllers[0], longName="Roll_Straight_Angle", attributeType="float", defaultValue=90, keyable=True)

        cmds.connectAttr(f"{self.ik_controllers[0]}.Ankle_Twist", f"{self.ik_sdk_nodes[0]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Ball_Twist", f"{self.ik_sdk_nodes[-2]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Toe_Twist", f"{self.ik_sdk_nodes[-1]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Heel_Twist", f"{self.ik_sdk_nodes[-3]}.rotateY")
        bank_clamp = cmds.createNode("clamp", name=f"{self.side}_legBank_CLM", ss=True)
        cmds.setAttr(f"{bank_clamp}.minG", -360)
        cmds.setAttr(f"{bank_clamp}.maxR", 360)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Bank", f"{bank_clamp}.inputR")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Bank", f"{bank_clamp}.inputG")
        if self.side == "L":
            cmds.connectAttr(f"{bank_clamp}.outputG", f"{self.ik_sdk_nodes[1]}.rotateZ")
            cmds.connectAttr(f"{bank_clamp}.outputR", f"{self.ik_sdk_nodes[2]}.rotateZ")
        else:
            cmds.connectAttr(f"{bank_clamp}.outputG", f"{self.ik_sdk_nodes[2]}.rotateZ")
            cmds.connectAttr(f"{bank_clamp}.outputR", f"{self.ik_sdk_nodes[1]}.rotateZ")

        roll_straight_angle = cmds.createNode("remapValue", name=f"{self.side}_legRollStraightAngle_RMV", ss=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_straight_angle}.inputValue")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Straight_Angle", f"{roll_straight_angle}.inputMax")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Break_Angle", f"{roll_straight_angle}.inputMin")
        cmds.setAttr(f"{roll_straight_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_straight_angle}.outputMax", 1)

        multiply_divide_node = cmds.createNode("multiplyDivide", name=f"{self.side}_legRollStraightAngle_MDV", ss=True)
        cmds.setAttr(f"{multiply_divide_node}.operation", 1)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{multiply_divide_node}.input1X")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{multiply_divide_node}.input2X")
        cmds.connectAttr(f"{multiply_divide_node}.outputX", f"{self.ik_sdk_nodes[-1]}.rotateX")

        roll_break_angle = cmds.createNode("remapValue", name=f"{self.side}_legRollBreakAngle_RMV", ss=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_break_angle}.inputValue")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Break_Angle", f"{roll_break_angle}.inputMax")
        cmds.setAttr(f"{roll_break_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_break_angle}.outputMax", 1)

        reverse = cmds.createNode("reverse", name=f"{self.side}_legRollBreakAngle_REV", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{reverse}.inputX")

        roll_angle_enable_mdv = cmds.createNode("multiplyDivide", name=f"{self.side}_legRollAngleEnable_MDV", ss=True)
        cmds.setAttr(f"{roll_angle_enable_mdv}.operation", 1)
        cmds.connectAttr(f"{reverse}.outputX", f"{roll_angle_enable_mdv}.input1X")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_angle_enable_mdv}.input2X")

        roll_lift_angle_mdv = cmds.createNode("multiplyDivide", name=f"{self.side}_legRollLiftAngle_MDV", ss=True)
        cmds.setAttr(f"{roll_lift_angle_mdv}.operation", 1)
        cmds.connectAttr(f"{roll_break_angle}.outValue", f"{roll_lift_angle_mdv}.input1X")
        cmds.connectAttr(f"{roll_angle_enable_mdv}.outputX", f"{roll_lift_angle_mdv}.input2X")
        cmds.connectAttr(f"{roll_lift_angle_mdv}.outputX", f"{self.ik_sdk_nodes[-2]}.rotateX")
