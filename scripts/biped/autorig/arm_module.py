from turtle import up

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

class ArmModule(object):

    def __init__(self):

        """
        Initialize the ArmModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        
    def make(self, side, skinning_jnts, primaryInputAxis = (1, 0, 0), secondaryInputAxis = (0, 0, 1)):

        """ 
        Create the arm module structure and controllers. Call this method with the side ('L' or 'R') to create the respective arm module.
        Args:
            side (str): The side of the arm ('L' or 'R').
            primaryInputAxis (tuple): The primary axis for orientation.
            secondaryInputAxis (tuple): The secondary axis for orientation.

        """
        self.skinning_joint_numbers = skinning_jnts
        self.side = side

        self.primaryInputAxis = primaryInputAxis if self.side == "L" else tuple(-x for x in primaryInputAxis)
        self.secondaryInputAxis = secondaryInputAxis if self.side == "L" else tuple(-x for x in secondaryInputAxis)

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
        self.elbow_pin_setup()
        skel_env = self.de_boor_ribbon(self.skinning_joint_numbers)
        
        data_manager.DataExportBiped().append_data("arm_module",
                            {
                                f"{self.side}_shoulder_JNT": self.arm_chain[0],
                                f"{self.side}_wrist_JNT": self.wrist_skinning,
                                f"{self.side}_armSettings": self.settings_ctl,
                                f"{self.side}_armIk": self.ik_wrist_ctl,
                                f"{self.side}_armPv": self.pv_ctl,
                                f"{self.side}_shoulderFk": self.fk_controllers[0],
                                f"{self.side}_armIkRoot": self.ik_root_ctl,
                                f"{self.side}_skinningJoints": skel_env
                            })
        
        cmds.delete(self.arm_chain)

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

        self.guides_matrices, self.guides_trns = guides_manager.orient_guides(self.arm_chain, self.primaryInputAxis, self.secondaryInputAxis)

    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"], parent=self.controllers_grp, locked_attrs=["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility", "rotateOrder"], match=self.settings_loc)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName= "Switch IK --> FK", attributeType="float", defaultValue=1, minValue=0, maxValue=1, keyable=True)

        # No FK joint chain: the FK controllers feed the blend matrices directly
        # (see controllers_creation), so only the IK chain is needed.
        self.ik_chain = []

        for joint in self.arm_chain:

            cmds.select(clear=True)
            ik_joint = cmds.joint(name=joint.replace("_JNT", "Ik_JNT"))
            cmds.matchTransform(ik_joint, joint, pos=True, rot=True)
            cmds.makeIdentity(ik_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)

            if self.ik_chain:
                cmds.parent(ik_joint, self.ik_chain[-1])

            self.ik_chain.append(ik_joint)

        cmds.parent(self.ik_chain[0], self.module_trn)

    def controllers_creation(self):

        """
        Create controllers for the arm module.
        """
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armFkControllers_GRP", ss=True, p=self.controllers_grp)

        for i, joint in enumerate(self.arm_chain):

            fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", "Fk"), offset=["GRP", "ANM"]) # create FK controllers
            self.lock_attributes(fk_ctl, ["translateX", "translateY", "translateZ", "scaleX", "scaleY", "scaleZ", "visibility"])

            cmds.connectAttr(self.guides_matrices[i], f"{fk_node[0]}.offsetParentMatrix")

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            # FK ctl worldMatrix feeds the blend matrix directly (no FK joint chain)
            ik_joint = joint.replace("_JNT", "Ik_JNT")
            if i == 0:
                blend_matrix = matrix_manager.fk_blend(joint, ik_joint, fk_ctl, None, self.settings_ctl)

            else:
                blend_matrix = matrix_manager.fk_blend(joint, ik_joint, fk_ctl, self.arm_chain[i-1], self.settings_ctl)

                mmx_negate = cmds.createNode("multMatrix", name=joint.replace("JNT", "MMX"), ss=True)
                inverse_matrix = cmds.createNode("inverseMatrix", name=joint.replace("JNT", "INV"), ss=True)
                cmds.connectAttr(self.guides_matrices[i-1], f"{inverse_matrix}.inputMatrix")

                cmds.connectAttr(self.guides_matrices[i], f"{mmx_negate}.matrixIn[0]")
                cmds.connectAttr(f"{inverse_matrix}.outputMatrix", f"{mmx_negate}.matrixIn[1]")

                cmds.connectAttr(f"{mmx_negate}.matrixSum", f"{fk_node[0]}.offsetParentMatrix", force=True)

            cmds.xform(fk_node[0], m=om.MMatrix.kIdentity)

            self.blend_matrices.append(blend_matrix)

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)


        self.ik_controllers = []
        self.ik_controllers = []

        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armIkControllers_GRP", ss=True, p=self.controllers_grp)

        self.ik_wrist_nodes, self.ik_wrist_ctl = curve_tool.create_controller(name=f"{self.side}_armIkWrist", offset=["GRP", "SPC"])
        self.lock_attributes(self.ik_wrist_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_wrist_nodes[0], ik_controllers_trn)
        # cmds.matchTransform(self.ik_wrist_nodes[0], self.arm_chain[-1], pos=True, rot=True)
        cmds.connectAttr(self.guides_matrices[-1], f"{self.ik_wrist_nodes[0]}.offsetParentMatrix")

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_armPv", offset=["GRP", "SPC"])
        self.lock_attributes(self.pv_ctl, ["rx", "ry", "rz", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        cmds.connectAttr(self.guides_matrices[1], f"{self.pv_nodes[0]}.offsetParentMatrix")
        cmds.xform(self.pv_nodes[0], m=om.MMatrix.kIdentity)

        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_armPv_CRV") # Create a line that points always to the PV
        row_knee = cmds.createNode("rowFromMatrix", name=f"{self.side}_armPv_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.side}_armPvCtl_RFM", ss=True)
        cmds.setAttr(f"{row_knee}.input", 3)  # translation row
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        cmds.connectAttr(f"{self.arm_chain[1]}.worldMatrix[0]", f"{row_knee}.matrix")
        for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
            cmds.connectAttr(f"{row_knee}.output{axis}", f"{crv_point_pv}.controlPoints[0].{value}")
            cmds.connectAttr(f"{row_ctl}.output{axis}", f"{crv_point_pv}.controlPoints[1].{value}")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)
        cmds.setAttr(f"{crv_point_pv}.hiddenInOutliner", 1)

        cmds.parent(crv_point_pv, self.pv_ctl)

        self.ik_root_nodes, self.ik_root_ctl = curve_tool.create_controller(name=f"{self.side}_armIkRoot", offset=["GRP"])
        self.lock_attributes(self.ik_root_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_root_nodes[0], ik_controllers_trn)
        cmds.connectAttr(self.guides_matrices[0], f"{self.ik_root_nodes[0]}.offsetParentMatrix")
        cmds.xform(self.ik_root_nodes[0], m=om.MMatrix.kIdentity)

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

        for i, ctl in enumerate(self.fk_controllers):
            if i < len(self.fk_controllers) - 1:
                
                # cmds.setAttr(f"{ctl}.translateX", lock=False)
                cmds.addAttr(ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------")
                cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

                label = ctl.split("_")[1]
                mult_node = cmds.createNode("multiply", n=f"{self.side}_arm{label}_MUL")
                dist_node = cmds.createNode("distanceBetween", name=f"{self.side}_arm{label}DistanceBetween_DBT", ss=True)

                cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
                cmds.connectAttr(self.guides_matrices[i], f"{dist_node}.inMatrix1")
                cmds.connectAttr(self.guides_matrices[i+1], f"{dist_node}.inMatrix2")
                
                if self.side == "R":
                    multiply_negate = cmds.createNode("multiply", name=f"{self.side}_arm{label}_Negate_MUL", ss=True)
                    cmds.connectAttr(f"{dist_node}.distance", f"{multiply_negate}.input[0]")
                    cmds.setAttr(f"{multiply_negate}.input[1]", -1)
                    cmds.connectAttr(f"{multiply_negate}.output", f"{mult_node}.input[1]")
                else:
                    cmds.connectAttr(f"{dist_node}.distance", f"{mult_node}.input[1]")

                target_node = self.fk_nodes[i+1]
                
                row_translate = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowFromMatrix_RFM", ss=True)
                cmds.setAttr(f"{row_translate}.input", 3)
                
                connection = cmds.listConnections(f"{target_node}.offsetParentMatrix", source=True, destination=False, plugs=True)[0]
                cmds.connectAttr(connection, f"{row_translate}.matrix")
                fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_arm{label}_FBF", ss=True)

                row_x = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowX_RFM", ss=True)
                row_y = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowY_RFM", ss=True)
                row_z = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowZ_RFM", ss=True)
                cmds.setAttr(f"{row_x}.input", 0)
                cmds.setAttr(f"{row_y}.input", 1)
                cmds.setAttr(f"{row_z}.input", 2)
                cmds.connectAttr(connection, f"{row_x}.matrix")
                cmds.connectAttr(connection, f"{row_y}.matrix")
                cmds.connectAttr(connection, f"{row_z}.matrix")

                cmds.connectAttr(f"{row_x}.outputX", f"{fbf}.in00")
                cmds.connectAttr(f"{row_x}.outputY", f"{fbf}.in01")
                cmds.connectAttr(f"{row_x}.outputZ", f"{fbf}.in02")

                cmds.connectAttr(f"{row_y}.outputX", f"{fbf}.in10")
                cmds.connectAttr(f"{row_y}.outputY", f"{fbf}.in11")
                cmds.connectAttr(f"{row_y}.outputZ", f"{fbf}.in12")

                cmds.connectAttr(f"{row_z}.outputX", f"{fbf}.in20")
                cmds.connectAttr(f"{row_z}.outputY", f"{fbf}.in21")
                cmds.connectAttr(f"{row_z}.outputZ", f"{fbf}.in22")

                cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30")
                cmds.connectAttr(f"{row_translate}.outputY", f"{fbf}.in31")
                cmds.connectAttr(f"{row_translate}.outputZ", f"{fbf}.in32")

                cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)


    def soft_ik(self):

        """
        Setup soft IK for the arm module.
        """

        # --- Stretchy IK Controllers ---
        cmds.addAttr(self.ik_wrist_ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.ik_wrist_ctl}.STRETCHY", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="upperLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="lowerLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="Stretch", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, longName="SOFT", niceName="SOFT ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.ik_wrist_ctl}.SOFT", lock=True, keyable=False, channelBox=True)
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
        if soft_distance < 0.01:
            soft_distance = 0.1

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

        # Soft sin nodos DAG: composeMatrix(tx soft) * aimMatrix replica el
        # worldMatrix del antiguo {side}_armSoft_TRN (hijo de {side}_armSoft_OFF)
        self.soft_cmx = cmds.createNode("composeMatrix", name=f"{self.side}_armSoft_CMX", ss=True)
        self.soft_mmx = cmds.createNode("multMatrix", name=f"{self.side}_armSoft_MMX", ss=True)
        cmds.connectAttr(f"{self.soft_cmx}.outputMatrix", f"{self.soft_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{self.soft_mmx}.matrixIn[1]")

        nodes_to_create = {
        f"{self.side}_armDistanceToControl_DBT": ("distanceBetween", None),  # 0
        f"{self.side}_armDistanceToControlNormalized_DIV": ("divide", None),  # 1
        f"{self.side}_armSoftValue_RMV": ("remapValue", None),  # 2
        f"{self.side}_armDistanceToControlMinusSoftDistance_SUB": ("subtract", None),  # 3
        f"{self.side}_armUpperLength_MUL": ("multiply", None),  # 4
        f"{self.side}_armDistanceToControlMinusSoftDistanceDividedBySoftValue_DIV": ("divide", None),  # 5
        f"{self.side}_armFullLength_SUM": ("sum", None),  # 6
        f"{self.side}_armDistanceToControlMinusSoftDistanceDividedBySoftValueNegate_MUL": ("multiply", None),  # 7
        f"{self.side}_armSoftDistance_SUB": ("subtract", None),  # 8
        f"{self.side}_armSoftEPower_POW": ("power", None),  # 9
        f"{self.side}_armLowerLength_MUL": ("multiply", None),  # 10
        f"{self.side}_armSoftOneMinusEPower_SUB": ("subtract", None),  # 11
        f"{self.side}_armSoftOneMinusEPowerSoftValueEnable_MUL": ("multiply", None),  # 12
        f"{self.side}_armSoftConstant_SUM": ("sum", None),  # 13
        f"{self.side}_armLengthRatio_DIV": ("divide", None),  # 14
        f"{self.side}_armSoftRatio_DIV": ("divide", None),  # 15
        f"{self.side}_armDistanceToControlDividedByTheLengthRatio_DIV": ("divide", None),  # 16
        f"{self.side}_armSoftEffectorDistance_MUL": ("multiply", None),  # 17
        f"{self.side}_armSoftCondition_CON": ("condition", None),  # 18
        f"{self.side}_armUpperLengthStretch_MUL": ("multiply", None),  # 19
        f"{self.side}_armDistanceToControlDividedByTheSoftEffector_DIV": ("divide", None),  # 20
        f"{self.side}_armDistanceToControlDividedByTheSoftEffectorMinusOne_SUB": ("subtract", None),  # 21
        f"{self.side}_armDistanceToControlDividedByTheSoftEffectorMinusOneMultipliedByTheStretch_MUL": ("multiply", None),  # 22
        f"{self.side}_armStretchFactor_SUM": ("sum", None),  # 23
        f"{self.side}_armSoftEffectStretchDistance_MUL": ("multiply", None),  # 24
        f"{self.side}_armLowerLengthStretch_MUL": ("multiply", None),  # 25
        }

        self.created_nodes = []
        for node_name, (node_type, operation) in nodes_to_create.items():
            node = cmds.createNode(node_type, name=node_name)
            self.created_nodes.append(node)
            if operation is not None:
                cmds.setAttr(f'{node}.operation', operation)

        # Connections between selected nodes
        cmds.connectAttr(self.created_nodes[0] + ".distance", self.created_nodes[1]+".input1")
        cmds.connectAttr(self.created_nodes[1] + ".output", self.created_nodes[14]+".input1")
        cmds.connectAttr(self.created_nodes[1] + ".output", self.created_nodes[3]+".input1")
        cmds.connectAttr(self.created_nodes[1] + ".output", self.created_nodes[16]+".input1")
        cmds.connectAttr(self.created_nodes[1] + ".output", self.created_nodes[18]+".firstTerm")
        cmds.connectAttr(self.created_nodes[1] + ".output", self.created_nodes[18]+".colorIfFalseR")
        cmds.connectAttr(self.created_nodes[1] + ".output", self.created_nodes[20]+".input1")
        cmds.connectAttr(self.created_nodes[2] + ".outValue", self.created_nodes[5]+".input2")
        cmds.connectAttr(self.created_nodes[2] + ".outValue", self.created_nodes[8]+".input2")
        cmds.connectAttr(self.created_nodes[2] + ".outValue", self.created_nodes[12]+".input[0]")
        cmds.connectAttr(self.created_nodes[3] + ".output", self.created_nodes[5]+".input1")
        cmds.connectAttr(self.created_nodes[8] + ".output", self.created_nodes[3]+".input2")
        cmds.connectAttr(self.created_nodes[4] + ".output", self.created_nodes[18]+".colorIfFalseG")
        cmds.connectAttr(self.created_nodes[4] + ".output", self.created_nodes[6]+".input[0]")
        cmds.connectAttr(self.created_nodes[4] + ".output", self.created_nodes[19]+".input[1]")
        cmds.connectAttr(self.created_nodes[5] + ".output", self.created_nodes[7]+".input[0]")
        cmds.connectAttr(self.created_nodes[6] + ".output", self.created_nodes[15]+".input2")
        cmds.connectAttr(self.created_nodes[6] + ".output", self.created_nodes[8]+".input1")
        cmds.connectAttr(self.created_nodes[6] + ".output", self.created_nodes[14]+".input2")
        cmds.connectAttr(self.created_nodes[10] + ".output", self.created_nodes[6]+".input[1]")
        cmds.connectAttr(self.created_nodes[7] + ".output", self.created_nodes[9]+".exponent")
        cmds.connectAttr(self.created_nodes[8] + ".output", self.created_nodes[13]+".input[1]")
        cmds.connectAttr(self.created_nodes[8] + ".output", self.created_nodes[18]+".secondTerm")
        cmds.connectAttr(self.created_nodes[9] + ".output", self.created_nodes[11]+".input2")
        cmds.connectAttr(self.created_nodes[10] + ".output", self.created_nodes[18]+".colorIfFalseB")
        cmds.connectAttr(self.created_nodes[10] + ".output", self.created_nodes[25]+".input[1]")
        cmds.connectAttr(self.created_nodes[11] + ".output", self.created_nodes[12]+".input[1]")
        cmds.connectAttr(self.created_nodes[12] + ".output", self.created_nodes[13]+".input[0]")
        cmds.connectAttr(self.created_nodes[13] + ".output", self.created_nodes[15]+".input1")
        cmds.connectAttr(self.created_nodes[14] + ".output", self.created_nodes[16]+".input2")
        cmds.connectAttr(self.created_nodes[15] + ".output", self.created_nodes[17]+".input[0]")
        cmds.connectAttr(self.created_nodes[16] + ".output", self.created_nodes[17]+".input[1]")
        cmds.connectAttr(self.created_nodes[17] + ".output", self.created_nodes[24]+".input[0]")
        cmds.connectAttr(self.created_nodes[17] + ".output", self.created_nodes[20]+".input2")
        cmds.connectAttr(self.created_nodes[24] + ".output", self.created_nodes[18]+".colorIfTrueR")
        cmds.connectAttr(self.created_nodes[19] + ".output", self.created_nodes[18]+".colorIfTrueG")
        cmds.connectAttr(self.created_nodes[25] + ".output", self.created_nodes[18]+".colorIfTrueB")
        cmds.connectAttr(self.created_nodes[23] + ".output", self.created_nodes[19]+".input[0]")
        cmds.connectAttr(self.created_nodes[20] + ".output", self.created_nodes[21]+".input1")
        cmds.connectAttr(self.created_nodes[21] + ".output", self.created_nodes[22]+".input[0]")
        cmds.connectAttr(self.created_nodes[22] + ".output", self.created_nodes[23]+".input[0]")
        cmds.connectAttr(self.created_nodes[23] + ".output", self.created_nodes[24]+".input[1]")
        cmds.connectAttr(self.created_nodes[23] + ".output", self.created_nodes[25]+".input[0]")

        cmds.setAttr(f"{self.created_nodes[9]}.input", math.e)
        cmds.setAttr(f"{self.created_nodes[4]}.input[1]", abs(cmds.getAttr(f"{self.ik_chain[1]}.translateX")))
        cmds.setAttr(f"{self.created_nodes[10]}.input[1]", abs(cmds.getAttr(f"{self.ik_chain[-1]}.translateX")))
        cmds.setAttr(f"{self.created_nodes[2]}.outputMin", 0.001)
        cmds.setAttr(f"{self.created_nodes[2]}.outputMax", soft_distance)
        cmds.setAttr(f"{self.created_nodes[7]}.input[1]", -1.0)
        cmds.setAttr(f"{self.created_nodes[18]}.operation", 2)
        cmds.setAttr(f"{self.created_nodes[11]}.input1", 1.0)  # 1 - e^x
        cmds.setAttr(f"{self.created_nodes[21]}.input2", 1.0)  # x - 1
        cmds.setAttr(f"{self.created_nodes[23]}.input[1]", 1.0)  # 1 + stretch delta

        cmds.connectAttr(f"{self.ik_wrist_ctl}.upperLengthMult", f"{self.created_nodes[4]}.input[0]")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.lowerLengthMult", f"{self.created_nodes[10]}.input[0]")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.Stretch", f"{self.created_nodes[22]}.input[1]")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix2")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.Soft", f"{self.created_nodes[2]}.inputValue")

        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.created_nodes[1]}.input2")

        cmds.connectAttr(f"{self.created_nodes[18]}.outColorR", f"{self.soft_cmx}.inputTranslateX")
        if self.side == "L":
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{self.ik_chain[1]}.translateX")
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{self.ik_chain[-1]}.translateX")
        else:
            abs_up = cmds.createNode("multiply", n=f"{self.side}_armAbsUpper_MUL")
            abs_low = cmds.createNode("multiply", n=f"{self.side}_armAbsLower_MUL")
            cmds.setAttr(f"{abs_up}.input[1]", -1)
            cmds.setAttr(f"{abs_low}.input[1]", -1)
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{abs_up}.input[0]")
            cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{abs_low}.input[0]")
            cmds.connectAttr(f"{abs_up}.output", f"{self.ik_chain[1]}.translateX")
            cmds.connectAttr(f"{abs_low}.output", f"{self.ik_chain[-1]}.translateX")

        cmds.connectAttr(f"{self.soft_mmx}.matrixSum", f"{self.ik_handle}.offsetParentMatrix", force=True)
        cmds.orientConstraint(self.ik_wrist_ctl, self.ik_chain[-1], maintainOffset=False)
        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{self.ik_chain[0]}.offsetParentMatrix")

        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.ik_chain[0]}.{attr}{axis}", 0)
                cmds.setAttr(f"{self.arm_chain[0]}.{attr}{axis}", 0)
    
    def elbow_pin_setup(self):

        """
        Setup elbow pinning for the arm module.
        """
        # Add attributes to PV controller
        cmds.addAttr(self.pv_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.pv_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, longName="Pin", niceName="Elbow Pin", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        # Pinning setup
        upper_distance = cmds.createNode("distanceBetween", name=f"{self.side}_armElbowPinUpper_DBT", ss=True)
        lower_distance = cmds.createNode("distanceBetween", name=f"{self.side}_armElbowPinLower_DBT", ss=True)

        cmds.connectAttr(f"{self.ik_root_ctl}.worldMatrix[0]", f"{upper_distance}.inMatrix1")
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{upper_distance}.inMatrix2")
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{lower_distance}.inMatrix1")
        cmds.connectAttr(f"{self.ik_wrist_ctl}.worldMatrix[0]", f"{lower_distance}.inMatrix2")

        upper_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_armElbowPinUpper_BTA", ss=True)
        lower_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_armElbowPinLower_BTA", ss=True)

        cmds.connectAttr(f"{self.pv_ctl}.Pin", f"{upper_blend}.attributesBlender")
        cmds.connectAttr(f"{self.pv_ctl}.Pin", f"{lower_blend}.attributesBlender")
        cmds.connectAttr(f"{self.created_nodes[18]}.outColorG", f"{upper_blend}.input[0]")
        cmds.connectAttr(f"{self.created_nodes[18]}.outColorB", f"{lower_blend}.input[0]")
        cmds.connectAttr(f"{upper_distance}.distance", f"{upper_blend}.input[1]")
        cmds.connectAttr(f"{lower_distance}.distance", f"{lower_blend}.input[1]")
        if self.side == "L":
            cmds.connectAttr(f"{upper_blend}.output", f"{self.ik_chain[1]}.translateX", force=True)
            cmds.connectAttr(f"{lower_blend}.output", f"{self.ik_chain[-1]}.translateX", force=True)
        else:
            negate_upper = cmds.createNode("multiply", name=f"{self.side}_armElbowPinUpperNegate_MUL", ss=True)
            negate_lower = cmds.createNode("multiply", name=f"{self.side}_armElbowPinLowerNegate_MUL", ss=True)
            cmds.setAttr(f"{negate_upper}.input[1]", -1)
            cmds.setAttr(f"{negate_lower}.input[1]", -1)
            cmds.connectAttr(f"{upper_blend}.output", f"{negate_upper}.input[0]")
            cmds.connectAttr(f"{lower_blend}.output", f"{negate_lower}.input[0]")
            cmds.connectAttr(f"{negate_upper}.output", f"{self.ik_chain[1]}.translateX", force=True)
            cmds.connectAttr(f"{negate_lower}.output", f"{self.ik_chain[-1]}.translateX", force=True)


    def de_boor_ribbon(self, skinning_joint_numbers):

        """
        Create a de Boor ribbon setup.
        """


        guides_aim = cmds.createNode("aimMatrix", name=f"{self.side}_armGuides_AIM", ss=True)
        cmds.connectAttr(self.guides_trns[0], f"{guides_aim}.inputMatrix")
        cmds.connectAttr(self.guides_trns[1], f"{guides_aim}.primary.primaryTargetMatrix")
        cmds.connectAttr(self.guides_trns[2], f"{guides_aim}.secondary.secondaryTargetMatrix")
        cmds.setAttr(f"{guides_aim}.primaryInputAxis", *self.primaryInputAxis, type="double3")
        cmds.setAttr(f"{guides_aim}.secondaryInputAxis", *self.secondaryInputAxis, type="double3")
        cmds.setAttr(f"{guides_aim}.secondaryMode", 1) # Aim


        nonRollAlign = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollAlign_BLM", ss=True)
        nonRollAim = cmds.createNode("aimMatrix", name=f"{self.side}_armNonRollAim_AMX", ss=True)
        blend_matrix_nodes = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollControllers_BLM", ss=True)

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
        cmds.setAttr(f"{nonRollAim}.primaryInputAxis", *self.primaryInputAxis, type="double3")
       

        # ----- Roll setup via swing-twist (quaternion), composed entirely with
        # MATRIX nodes so the roll is no longer a DAG joint chain that slows the
        # rig (no joints, no ikSC handles, no flips).
        aim_letter = ['x', 'y', 'z'][[abs(v) for v in self.primaryInputAxis].index(1)]
        aim_comp = aim_letter.upper()

        el = om.MVector(cmds.xform(self.arm_chain[1], q=True, ws=True, t=True))
        wr = om.MVector(cmds.xform(self.arm_chain[2], q=True, ws=True, t=True))
        forearm_len = (wr - el).length()
        forearm_len = forearm_len if self.side == "L" else -forearm_len

        # UPPER — twisted shoulder frame (rotation only) feeding the up-roll blend.
        # Quaternion fed straight into composeMatrix.inputQuat (useEulerRotation=0):
        # avoids the matrix->rotate->matrix round-trip (no quatToEuler).
        upper_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAim}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_armUpper", return_quat=True)
        upper_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_armUpperRollTwist_CMP", ss=True)
        cmds.setAttr(f"{upper_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{upper_twist}.outputQuat", f"{upper_twist_cmp}.inputQuat")
        upper_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_armUpperRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{upper_twist_cmp}.outputMatrix", f"{upper_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{nonRollAim}.outputMatrix", f"{upper_twist_mm}.matrixIn[1]")

        # LOWER — twisted forearm frame offset to the wrist (aim target for the ribbon)
        lower_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[2][0]}.outputMatrix", f"{self.blend_matrices[1][0]}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_armLower", return_quat=True)
        lower_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_armLowerRollTwist_CMP", ss=True)
        cmds.setAttr(f"{lower_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{lower_twist}.outputQuat", f"{lower_twist_cmp}.inputQuat")
        cmds.setAttr(f"{lower_twist_cmp}.inputTranslate{aim_comp}", forearm_len)
        lower_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_armLowerRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{lower_twist_cmp}.outputMatrix", f"{lower_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{lower_twist_mm}.matrixIn[1]")
        # Far anchor must track the REAL wrist position (so it follows stretch),
        # taking only the twisted forearm rotation — mirrors the upper's up_roll_blm.
        lower_roll_pm = cmds.createNode("blendMatrix", name=f"{self.side}_armLowerRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[2][0]}.outputMatrix", f"{lower_roll_pm}.inputMatrix")
        cmds.connectAttr(f"{lower_twist_mm}.matrixSum", f"{lower_roll_pm}.target[0].targetMatrix")
        cmds.setAttr(f"{lower_roll_pm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].shearWeight", 0)

        # Up Roll Blend Matrix — replaces the shoulder rotation with the twisted frame
        up_roll_blm = cmds.createNode("blendMatrix", name=f"{self.side}_armUpperRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{up_roll_blm}.inputMatrix")
        cmds.connectAttr(f"{upper_twist_mm}.matrixSum", f"{up_roll_blm}.target[0].targetMatrix")
        cmds.setAttr(f"{up_roll_blm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].rotateWeight", 1)
        cmds.setAttr(f"{up_roll_blm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].shearWeight", 0)

        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout([nonRollAim], [up_roll_blm], "Upper", skinning_joint_numbers)
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], [lower_roll_pm], "Lower", skinning_joint_numbers)

        cmds.select(clear=True)
        self.wrist_skinning = cmds.joint(name=f"{self.side}_wristSkinning_JNT")
        cmds.connectAttr(f"{self.blend_matrices[-1][0]}.outputMatrix", f"{self.wrist_skinning}.offsetParentMatrix")
        cmds.parent(self.wrist_skinning, self.skeleton_grp)

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

    def de_boor_ribbon_callout(self, first_sel, second_sel, part, skinning_joint_numbers):

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

        cmds.setAttr(f"{aim_matrix}.primaryInputAxis", *self.primaryInputAxis, type="double3")
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", *self.secondaryInputAxis, type="double3")

        blend_matrix = cmds.createNode("blendMatrix", name=f"{self.module_name}{part}MainBendy_BMT", ss=True)
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{blend_matrix}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{blend_matrix}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix}.target[0].translateWeight", 0.5)
        cmds.setAttr(f"{blend_matrix}.target[0].rotateWeight", 0)
        cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{main_bendy_nodes[0]}.offsetParentMatrix")

        for i, ctl in enumerate([main_bendy_ctl, up_bendy_ctl, low_bendy_ctl]):

            self.lock_attributes(ctl, ["visibility"])

            if i == 0:
                cmds.addAttr(ctl, longName = "BENDY", niceName="BENDY ------", attributeType="enum", enumName="------", keyable=True)
                cmds.setAttr(f"{ctl}.BENDY", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(ctl, longName="Height", attributeType="float", minValue=0, defaultValue=0.5, maxValue=1, keyable=True)
                cmds.addAttr(ctl, longName="Extra_Controllers", attributeType="bool", keyable=False)
                cmds.setAttr(f"{ctl}.Extra_Controllers", channelBox=True)

        cmds.connectAttr(f"{main_bendy_ctl}.Height", f"{blend_matrix}.target[0].translateWeight") # Connect Height to blend_matrix_main
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Controllers", f"{up_bendy_nodes[0]}.visibility")
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Controllers", f"{low_bendy_nodes[0]}.visibility")

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

        def get_axis_info(axis_tuple):
            for i, val in enumerate(axis_tuple):
                if val != 0:
                    return i, val
            return 0, 1

        aim_idx, aim_sign = get_axis_info(self.primaryInputAxis)
        up_idx, up_sign = get_axis_info(self.secondaryInputAxis)

        # 3. Mapeo a letras
        axis_map = ['x', 'y', 'z']
        aim_axis = axis_map[aim_idx]
        up_axis = axis_map[up_idx]
        aim_axis_signed = f"{'-' if aim_sign < 0 else ''}{aim_axis}"
        up_axis_signed = f"{'' if up_sign < 0 else ''}{up_axis}"
        
        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis=aim_axis_signed, up_axis=up_axis_signed, skeleton_grp=self.skeleton_grp, num_joints=skinning_joint_numbers) # Call the ribbon script to create de Boors system

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

