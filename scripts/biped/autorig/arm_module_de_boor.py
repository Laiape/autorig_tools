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

class ArmModule(object):

    def __init__(self):

        """
        Initialize the ArmModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the arm module structure and controllers. Call this method with the side ('L' or 'R') to create the respective arm module.
        Args:
            side (str): The side of the arm ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_arm"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.fk_stretch()
        self.soft_ik()
        self.de_boor_ribbon()
        
        data_manager.DataExportBiped().append_data("arm_module",
                            {
                                f"{self.side}_shoulder_JNT": self.arm_chain[0],
                                f"{self.side}_wrist_JNT": self.arm_chain[-1],
                                f"{self.side}_armSettings": self.settings_ctl,
                                f"{self.side}_armIk": self.ik_wrist_ctl,
                                f"{self.side}_armPv": self.pv_ctl,
                                f"{self.side}_shoulderFk": self.fk_controllers[0],
                                f"{self.side}_armIkRoot": self.ik_root_ctl,
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

        self.arm_chain = guides_manager.get_guides(f"{self.side}_shoulder_JNT")
        cmds.parent(self.arm_chain[0], self.module_trn)
        self.settings_loc = guides_manager.get_guides(f"{self.side}_armSettings_LOCShape")

    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName= "Switch IK --> FK", attributeType="float", defaultValue=1, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        self.fk_chain = []
        self.ik_chain = []

        for joint in self.arm_chain:

            cmds.select(clear=True)
            fk_joint = cmds.joint(name=joint.replace("_JNT", "Fk_JNT"))
            cmds.makeIdentity(fk_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)

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
        cmds.parent(self.fk_chain[0], self.module_trn)

    def controllers_creation(self):

        """
        Create controllers for the arm module.
        """
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

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
                blend_matrix = matrix_manager.fk_constraint(joint, None, True, self.settings_ctl)
            else:
                blend_matrix = matrix_manager.fk_constraint(joint, self.fk_chain[i-1], True, self.settings_ctl)

            self.blend_matrices.append(blend_matrix)

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

        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_armPv_CRV") # Create a line that points always to the PV
        decompose_knee = cmds.createNode("decomposeMatrix", name=f"{self.side}_armPv_DCM", ss=True)
        decompose_ctl = cmds.createNode("decomposeMatrix", name=f"{self.side}_armPvCtl_DCM", ss=True)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{decompose_ctl}.inputMatrix")
        cmds.connectAttr(f"{self.arm_chain[1]}.worldMatrix[0]", f"{decompose_knee}.inputMatrix")
        cmds.connectAttr(f"{decompose_knee}.outputTranslate", f"{crv_point_pv}.controlPoints[0]")
        cmds.connectAttr(f"{decompose_ctl}.outputTranslate", f"{crv_point_pv}.controlPoints[1]")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)

        cmds.parent(crv_point_pv, self.pv_ctl)

        self.ik_root_nodes, self.ik_root_ctl = curve_tool.create_controller(name=f"{self.side}_armIkRoot", offset=["GRP"])
        self.lock_attributes(self.ik_root_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
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
        self.float_constant_freeze = cmds.createNode("floatConstant", name=f"{self.side}_armFreeze_FC", ss=True)
        cmds.setAttr(f"{self.float_constant_freeze}.inFloat", 0)

        for attr in ["tx", "ty", "tz", "rx", "ry", "rz"]:
            cmds.connectAttr(f"{self.float_constant_freeze}.outFloat", f"{self.ik_handle}.{attr}")

        cmds.select(self.pv_nodes[0])
        if self.side == "L":
            cmds.move(0, 0, -20, relative=True, objectSpace=True, worldSpaceDistance=True)
        else:
            cmds.move(0, 0, 20, relative=True, objectSpace=True, worldSpaceDistance=True)
        cmds.poleVectorConstraint(self.pv_ctl, self.ik_handle)
        self.lock_attributes(self.pv_ctl, ["sx", "sy", "sz", "v"])

    def fk_stretch(self):

        """
        Setup FK stretch for the arm module.
        """

        for ctl in self.fk_controllers:
            cmds.setAttr(f"{ctl}.translateX", lock=False)
            cmds.addAttr(ctl, longName="STRETCHY", attributeType="enum", enumName="____")
            cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True)
            cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

        self.upper_double_mult_linear = cmds.createNode("multDoubleLinear", n=f"{self.side}_armUpperDoubleMultLinear_MDL")
        self.lower_double_mult_linear = cmds.createNode("multDoubleLinear", n=f"{self.side}_armLowerDoubleMultLinear_MDL")
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
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{self.soft_off}.offsetParentMatrix")

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
        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{self.ik_chain[0]}.offsetParentMatrix")

        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.ik_chain[0]}.{attr}{axis}", 0)
                cmds.setAttr(f"{self.arm_chain[0]}.{attr}{axis}", 0)

    def de_boor_ribbon(self):

        """
        Create a de Boor ribbon setup.
        """

        primary_aim_vector = (1, 0, 0)
        secondary_aim_vector = (0, 0, 1)

        guides = []
        for node in self.arm_chain:
            
            guide = cmds.createNode("transform", name=node.replace("_JNT", "_GUIDE"), ss=True, p=self.module_trn)
            cmds.matchTransform(guide, node, pos=True, rot=True)
            guides.append(guide)

        guides_aim = cmds.createNode("aimMatrix", name=f"{self.side}_armGuides_AIM", ss=True)
        cmds.connectAttr(f"{guides[0]}.worldMatrix[0]", f"{guides_aim}.inputMatrix")
        cmds.connectAttr(f"{guides[1]}.worldMatrix[0]", f"{guides_aim}.primary.primaryTargetMatrix")
        cmds.connectAttr(f"{guides[2]}.worldMatrix[0]", f"{guides_aim}.secondary.secondaryTargetMatrix")
        cmds.setAttr(f"{guides_aim}.primaryInputAxis", *primary_aim_vector, type="double3")
        cmds.setAttr(f"{guides_aim}.secondaryInputAxis", *secondary_aim_vector, type="double3")
        cmds.setAttr(f"{guides_aim}.secondaryMode", 1) # Aim


        nonRollAlign = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollAlign_BLM", ss=True)
        nonRollAim = cmds.createNode("aimMatrix", name=f"{self.side}_armNonRollAim_AMX", ss=True)
        blend_matrix_nodes = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollControllers_BLM", ss=True)
        nonRollMasterWalk_mmx = cmds.createNode("multMatrix", name=f"{self.side}_armNonRollMasterWalk_MMX", ss=True)

        cmds.connectAttr(f"{guides_aim}.outputMatrix", f"{nonRollMasterWalk_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{nonRollMasterWalk_mmx}.matrixIn[1]")

        cmds.connectAttr(f"{self.ik_root_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.inputMatrix")
        cmds.connectAttr(f"{self.fk_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{blend_matrix_nodes}.target[0].weight")

        cmds.connectAttr(f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAlign}.inputMatrix")
        cmds.connectAttr(f"{blend_matrix_nodes}.outputMatrix", f"{nonRollAlign}.target[0].targetMatrix")
        cmds.setAttr(f"{nonRollAlign}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].translateWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].shearWeight", 0)
        

        cmds.connectAttr(f"{nonRollAlign}.outputMatrix", f"{nonRollAim}.inputMatrix")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{nonRollAim}.primaryTargetMatrix")
        cmds.setAttr(f"{nonRollAim}.primaryInputAxis", *primary_aim_vector, type="double3")


        # Placeholder for de Boor ribbon setup
        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout([nonRollAim], self.blend_matrices[1], "Upper")
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], self.blend_matrices[2], "Lower")

        cmds.select(clear=True)
        wrist_skinning = cmds.joint(name=f"{self.side}_wristSkinning_JNT")
        cmds.connectAttr(f"{self.arm_chain[-1]}.worldMatrix[0]", f"{wrist_skinning}.offsetParentMatrix")
        cmds.parent(wrist_skinning, self.skeleton_grp)

        # Contraint settings controller to first skinning joint
        first_skinning_jnt = self.upper_skinning_jnt_trn[0]
        parent_matrix = cmds.createNode("parentMatrix", name=first_skinning_jnt.replace("JNT", "PMX"), ss=True)
        settings_ctl_world_matrix = cmds.getAttr(f"{self.settings_node[0]}.worldMatrix[0]")
        cmds.setAttr(f"{parent_matrix}.inputMatrix", settings_ctl_world_matrix, type="matrix")
        cmds.connectAttr(f"{first_skinning_jnt}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        offset_matrix = matrix_manager.get_offset_matrix(self.settings_node[0], first_skinning_jnt)
        cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{self.settings_node[0]}.offsetParentMatrix")
        cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", offset_matrix, type="matrix")
        cmds.xform(self.settings_node[0], m=om.MMatrix.kIdentity)
        cmds.setAttr(f"{self.settings_node[0]}.inheritsTransform", 0)

    def de_boor_ribbon_callout(self, first_sel, second_sel, part):

        if cmds.objExists(f"{first_sel[0]}.outputMatrix"):
            first_sel_output = f"{first_sel[0]}.outputMatrix"
        if cmds.objExists(f"{first_sel}.outputMatrix"):
            first_sel_output = f"{first_sel}.outputMatrix"
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

        
        aim_matrix = cmds.createNode("aimMatrix", name=f"{self.module_name}{part}MainBendy_AMT", ss=True)
        cmds.connectAttr(first_sel_output, f"{aim_matrix}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{aim_matrix}.primaryTargetMatrix")

        if self.side == "L":   
            cmds.setAttr(f"{aim_matrix}.primaryInputAxis", 1, 0, 0, type="double3") # Aim X+
        else:
            cmds.setAttr(f"{aim_matrix}.primaryInputAxis", -1, 0, 0, type="double3") # Aim X-
            
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", 0, 1, 0, type="double3")

        blend_matrix = cmds.createNode("blendMatrix", name=f"{self.module_name}{part}MainBendy_BMT", ss=True)
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{blend_matrix}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{blend_matrix}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix}.target[0].translateWeight", 0.5)
        cmds.setAttr(f"{blend_matrix}.target[0].rotateWeight", 0)
        cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{main_bendy_nodes[0]}.offsetParentMatrix")

        for i, ctl in enumerate([main_bendy_ctl, up_bendy_ctl, low_bendy_ctl]):

            self.lock_attributes(ctl, ["visibility"])

            
            

            if i == 0:
                cmds.addAttr(ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
                cmds.setAttr(f"{ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
                cmds.addAttr(ctl, longName="Bendy_Height", attributeType="float", minValue=0, defaultValue=0.5, maxValue=1, keyable=True)
                cmds.addAttr(ctl, longName="Extra_Bendys", attributeType="bool", keyable=False)
                cmds.setAttr(f"{ctl}.Extra_Bendys", channelBox=True)

        cmds.connectAttr(f"{main_bendy_ctl}.Bendy_Height", f"{blend_matrix}.target[0].translateWeight") # Connect Bendy_Height to blend_matrix_main
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Bendys", f"{up_bendy_nodes[0]}.visibility")
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Bendys", f"{low_bendy_nodes[0]}.visibility")

        for i, ctl in enumerate([up_bendy_nodes[0], low_bendy_nodes[0]]):

            blend_matrix_ = cmds.createNode("blendMatrix", name=f"{ctl}_BMT", ss=True)
            cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{blend_matrix_}.inputMatrix")
            cmds.connectAttr(second_sel_output, f"{blend_matrix_}.target[0].targetMatrix")
            if i == 0:
                cmds.setAttr(f"{blend_matrix_}.target[0].translateWeight", 0.25)
            elif i == 1:
                cmds.setAttr(f"{blend_matrix_}.target[0].translateWeight", 0.75)
            cmds.setAttr(f"{blend_matrix_}.target[0].rotateWeight", 0)
            cmds.connectAttr(f"{blend_matrix_}.outputMatrix", f"{ctl}.offsetParentMatrix")


        sel = (first_sel[0], up_bendy_ctl, main_bendy_ctl, low_bendy_ctl, second_sel[0])

        params = [i / (len(sel) - 1) for i in range(len(sel))] # Custom parameter to place the last joint in the 0.95 position
        params[-1] = 0.95

        if self.side == "L":
            output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis='x', up_axis='z', skeleton_grp=self.skeleton_grp) # Call the ribbon script to create de Boors system
        elif self.side == "R":
            output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis='-x', up_axis='z', skeleton_grp=self.skeleton_grp)

        for t in temp:
            cmds.delete(t)

        return output_joints
        

        

    def curvature(self):

        """
        Calculate the curvature of the arm module.
        This method is a placeholder for future implementation.
        Calculate the curvature of the arm module.
        This method is a placeholder for future implementation.

        """
        
        # Placeholder for curvature calculation
        pass

