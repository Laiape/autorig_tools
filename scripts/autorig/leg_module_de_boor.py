import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool

from autorig.utilities import matrix_manager
from autorig.utilities import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)
reload(ribbon)

class LegModule(object):

    def __init__(self):

        """
        Initialize the LegModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")
        self.local_hip_ctl = data_manager.DataExport().get_data("spine_module", "local_hip_ctl")

    def make(self, side):

        """ 
        Create the leg module structure and controllers. Call this method with the side ('L' or 'R') to create the respective leg module.
        Args:
            side (str): The side of the leg ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_leg"
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_legModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_legSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_legControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.foot_attributes()
        self.fk_stretch()
        self.soft_ik()
        self.de_boor_ribbon()

        # cmds.parent(self.controllers_grp, self.local_hip_ctl)

        data_manager.DataExport().append_data("leg_module",
                            {
                                f"{self.side}_hip_JNT": self.leg_chain[0],
                                f"{self.side}_knee_JNT": self.leg_chain[1],
                                f"{self.side}_ankle_JNT": self.leg_chain[2],
                                f"{self.side}_legIk": self.ik_controllers[0],
                                f"{self.side}_hipFk": self.fk_controllers[0],
                                f"{self.side}_legPv": self.pv_ctl,
                            })

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

            if self.fk_chain:
                cmds.parent(fk_joint, self.fk_chain[-1])    

            self.fk_chain.append(fk_joint)
            self.ik_chain.append(ik_joint)

        cmds.parent(self.ik_chain[0], self.module_trn)

    def controllers_creation(self):

        """
        Create controllers for the leg module.
        """
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

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
                blend_matrix = matrix_manager.fk_constraint(joint, None, True, self.settings_ctl)
            else:
                blend_matrix = matrix_manager.fk_constraint(joint, self.fk_chain[i-1], True, self.settings_ctl)

            self.blend_matrices.append(blend_matrix)

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
            "toeIk": self.leg_chain[4],
            "ballIk": self.leg_chain[3]
            
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
        cmds.xform(self.ik_chain[0], m=om.MMatrix.kIdentity)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{self.ik_chain[0]}.offsetParentMatrix")
        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.ik_chain[0]}.{attr}{axis}", 0)
                cmds.setAttr(f"{self.leg_chain[0]}.{attr}{axis}", 0)

        cmds.parent(self.root_ik_nodes[0], ik_controllers_trn)

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_legPv", offset=["GRP"])
        self.lock_attributes(self.pv_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        cmds.matchTransform(self.pv_nodes[0], self.leg_chain[1], pos=True, rot=True)
        
        cmds.select(self.pv_nodes[0])
        if self.side == "L":
            cmds.move(0, 30, 0, relative=True, objectSpace=True, worldSpaceDistance=True)
        else:
            cmds.move(0, -30, 0, relative=True, objectSpace=True, worldSpaceDistance=True)

        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_legPv_CRV") # Create a line that points always to the PV
        decompose_knee = cmds.createNode("decomposeMatrix", name=f"{self.side}_legPv_DCM", ss=True)
        decompose_ctl = cmds.createNode("decomposeMatrix", name=f"{self.side}_legPvCtl_DCM", ss=True)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{decompose_ctl}.inputMatrix")
        cmds.connectAttr(f"{self.leg_chain[1]}.worldMatrix[0]", f"{decompose_knee}.inputMatrix")
        cmds.connectAttr(f"{decompose_knee}.outputTranslate", f"{crv_point_pv}.controlPoints[0]")
        cmds.connectAttr(f"{decompose_ctl}.outputTranslate", f"{crv_point_pv}.controlPoints[1]")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)
        cmds.parent(crv_point_pv, self.pv_ctl)

        
    def ik_setup(self):

        """
        Set up the IK handle for the leg module.
        """
        self.ik_handle = cmds.ikHandle(name=f"{self.side}_legIk_HDL", startJoint=self.ik_chain[0], endEffector=self.ik_chain[-3], solver="ikRPsolver")[0]
        self.ball_handle = cmds.ikHandle(name=f"{self.side}_ballIk_HDL", startJoint=self.ik_chain[-3], endEffector=self.ik_chain[-2], solver="ikSCsolver")[0]
        self.toe_handle = cmds.ikHandle(name=f"{self.side}_toeIk_HDL", startJoint=self.ik_chain[-2], endEffector=self.ik_chain[-1], solver="ikSCsolver")[0]
        cmds.parent(self.ik_handle, self.module_trn)
        cmds.parent(self.ball_handle, self.module_trn)
        cmds.parent(self.toe_handle, self.module_trn)

        mult_matrix = cmds.createNode("multMatrix", name=f"{self.side}_legIkMultMatrix_MTX", ss=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{self.ik_nodes[-1]}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[2]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{self.ik_handle}.offsetParentMatrix")


        freeze_float_constant = cmds.createNode("floatConstant", name=f"{self.side}_freeze_FCF", ss=True)
        cmds.setAttr(f"{freeze_float_constant}.inFloat", 0)
        for attr in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
            cmds.connectAttr(f"{freeze_float_constant}.outFloat", f"{self.ik_handle}.{attr}")

        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{self.ball_handle}.offsetParentMatrix") # If it doesnt work change for parentConstraint
        cmds.xform(self.ball_handle, t=(0, 0, 0), ro=(0, 0, 0))

        cmds.connectAttr(f"{self.ik_controllers[-2]}.worldMatrix[0]", f"{self.toe_handle}.offsetParentMatrix") # If it doesnt work change for parentConstraint
        cmds.xform(self.toe_handle, t=(0, 0, 0), ro=(0, 0, 0))
        cmds.poleVectorConstraint(self.pv_ctl, self.ik_handle)

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
        cmds.connectAttr(f"{multiply_divide_node}.outputX", f"{self.ik_sdk_nodes[-2]}.rotateX")

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
        cmds.connectAttr(f"{roll_lift_angle_mdv}.outputX", f"{self.ik_sdk_nodes[-1]}.rotateX")

    def fk_stretch(self):

        """
        Setup FK stretch for the leg module.
        """

        for ctl in self.fk_controllers:
            cmds.setAttr(f"{ctl}.translateX", lock=False)
            cmds.addAttr(ctl, shortName="STRETCHY", attributeType="enum", enumName="____", keyable=True)
            cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True)
            cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

        self.upper_double_mult_linear = cmds.createNode("multDoubleLinear", n=f"{self.side}_legUpperDoubleMultLinear_MDL")
        self.lower_double_mult_linear = cmds.createNode("multDoubleLinear", n=f"{self.side}_legLowerDoubleMultLinear_MDL")
        cmds.connectAttr(f"{self.fk_controllers[0]}.Stretch", f"{self.upper_double_mult_linear}.input1")
        cmds.connectAttr(f"{self.fk_controllers[1]}.Stretch", f"{self.lower_double_mult_linear}.input1")

        upper_distance = cmds.getAttr(f"{self.fk_nodes[1]}.translateX")
        lower_distance = cmds.getAttr(f"{self.fk_nodes[-1]}.translateX")

        cmds.setAttr(f"{self.upper_double_mult_linear}.input2", upper_distance)
        cmds.setAttr(f"{self.lower_double_mult_linear}.input2", lower_distance)
        cmds.connectAttr(f"{self.upper_double_mult_linear}.output", f"{self.fk_nodes[1]}.translateX")
        cmds.connectAttr(f"{self.lower_double_mult_linear}.output", f"{self.fk_nodes[-1]}.translateX")

    def soft_ik(self):

        """
        Setup soft IK for the leg module.
        """

        # --- Stretchy IK Controllers ---
        cmds.addAttr(self.ik_controllers[0], shortName="STRETCHY____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.STRETCHY____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_controllers[0], shortName="upperLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="lowerLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="Stretch", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="SOFT____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.SOFT____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_controllers[0], shortName="Soft", minValue=0, defaultValue=0, maxValue=1, keyable=True)

        # Calculate full_length and initial_distance using vector positions
        start_pos = om.MVector(cmds.xform(self.ik_chain[0], q=True, ws=True, t=True))
        mid_pos = om.MVector(cmds.xform(self.ik_chain[1], q=True, ws=True, t=True))
        end_pos = om.MVector(cmds.xform(self.ik_chain[2], q=True, ws=True, t=True))

        upper_length = (mid_pos - start_pos).length()
        lower_length = (end_pos - mid_pos).length()
        full_length = upper_length + lower_length
        initial_distance = (end_pos - start_pos).length()
        soft_distance = full_length - initial_distance

        # Create the soft IK handle TRN and do a parentMatrix to the last IK controller
        child_dag = om.MSelectionList().add(self.ik_controllers[0]).getDagPath(0)
        parent_dag = om.MSelectionList().add(self.ik_controllers[-1]).getDagPath(0)

        child_world_matrix = child_dag.inclusiveMatrix()
        parent_world_matrix = parent_dag.inclusiveMatrix()  

        offset_matrix = child_world_matrix * parent_world_matrix.inverse()

        soft_ik_handle = cmds.createNode("transform", name=f"{self.side}_legIkHandleManager_TRN", ss=True, p=self.module_trn)
        parent_matrix = cmds.createNode("parentMatrix", name=f"{self.side}_legSoftIkHDL_PM", ss=True)
        ankle_wM = cmds.getAttr(f"{self.ik_controllers[0]}.worldMatrix[0]")
        cmds.setAttr(f"{parent_matrix}.inputMatrix", ankle_wM, type="matrix")
        cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", offset_matrix, type="matrix")
        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{soft_ik_handle}.offsetParentMatrix")

        self.soft_off = cmds.createNode("transform", name=f"{self.side}_legSoft_OFF", p=self.module_trn)
        aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_legSoftOff_AMT", ss=True)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{aim_matrix}.inputMatrix")
        cmds.connectAttr(f"{soft_ik_handle}.worldMatrix[0]", f"{aim_matrix}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{aim_matrix}.primaryInputAxisX", 1)
        cmds.setAttr(f"{aim_matrix}.primaryInputAxisY", 0)
        cmds.setAttr(f"{aim_matrix}.primaryInputAxisZ", 0)
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxisX", 0)
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxisY", 1)
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxisZ", 0)
        cmds.setAttr(f"{aim_matrix}.primaryMode", 1)
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{self.soft_off}.offsetParentMatrix")

        self.soft_trn = cmds.createNode("transform", name=f"{self.side}_legSoft_TRN", p=self.soft_off)
        cmds.matchTransform(self.soft_trn, self.leg_chain[2], pos=True)

        nodes_to_create = {
        f"{self.side}_legDistanceToControl_DBT": ("distanceBetween", None),  # 0
        f"{self.side}_legDistanceToControlNormalized_FLM": ("floatMath", 3),  # 1
        f"{self.side}_legSoftValue_RMV": ("remapValue", None),  # 2
        f"{self.side}_legDistanceToControlMinusSoftDistance_FLM": ("floatMath", 1),  # 3
        f"{self.side}_legUpperLength_FLM": ("floatMath", 2),  # 4
        f"{self.side}_legDistanceToControlMinusSoftDistanceDividedBySoftValue_FLM": ("floatMath", 3),  # 5
        f"{self.side}_legFullLength_FLM": ("floatMath", 0),  # 6
        f"{self.side}_legDistanceToControlMinusSoftDistanceDividedBySoftValueNegate_FLM": ("floatMath", 2),  # 7
        f"{self.side}_legSoftDistance_FLM": ("floatMath", 1),  # 8
        f"{self.side}_legSoftEPower_FLM": ("floatMath", 6),  # 9
        f"{self.side}_legLowerLength_FLM": ("floatMath", 2),  # 10
        f"{self.side}_legSoftOneMinusEPower_FLM": ("floatMath", 1),  # 11
        f"{self.side}_legSoftOneMinusEPowerSoftValueEnable_FLM": ("floatMath", 2),  # 12
        f"{self.side}_legSoftConstant_FLM": ("floatMath", 0),  # 13
        f"{self.side}_legLengthRatio_FLM": ("floatMath", 3),  # 14
        f"{self.side}_legSoftRatio_FLM": ("floatMath", 3),  # 15
        f"{self.side}_legDistanceToControlDividedByTheLengthRatio_FLM": ("floatMath", 3),  # 16
        f"{self.side}_legSoftEffectorDistance_FLM": ("floatMath", 2),  # 17
        f"{self.side}_legSoftCondition_CON": ("condition", None),  # 18
        f"{self.side}_legUpperLengthStretch_FLM": ("floatMath", 2),  # 19
        f"{self.side}_legDistanceToControlDividedByTheSoftEffector_FLM": ("floatMath", 3),  # 20
        f"{self.side}_legDistanceToControlDividedByTheSoftEffectorMinusOne_FLM": ("floatMath", 1),  # 21
        f"{self.side}_legDistanceToControlDividedByTheSoftEffectorMinusOneMultipliedByTheStretch_FLM": ("floatMath", 2),  # 22
        f"{self.side}_legStretchFactor_FLM": ("floatMath", 0),  # 23
        f"{self.side}_legSoftEffectStretchDistance_FLM": ("floatMath", 2),  # 24
        f"{self.side}_legLowerLengthStretch_FLM": ("floatMath", 2),  # 25
        }

        self.created_nodes = []
        for node_name, (node_type, operation) in nodes_to_create.items():
            node = cmds.createNode(node_type, name=node_name)
            self.created_nodes.append(node)
            if operation is not None:
                cmds.setAttr(f'{node}.operation', operation)

        # Connections between selected nodes
        cmds.connectAttr(self.created_nodes[0] + ".distance", self.created_nodes[1]+".floatA")
        cmds.connectAttr(self.created_nodes[1] + ".outFloat", self.created_nodes[14]+".floatA")
        cmds.connectAttr(self.created_nodes[1] + ".outFloat", self.created_nodes[3]+".floatA")
        cmds.connectAttr(self.created_nodes[1] + ".outFloat", self.created_nodes[16]+".floatA")
        cmds.connectAttr(self.created_nodes[1] + ".outFloat", self.created_nodes[18]+".firstTerm")
        cmds.connectAttr(self.created_nodes[1] + ".outFloat", self.created_nodes[18]+".colorIfFalseR")
        cmds.connectAttr(self.created_nodes[1] + ".outFloat", self.created_nodes[20]+".floatA")
        cmds.connectAttr(self.created_nodes[2] + ".outValue", self.created_nodes[5]+".floatB")
        cmds.connectAttr(self.created_nodes[2] + ".outValue", self.created_nodes[8]+".floatB")
        cmds.connectAttr(self.created_nodes[2] + ".outValue", self.created_nodes[12]+".floatA")
        cmds.connectAttr(self.created_nodes[3] + ".outFloat", self.created_nodes[5]+".floatA")
        cmds.connectAttr(self.created_nodes[8] + ".outFloat", self.created_nodes[3]+".floatB")
        cmds.connectAttr(self.created_nodes[4] + ".outFloat", self.created_nodes[18]+".colorIfFalseG")
        cmds.connectAttr(self.created_nodes[4] + ".outFloat", self.created_nodes[6]+".floatA")
        cmds.connectAttr(self.created_nodes[4] + ".outFloat", self.created_nodes[19]+".floatB")
        cmds.connectAttr(self.created_nodes[5] + ".outFloat", self.created_nodes[7]+".floatA")
        cmds.connectAttr(self.created_nodes[6] + ".outFloat", self.created_nodes[15]+".floatB")
        cmds.connectAttr(self.created_nodes[6] + ".outFloat", self.created_nodes[8]+".floatA")
        cmds.connectAttr(self.created_nodes[6] + ".outFloat", self.created_nodes[14]+".floatB")
        cmds.connectAttr(self.created_nodes[10] + ".outFloat", self.created_nodes[6]+".floatB")
        cmds.connectAttr(self.created_nodes[7] + ".outFloat", self.created_nodes[9]+".floatB")
        cmds.connectAttr(self.created_nodes[8] + ".outFloat", self.created_nodes[13]+".floatB")
        cmds.connectAttr(self.created_nodes[8] + ".outFloat", self.created_nodes[18]+".secondTerm")
        cmds.connectAttr(self.created_nodes[9] + ".outFloat", self.created_nodes[11]+".floatB")
        cmds.connectAttr(self.created_nodes[10] + ".outFloat", self.created_nodes[18]+".colorIfFalseB")
        cmds.connectAttr(self.created_nodes[10] + ".outFloat", self.created_nodes[25]+".floatB")
        cmds.connectAttr(self.created_nodes[11] + ".outFloat", self.created_nodes[12]+".floatB")
        cmds.connectAttr(self.created_nodes[12] + ".outFloat", self.created_nodes[13]+".floatA")
        cmds.connectAttr(self.created_nodes[13] + ".outFloat", self.created_nodes[15]+".floatA")
        cmds.connectAttr(self.created_nodes[14] + ".outFloat", self.created_nodes[16]+".floatB")
        cmds.connectAttr(self.created_nodes[15] + ".outFloat", self.created_nodes[17]+".floatA")
        cmds.connectAttr(self.created_nodes[16] + ".outFloat", self.created_nodes[17]+".floatB")
        cmds.connectAttr(self.created_nodes[17] + ".outFloat", self.created_nodes[24]+".floatA")
        cmds.connectAttr(self.created_nodes[17] + ".outFloat", self.created_nodes[20]+".floatB")
        cmds.connectAttr(self.created_nodes[24] + ".outFloat", self.created_nodes[18]+".colorIfTrueR")
        cmds.connectAttr(self.created_nodes[19] + ".outFloat", self.created_nodes[18]+".colorIfTrueG")
        cmds.connectAttr(self.created_nodes[25] + ".outFloat", self.created_nodes[18]+".colorIfTrueB")
        cmds.connectAttr(self.created_nodes[23] + ".outFloat", self.created_nodes[19]+".floatA")
        cmds.connectAttr(self.created_nodes[20] + ".outFloat", self.created_nodes[21]+".floatA")
        cmds.connectAttr(self.created_nodes[21] + ".outFloat", self.created_nodes[22]+".floatA")
        cmds.connectAttr(self.created_nodes[22] + ".outFloat", self.created_nodes[23]+".floatA")
        cmds.connectAttr(self.created_nodes[23] + ".outFloat", self.created_nodes[24]+".floatB")
        cmds.connectAttr(self.created_nodes[23] + ".outFloat", self.created_nodes[25]+".floatA")

        cmds.setAttr(f"{self.created_nodes[9]}.floatA", math.e)
        cmds.setAttr(f"{self.created_nodes[4]}.floatB", abs(cmds.getAttr(f"{self.ik_chain[1]}.translateX")))
        cmds.setAttr(f"{self.created_nodes[10]}.floatB", abs(cmds.getAttr(f"{self.ik_chain[2]}.translateX")))
        cmds.setAttr(f"{self.created_nodes[2]}.outputMin", 0.001)
        cmds.setAttr(f"{self.created_nodes[2]}.outputMax", soft_distance)
        cmds.setAttr(f"{self.created_nodes[7]}.floatB", -1.0)
        cmds.setAttr(f"{self.created_nodes[18]}.operation", 2)

        cmds.connectAttr(f"{self.ik_controllers[0]}.upperLengthMult", f"{self.created_nodes[4]}.floatA")
        cmds.connectAttr(f"{self.ik_controllers[0]}.lowerLengthMult", f"{self.created_nodes[10]}.floatA")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Stretch", f"{self.created_nodes[22]}.floatB")
        cmds.connectAttr(f"{soft_ik_handle}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix2")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Soft", f"{self.created_nodes[2]}.inputValue")

        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.created_nodes[1]}.floatB")

        cmds.connectAttr(f"{self.created_nodes[18]}.outColorR", f"{self.soft_trn}.translateX")
        if self.side == "L":
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{self.ik_chain[1]}.translateX")
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{self.ik_chain[2]}.translateX")
        else:
            abs_up = cmds.createNode("floatMath", n=f"{self.side}_legAbsUpper_FLM")
            abs_low = cmds.createNode("floatMath", n=f"{self.side}_legAbsLower_FLM")
            cmds.setAttr(f"{abs_up}.operation", 2)
            cmds.setAttr(f"{abs_low}.operation", 2)
            cmds.setAttr(f"{abs_up}.floatB", -1)
            cmds.setAttr(f"{abs_low}.floatB", -1)
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{abs_up}.floatA")
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{abs_low}.floatA")
            cmds.connectAttr(f"{abs_up}.outFloat", f"{self.ik_chain[1]}.translateX")
            cmds.connectAttr(f"{abs_low}.outFloat", f"{self.ik_chain[2]}.translateX")

        cmds.connectAttr(f"{self.soft_trn}.worldMatrix[0]", f"{self.ik_handle}.offsetParentMatrix", force=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.rotate", f"{self.ik_chain[2]}.rotate")
        cmds.connectAttr(f"{self.ik_controllers[0]}.rotate", f"{self.ik_chain[1]}.rotate")
        
    def de_boor_ribbon(self):

        """
        Create a de Boor ribbon setup.
        """

        
        temp_trn = [cmds.createNode("transform", name=f"{self.side}_legLowBendyTemp_TRN", ss=True, p=self.module_trn)]
        cmds.matchTransform(temp_trn[0], self.leg_chain[2], pos=True)
        aim = cmds.aimConstraint(self.leg_chain[-2], temp_trn[0], aimVector=(1, 0, 0), upVector=(0, 1, 0), worldUpType="scene")
        cmds.delete(aim)


        # Placeholder for de Boor ribbon setup
        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[0], self.blend_matrices[1], "Upper")
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], temp_trn, "Lower")

        trn_outputs = cmds.listConnections(f"{temp_trn[0]}.worldMatrix[0]", destination=True, plugs=True)
        for output in trn_outputs:
            cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", output, force=True)

        cmds.select(clear=True)
        ball_skinning_jnt = cmds.joint(name=f"{self.module_name}BallSkinning_JNT")
        cmds.connectAttr(f"{self.leg_chain[-2]}.worldMatrix[0]", f"{ball_skinning_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        ankle_skinning_jnt = cmds.joint(name=f"{self.module_name}AnkleSkinning_JNT")
        cmds.connectAttr(f"{self.leg_chain[-3]}.worldMatrix[0]", f"{ankle_skinning_jnt}.offsetParentMatrix")
        cmds.parent(ankle_skinning_jnt, self.skeleton_grp)
        cmds.parent(ball_skinning_jnt, self.skeleton_grp)

    def de_boor_ribbon_callout(self, first_sel, second_sel, part):

        if cmds.objExists(f"{first_sel[0]}.outputMatrix"):
            first_sel_output = f"{first_sel[0]}.outputMatrix"
        elif cmds.objExists(f"{first_sel[0]}.worldMatrix[0]"):
            first_sel_output = f"{first_sel[0]}.worldMatrix[0]"

        if cmds.objExists(f"{second_sel[0]}.outputMatrix"):
            second_sel_output = f"{second_sel[0]}.outputMatrix"
        elif cmds.objExists(f"{second_sel[0]}.worldMatrix[0]"):
            second_sel_output = f"{second_sel[0]}.worldMatrix[0]"

        main_bendy_nodes, main_bendy_ctl = curve_tool.create_controller(name=f"{self.module_name}{part}MainBendy", offset=["GRP"])
        up_bendy_nodes, up_bendy_ctl = curve_tool.create_controller(name=f"{self.module_name}{part}UpBendy", offset=["GRP"])
        low_bendy_nodes, low_bendy_ctl = curve_tool.create_controller(name=f"{self.module_name}{part}LowBendy", offset=["GRP"])

        for node in [main_bendy_nodes[0], up_bendy_nodes[0], low_bendy_nodes[0]]:

            cmds.parent(node, self.controllers_grp)
            cmds.setAttr(f"{node}.inheritsTransform", 0)

        blend_matrix_main = cmds.createNode("blendMatrix", name=f"{self.side}_{part}MainBendy_BM", ss=True)
        cmds.connectAttr(first_sel_output, f"{blend_matrix_main}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{blend_matrix_main}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_main}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_main}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_main}.target[0].shearWeight", 0)
        cmds.setAttr(f"{blend_matrix_main}.target[0].translateWeight", 0.5)
        cmds.connectAttr(f"{blend_matrix_main}.outputMatrix", f"{main_bendy_nodes[0]}.offsetParentMatrix")


        for i, ctl in enumerate([main_bendy_ctl, up_bendy_ctl, low_bendy_ctl]):

            self.lock_attributes(ctl, ["visibility"])

            cmds.addAttr(ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
            cmds.setAttr(f"{ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
            cmds.addAttr(ctl, longName="Bendy_Height", attributeType="float", minValue=0, defaultValue=0.5, maxValue=1, keyable=True)

            if i == 0:

                cmds.addAttr(ctl, longName="Extra_Bendys", attributeType="bool", keyable=False)
                cmds.setAttr(f"{ctl}.Extra_Bendys", channelBox=True)

        cmds.connectAttr(f"{main_bendy_ctl}.Bendy_Height", f"{blend_matrix_main}.target[0].translateWeight") # Connect Bendy_Height to blend_matrix_main
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Bendys", f"{up_bendy_nodes[0]}.visibility")
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Bendys", f"{low_bendy_nodes[0]}.visibility")

        for i, node in enumerate([up_bendy_nodes[0], low_bendy_nodes[0]]): # Create blend matrices for up and low bendy nodes

            blend_matrix = cmds.createNode("blendMatrix", name=node.replace("GRP", "BMX"), ss=True)

            if i == 0:
                if "Upper" in node:
                    cmds.connectAttr(f"{self.leg_chain[0]}.worldMatrix[0]", f"{blend_matrix}.inputMatrix")
                elif "Lower" in node:
                    cmds.connectAttr(f"{self.leg_chain[1]}.worldMatrix[0]", f"{blend_matrix}.inputMatrix")
                cmds.connectAttr(f"{main_bendy_ctl}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
                cmds.connectAttr(f"{up_bendy_ctl}.Bendy_Height", f"{blend_matrix}.target[0].translateWeight")

            elif i == 1:
                cmds.connectAttr(f"{main_bendy_ctl}.worldMatrix[0]", f"{blend_matrix}.inputMatrix")

                if "Upper" in node:
                    cmds.connectAttr(f"{self.leg_chain[1]}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
                elif "Lower" in node:
                    cmds.connectAttr(f"{self.leg_chain[2]}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
                
                cmds.connectAttr(f"{low_bendy_ctl}.Bendy_Height", f"{blend_matrix}.target[0].translateWeight")


            cmds.setAttr(f"{blend_matrix}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].shearWeight", 0)
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{node}.offsetParentMatrix")

        

        sel = (first_sel[0], up_bendy_ctl, main_bendy_ctl, low_bendy_ctl, second_sel[0])

        params = [i / (len(sel) - 1) for i in range(len(sel))] # Custom parameter to place the last joint in the 0.95 position
        params[-1] = 0.95

        if self.side == "L":
            self.skinning_jnt_trn, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis='x', up_axis='y') # Call the ribbon script to create de Boors system
        elif self.side == "R":
            self.skinning_jnt_trn, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis='-x', up_axis='y')

        cmds.parent(self.skinning_jnt_trn, self.skeleton_grp)

        for t in temp:
            cmds.delete(t)

        