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

class ArmModule(object):

    def __init__(self):

        """
        Initialize the ArmModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the arm module structure and controllers. Call this method with the side ('L' or 'R') to create the respective arm module.
        Args:
            side (str): The side of the arm ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_armModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_armSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_armControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.fk_stretch()
        self.soft_ik()

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

        self.arm_chain = guides_manager.get_guides(f"{self.side}_shoulder_JNT")
        cmds.parent(self.arm_chain[0], self.module_trn)
        self.settings_loc = guides_manager.get_guides(f"{self.side}_armSettings_LOCShape")

    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        self.pair_blends = []
        self.fk_chain = []
        self.ik_chain = []

        for joint in self.arm_chain:

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

        # cmds.parent(self.fk_chain[0], self.module_trn)
        cmds.parent(self.ik_chain[0], self.module_trn)

    def controllers_creation(self):

        """
        Create controllers for the arm module.
        """
        self.fk_nodes = []
        self.fk_controllers = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armFkControllers_GRP", ss=True, p=self.controllers_grp)

        for i, joint in enumerate(self.fk_chain):

            fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", ""), offset=["GRP"]) # create FK controllers
            self.lock_attributes(fk_ctl, ["translateX", "translateY", "translateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
            
            cmds.matchTransform(fk_node[0], self.arm_chain[i], pos=True, rot=True)

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            if i == 0:
                matrix_manager.fk_constraint(joint, "None", self.pair_blends[i])
            else:
                matrix_manager.fk_constraint(joint, self.fk_chain[i-1], self.pair_blends[i])

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)


        self.ik_controllers = []
        self.ik_controllers = []

        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armIkControllers_GRP", ss=True, p=self.controllers_grp)

        self.ik_wrist_nodes, self.ik_wrist_ctl = curve_tool.create_controller(name=f"{self.side}_armIkWrist", offset=["GRP", "SPC"])
        self.lock_attributes(self.ik_wrist_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_wrist_nodes[0], ik_controllers_trn)
        cmds.matchTransform(self.ik_wrist_nodes[0], self.arm_chain[-1], pos=True, rot=True)

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_armPv", offset=["GRP", "SPC"])
        self.lock_attributes(self.pv_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        cmds.matchTransform(self.pv_nodes[0], self.arm_chain[1], pos=True, rot=True)

        self.ik_root_nodes, self.ik_root_ctl = curve_tool.create_controller(name=f"{self.side}_armIkRoot", offset=["GRP"])
        self.lock_attributes(self.ik_root_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_root_nodes[0], ik_controllers_trn)
        cmds.matchTransform(self.ik_root_nodes[0], self.arm_chain[0], pos=True, rot=True)

        reverse_node = cmds.createNode("reverse", name=f"{self.side}_armIkFK_REV", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{ik_controllers_trn}.visibility")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{fk_controllers_trn}.visibility")

    def ik_setup(self):

        """
        Setup the IK for the arm module.
        """
        
        self.ik_handle = cmds.ikHandle(name=f"{self.side}_armIkHandle_HDL", startJoint=self.ik_chain[0], endEffector=self.ik_chain[-1], solver="ikRPsolver")[0]
        cmds.parent(self.ik_handle, self.module_trn)
        cmds.setAttr(f"{self.ik_handle}.visibility", 0)

        cmds.connectAttr(f"{self.ik_wrist_ctl}.worldMatrix[0]", f"{self.ik_handle}.offsetParentMatrix")
        cmds.xform(self.ik_handle, a=True, t=(0, 0, 0), ro=(0, 0, 0), s=(1, 1, 1))

        # Set up the pole vector constraint for the IK handle
        arm_pos = om.MVector(cmds.xform(self.ik_chain[0], q=True, rp=True, ws=True))
        elbow_pos = om.MVector(cmds.xform(self.ik_chain[1], q=True, rp=True, ws=True))
        wrist_pos = om.MVector(cmds.xform(self.ik_chain[2], q=True, rp=True, ws=True))

        arm_to_wrist = wrist_pos - arm_pos
        arm_to_wrist_scaled = arm_to_wrist / 2
        mid_point = arm_pos + arm_to_wrist_scaled
        mid_point_to_elbow_vec = elbow_pos - mid_point
        mid_point_to_elbow_vec_scaled = mid_point_to_elbow_vec * 2
        mid_point_to_elbow_point = mid_point + mid_point_to_elbow_vec_scaled

        cmds.xform(self.pv_nodes[0], translation=mid_point_to_elbow_point)
        cmds.poleVectorConstraint(self.pv_ctl, self.ik_handle)
        self.lock_attributes(self.pv_ctl, ["sx", "sy", "sz", "v"])

    def fk_stretch(self):

        """
        Setup FK stretch for the arm module.
        """

        for ctl in self.fk_controllers:
            cmds.setAttr(f"{ctl}.translateX", lock=False)
            cmds.addAttr(ctl, shortName="STRETCHY____", attributeType="enum", enumName="____", keyable=True)
            cmds.setAttr(f"{ctl}.STRETCHY____", lock=True, keyable=False)
            cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

        self.upper_double_mult_linear = cmds.createNode("multDoubleLinear", n=f"{self.side}_armUpperDoubleMultLinear_MDL")
        self.lower_double_mult_linear = cmds.createNode("multDoubleLinear", n=f"{self.side}_armLowerDoubleMultLinear_MDL")
        cmds.connectAttr(f"{self.fk_controllers[0]}.Stretch", f"{self.upper_double_mult_linear}.input1")
        cmds.connectAttr(f"{self.fk_controllers[1]}.Stretch", f"{self.lower_double_mult_linear}.input1")

        upper_distance = cmds.getAttr(f"{self.fk_controllers[1]}.translateX")
        lower_distance = cmds.getAttr(f"{self.fk_controllers[-1]}.translateX")

        cmds.setAttr(f"{self.upper_double_mult_linear}.input2", upper_distance)
        cmds.setAttr(f"{self.lower_double_mult_linear}.input2", lower_distance)
        cmds.connectAttr(f"{self.upper_double_mult_linear}.output", f"{self.fk_controllers[1]}.translateX")
        cmds.connectAttr(f"{self.lower_double_mult_linear}.output", f"{self.fk_controllers[-1]}.translateX")
    
    def soft_ik(self):

        """
        Setup soft IK for the arm module.
        """

        # --- Stretchy IK Controllers ---
        cmds.addAttr(self.ik_wrist_ctl, shortName="STRETCHY____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_wrist_ctl}.STRETCHY____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="upperLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="lowerLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="Stretch", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="SOFT____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_wrist_ctl}.SOFT____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="Soft", minValue=0, defaultValue=0, maxValue=1, keyable=True)

        # Calculate full_length and initial_distance using vector positions
        start_pos = om.MVector(cmds.xform(self.ik_chain[0], q=True, ws=True, t=True))
        mid_pos = om.MVector(cmds.xform(self.ik_chain[1], q=True, ws=True, t=True))
        end_pos = om.MVector(cmds.xform(self.ik_chain[2], q=True, ws=True, t=True))

        upper_length = (mid_pos - start_pos).length()
        lower_length = (end_pos - mid_pos).length()
        full_length = upper_length + lower_length
        initial_distance = (end_pos - start_pos).length()
        soft_distance = full_length - initial_distance

        self.soft_off = cmds.createNode("transform", name=f"{self.side}_armSoft_OFF", p=self.module_trn)
        decompose_matrix_translate = cmds.createNode("decomposeMatrix", name=f"{self.side}_armSoftTranslation_DCM", ss=True)
        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{decompose_matrix_translate}.inputMatrix")
        aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_armSoftOff_AMT", ss=True)
        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{aim_matrix}.inputMatrix")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.worldMatrix[0]", f"{aim_matrix}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{aim_matrix}.primaryInputAxisX", 1)
        cmds.setAttr(f"{aim_matrix}.primaryInputAxisY", 0)
        cmds.setAttr(f"{aim_matrix}.primaryInputAxisZ", 0)
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxisX", 0)
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxisY", 1)
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxisZ", 0)
        cmds.setAttr(f"{aim_matrix}.primaryMode", 1)
        decompose_matrix_rotate = cmds.createNode("decomposeMatrix", name=f"{self.side}_armSoftRotation_DCM", ss=True)
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{decompose_matrix_rotate}.inputMatrix")
        compose_matrix = cmds.createNode("composeMatrix", name=f"{self.side}_armSoftCompose_CM", ss=True)
        cmds.connectAttr(f"{decompose_matrix_translate}.outputTranslate", f"{compose_matrix}.inputTranslate")
        cmds.connectAttr(f"{decompose_matrix_rotate}.outputRotate", f"{compose_matrix}.inputRotate")
        cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{self.soft_off}.offsetParentMatrix")

        self.soft_trn = cmds.createNode("transform", name=f"{self.side}_armSoft_TRN", p=self.soft_off)
        cmds.matchTransform(self.soft_trn, self.arm_chain[-1], pos=True)



        nodes_to_create = {
        f"{self.side}_armDistanceToControl_DBT": ("distanceBetween", None),  # 0
        f"{self.side}_armDistanceToControlNormalized_FLM": ("floatMath", 3),  # 1
        f"{self.side}_armSoftValue_RMV": ("remapValue", None),  # 2
        f"{self.side}_armDistanceToControlMinusSoftDistance_FLM": ("floatMath", 1),  # 3
        f"{self.side}_armUpperLength_FLM": ("floatMath", 2),  # 4
        f"{self.side}_armDistanceToControlMinusSoftDistanceDividedBySoftValue_FLM": ("floatMath", 3),  # 5
        f"{self.side}_armFullLength_FLM": ("floatMath", 0),  # 6
        f"{self.side}_armDistanceToControlMinusSoftDistanceDividedBySoftValueNegate_FLM": ("floatMath", 2),  # 7
        f"{self.side}_armSoftDistance_FLM": ("floatMath", 1),  # 8
        f"{self.side}_armSoftEPower_FLM": ("floatMath", 6),  # 9
        f"{self.side}_armLowerLength_FLM": ("floatMath", 2),  # 10
        f"{self.side}_armSoftOneMinusEPower_FLM": ("floatMath", 1),  # 11
        f"{self.side}_armSoftOneMinusEPowerSoftValueEnable_FLM": ("floatMath", 2),  # 12
        f"{self.side}_armSoftConstant_FLM": ("floatMath", 0),  # 13
        f"{self.side}_armLengthRatio_FLM": ("floatMath", 3),  # 14
        f"{self.side}_armSoftRatio_FLM": ("floatMath", 3),  # 15
        f"{self.side}_armDistanceToControlDividedByTheLengthRatio_FLM": ("floatMath", 3),  # 16
        f"{self.side}_armSoftEffectorDistance_FLM": ("floatMath", 2),  # 17
        f"{self.side}_armSoftCondition_CON": ("condition", None),  # 18
        f"{self.side}_armUpperLengthStretch_FLM": ("floatMath", 2),  # 19
        f"{self.side}_armDistanceToControlDividedByTheSoftEffector_FLM": ("floatMath", 3),  # 20
        f"{self.side}_armDistanceToControlDividedByTheSoftEffectorMinusOne_FLM": ("floatMath", 1),  # 21
        f"{self.side}_armDistanceToControlDividedByTheSoftEffectorMinusOneMultipliedByTheStretch_FLM": ("floatMath", 2),  # 22
        f"{self.side}_armStretchFactor_FLM": ("floatMath", 0),  # 23
        f"{self.side}_armSoftEffectStretchDistance_FLM": ("floatMath", 2),  # 24
        f"{self.side}_armLowerLengthStretch_FLM": ("floatMath", 2),  # 25
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
        cmds.setAttr(f"{self.created_nodes[10]}.floatB", abs(cmds.getAttr(f"{self.ik_chain[-1]}.translateX")))
        cmds.setAttr(f"{self.created_nodes[2]}.outputMin", 0.001)
        cmds.setAttr(f"{self.created_nodes[2]}.outputMax", soft_distance)
        cmds.setAttr(f"{self.created_nodes[7]}.floatB", -1.0)
        cmds.setAttr(f"{self.created_nodes[18]}.operation", 2)

        cmds.connectAttr(f"{self.ik_wrist_ctl}.upperLengthMult", f"{self.created_nodes[4]}.floatA")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.lowerLengthMult", f"{self.created_nodes[10]}.floatA")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.Stretch", f"{self.created_nodes[22]}.floatB")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix2")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.Soft", f"{self.created_nodes[2]}.inputValue")

        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.created_nodes[1]}.floatB")

        cmds.connectAttr(f"{self.created_nodes[18]}.outColorR", f"{self.soft_trn}.translateX")
        if self.side == "L":
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{self.ik_chain[1]}.translateX")
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{self.ik_chain[-1]}.translateX")
        else:
            abs_up = cmds.createNode("floatMath", n=f"{self.side}_armAbsUpper_FLM")
            abs_low = cmds.createNode("floatMath", n=f"{self.side}_armAbsLower_FLM")
            cmds.setAttr(f"{abs_up}.operation", 2)
            cmds.setAttr(f"{abs_low}.operation", 2)
            cmds.setAttr(f"{abs_up}.floatB", -1)
            cmds.setAttr(f"{abs_low}.floatB", -1)
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{abs_up}.floatA")
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{abs_low}.floatA")
            cmds.connectAttr(f"{abs_up}.outFloat", f"{self.ik_chain[1]}.translateX")
            cmds.connectAttr(f"{abs_low}.outFloat", f"{self.ik_chain[-1]}.translateX")

        cmds.connectAttr(f"{self.soft_trn}.worldMatrix[0]", f"{self.ik_handle}.offsetParentMatrix", force=True)
        cmds.connectAttr(f"{self.ik_wrist_ctl}.rotate", f"{self.ik_chain[-1]}.rotate")
        cmds.parentConstraint(self.ik_root_ctl, self.ik_chain[0], maintainOffset=True)
