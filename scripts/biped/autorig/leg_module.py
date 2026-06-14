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

class LegModule(object):

    def __init__(self):

        """
        Initialize the LegModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.local_hip_ctl = data_manager.DataExportBiped().get_data("spine_module", "local_hip_ctl")

    def make(self, side, skinning_jnts, primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, -1, 0)):

        """ 
        Create the leg module structure and controllers. Call this method with the side ('L' or 'R') to create the respective leg module.
        Args:
            side (str): The side of the leg ('L' or 'R').

        """
        self.skinning_joint_numbers = skinning_jnts
        self.side = side

        self.primary_axis = primaryInputAxis if self.side == "L" else tuple(-x for x in primaryInputAxis)
        self.secondary_axis = secondaryInputAxis if self.side == "L" else tuple(-x for x in secondaryInputAxis)

        # Set the axis information based on the primary and secondary input axes
        def get_axis_info(axis_tuple):
            for i, val in enumerate(axis_tuple):
                if val != 0:
                    return i, val
            return 0, 1

        aim_idx, aim_sign = get_axis_info(self.primary_axis)
        up_idx, up_sign = get_axis_info(self.secondary_axis)

        axis_map = ['x', 'y', 'z']
        aim_axis = axis_map[aim_idx]
        up_axis = axis_map[up_idx]
        self.aim_axis_signed = (f"{'-' if aim_sign < 0 else ''}{aim_axis}")
        self.up_axis_signed = f"{'' if up_sign < 0 else ''}{up_axis}"

        # Create the main groups for the leg module
        self.module_name = f"{self.side}_leg"
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_legModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_legSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_legControllers_GRP", ss=True, p=self.masterwalk_ctl)

        
        # Build the leg module by calling the respective methods
        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.fk_stretch()
        self.ik_setup()
        self.soft_ik()
        self.knee_pin_setup()
        self.foot_attributes()
        self.de_boor_ribbon(self.skinning_joint_numbers)

        data_manager.DataExportBiped().append_data("leg_module",
                            {
                                f"{self.side}_hip_JNT": self.leg_chain[0],
                                f"{self.side}_knee_JNT": self.leg_chain[1],
                                f"{self.side}_ankle_JNT": self.leg_chain[2],
                                f"{self.side}_legIk": self.ik_controllers[0],
                                f"{self.side}_hipFk": self.fk_controllers[0],
                                f"{self.side}_legPv": self.pv_ctl,
                                f"{self.side}_rootIk": self.root_ik_ctl,
                            })
        
        cmds.delete(self.leg_chain)

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


        self.guides_matrices, self.guides_trns = guides_manager.orient_guides(guides=self.leg_chain, primaryInputAxis=self.primary_axis, secondaryInputAxis=self.secondary_axis)


    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_legSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility", "rotateOrder"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName= "Switch IK --> FK", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        # Create the IK joint chain based on the leg guides
        self.ik_chain = []

        for joint in self.leg_chain:

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
        Create controllers for the leg module.
        """
        # FK Controllers
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_legFkControllers_GRP", ss=True, p=self.controllers_grp)
        

        for i, joint in enumerate(self.leg_chain):

            if i < len(self.leg_chain) - 1:
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
                    blend_matrix = matrix_manager.fk_blend(joint, ik_joint, fk_ctl, self.leg_chain[i-1], self.settings_ctl)

                    mmx_negate = cmds.createNode("multMatrix", name=joint.replace("JNT", "MMX"), ss=True)
                    inverse_matrix = cmds.createNode("inverseMatrix", name=joint.replace("JNT", "INV"), ss=True)
                    cmds.connectAttr(self.guides_matrices[i-1], f"{inverse_matrix}.inputMatrix")

                    cmds.connectAttr(self.guides_matrices[i], f"{mmx_negate}.matrixIn[0]")
                    cmds.connectAttr(f"{inverse_matrix}.outputMatrix", f"{mmx_negate}.matrixIn[1]")

                    cmds.connectAttr(f"{mmx_negate}.matrixSum", f"{fk_node[0]}.offsetParentMatrix", force=True)

                cmds.xform(fk_node[0], m=om.MMatrix.kIdentity)

                self.blend_matrices.append(blend_matrix)

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)
        

        # IK Controllers
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

        for i, (name, guide) in enumerate(ik_controller_dict.items()):

            ik_node, ik_ctl = curve_tool.create_controller(name=f"{self.side}_{name}", offset=["GRP", "SDK"])
            self.lock_attributes(ik_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
            if i == 0:
                pick_matrix = cmds.createNode("pickMatrix", name=f"{self.side}_{name}_PKM", ss=True)
                cmds.setAttr(f"{pick_matrix}.useRotate", 0)
                cmds.connectAttr(self.guides_matrices[2], f"{pick_matrix}.inputMatrix")
                if self.side == "R":
                    matrix_manager.mirror_controllers(controllers_grp=[ik_node[0]], input_matrix=f"{pick_matrix}.outputMatrix", secondary_axis=self.secondary_axis, rotate_180=True)
                else:
                    cmds.connectAttr(f"{pick_matrix}.outputMatrix", f"{ik_node[0]}.offsetParentMatrix")
            else:
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

        self.root_ik_nodes, self.root_ik_ctl = curve_tool.create_controller(name=f"{self.side}_legRootIk", offset=["GRP", "ANM"])
        self.lock_attributes(self.root_ik_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.connectAttr(self.guides_matrices[0], f"{self.root_ik_nodes[0]}.offsetParentMatrix")

        cmds.xform(self.root_ik_nodes[0], m=om.MMatrix.kIdentity)
        cmds.xform(self.ik_chain[0], m=om.MMatrix.kIdentity)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{self.ik_chain[0]}.offsetParentMatrix")
        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.ik_chain[0]}.{attr}{axis}", 0)
                cmds.setAttr(f"{self.leg_chain[0]}.{attr}{axis}", 0)

        cmds.parent(self.root_ik_nodes[0], ik_controllers_trn)

        # Create PV controller
        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_legPv", offset=["GRP", "ANM"])
        self.lock_attributes(self.pv_ctl, ["rx", "ry", "rz", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)

        if self.side == "R": # Mirror the PV controller
                matrix_manager.mirror_controllers(controllers_grp=[self.pv_nodes[0]], input_matrix=self.guides_matrices[1], secondary_axis=(1,0,0), rotate_180=True)
        else:
            cmds.connectAttr(self.guides_matrices[1], f"{self.pv_nodes[0]}.offsetParentMatrix")
        cmds.xform(self.pv_nodes[0], m=om.MMatrix.kIdentity)
        
        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_legPv_CRV") # Create a line that points always to the PV
        row_knee = cmds.createNode("rowFromMatrix", name=f"{self.side}_legPv_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.side}_legPvCtl_RFM", ss=True)
        cmds.setAttr(f"{row_knee}.input", 3)  # translation row
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        cmds.connectAttr(f"{self.leg_chain[1]}.worldMatrix[0]", f"{row_knee}.matrix")
        for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
            cmds.connectAttr(f"{row_knee}.output{axis}", f"{crv_point_pv}.controlPoints[0].{value}")
            cmds.connectAttr(f"{row_ctl}.output{axis}", f"{crv_point_pv}.controlPoints[1].{value}")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)
        cmds.parent(crv_point_pv, self.pv_ctl)
        cmds.setAttr(f"{crv_point_pv}.hiddenInOutliner", 1)


    
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


        cmds.connectAttr(f"{self.ik_controllers[0]}.worldMatrix[0]", f"{self.ik_handle}.offsetParentMatrix")
        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{self.ball_handle}.offsetParentMatrix")
        cmds.connectAttr(f"{self.ik_controllers[-2]}.worldMatrix[0]", f"{self.toe_handle}.offsetParentMatrix") 

        freeze_float_constant = cmds.createNode("floatConstant", name=f"{self.side}_freeze_FCF", ss=True)
        cmds.setAttr(f"{freeze_float_constant}.inFloat", 0)
        for attr in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
            cmds.connectAttr(f"{freeze_float_constant}.outFloat", f"{self.ik_handle}.{attr}")
            cmds.connectAttr(f"{freeze_float_constant}.outFloat", f"{self.ball_handle}.{attr}")
            cmds.connectAttr(f"{freeze_float_constant}.outFloat", f"{self.toe_handle}.{attr}")

        pv_c = cmds.poleVectorConstraint(self.pv_ctl, self.ik_handle)[0]

        cmds.select(self.pv_nodes[0])
        if self.secondary_axis == (0, 1, 0):
            if self.side == "L":
                cmds.move(0, 20, 0, relative=True, objectSpace=True, worldSpaceDistance=True)
            else:
                cmds.move(0, 20, 0, relative=True, objectSpace=True, worldSpaceDistance=True)
        elif self.secondary_axis == (0, -1, 0):
            if self.side == "L":
                cmds.move(0, 20, 0, relative=True, objectSpace=True, worldSpaceDistance=True)
            else:
                cmds.move(0, 20, 0, relative=True, objectSpace=True, worldSpaceDistance=True)

    

    def foot_attributes(self):

        """
        Add foot attributes to the leg module.
        """
        cmds.addAttr(self.ik_controllers[0], longName = "EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        
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
        cmds.connectAttr(f"{self.ik_controllers[0]}.Ball_Twist", f"{self.ik_sdk_nodes[-1]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Toe_Twist", f"{self.ik_sdk_nodes[-2]}.rotateY")
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

        multiply_node = cmds.createNode("multiply", name=f"{self.side}_legRollStraightAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{multiply_node}.input[0]")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{multiply_node}.input[1]")
        negate_roll_straight = cmds.createNode("negate", name=f"{self.side}_legRollStraight_NEG", ss=True)
        cmds.connectAttr(f"{multiply_node}.output", f"{negate_roll_straight}.input")
        cmds.connectAttr(f"{negate_roll_straight}.output", f"{self.ik_sdk_nodes[-2]}.rotateZ")

        roll_break_angle = cmds.createNode("remapValue", name=f"{self.side}_legRollBreakAngle_RMV", ss=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_break_angle}.inputValue")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Break_Angle", f"{roll_break_angle}.inputMax")
        cmds.setAttr(f"{roll_break_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_break_angle}.outputMax", 1)

        reverse = cmds.createNode("reverse", name=f"{self.side}_legRollBreakAngle_REV", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{reverse}.inputX")

        roll_angle_enable_mul = cmds.createNode("multiply", name=f"{self.side}_legRollAngleEnable_MUL", ss=True)
        cmds.connectAttr(f"{reverse}.outputX", f"{roll_angle_enable_mul}.input[0]")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_angle_enable_mul}.input[1]")

        roll_lift_angle_mul = cmds.createNode("multiply", name=f"{self.side}_legRollLiftAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_break_angle}.outValue", f"{roll_lift_angle_mul}.input[0]")
        cmds.connectAttr(f"{roll_angle_enable_mul}.output", f"{roll_lift_angle_mul}.input[1]")
        negate_roll_lift = cmds.createNode("negate", name=f"{self.side}_legRollLift_NEG", ss=True)
        cmds.connectAttr(f"{roll_lift_angle_mul}.output", f"{negate_roll_lift}.input")
        cmds.connectAttr(f"{negate_roll_lift}.output", f"{self.ik_sdk_nodes[-1]}.rotateZ")

    def fk_stretch(self):

        """
        Setup FK stretch for the leg module.
        """


        for i, ctl in enumerate(self.fk_controllers):
            if i < len(self.fk_controllers) - 2:
                
                cmds.addAttr(ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------")
                cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

                label = ctl.split("_")[1]
                mult_node = cmds.createNode("multiply", n=f"{self.side}_leg{label}_MUL")
                dist_node = cmds.createNode("distanceBetween", name=f"{self.side}_leg{label}DistanceBetween_DBT", ss=True)

                cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
                cmds.connectAttr(self.guides_matrices[i], f"{dist_node}.inMatrix1")
                cmds.connectAttr(self.guides_matrices[i+1], f"{dist_node}.inMatrix2")
                
                if self.side == "R":
                    multiply_negate = cmds.createNode("multiply", name=f"{self.side}_leg{label}Negate_MUL", ss=True)
                    cmds.connectAttr(f"{dist_node}.distance", f"{multiply_negate}.input[0]")
                    cmds.setAttr(f"{multiply_negate}.input[1]", -1)
                    cmds.connectAttr(f"{multiply_negate}.output", f"{mult_node}.input[1]")
                else:
                    cmds.connectAttr(f"{dist_node}.distance", f"{mult_node}.input[1]")

                target_node = self.fk_nodes[i+1]
                connection = cmds.listConnections(f"{target_node}.offsetParentMatrix", source=True, destination=False, plugs=True)[0]
                
                fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_leg{label}_FBF", ss=True)

                for row_index in range(4):
                    rfm = cmds.createNode("rowFromMatrix", name=f"{self.side}_leg{label}0{row_index}_RFM", ss=True)
                    cmds.connectAttr(connection, f"{rfm}.matrix")
                    cmds.setAttr(f"{rfm}.input", row_index)

                    for col_index in range(3):
                        cmds.connectAttr(
                            f"{rfm}.outputX" if col_index == 0 else
                            f"{rfm}.outputY" if col_index == 1 else
                            f"{rfm}.outputZ",
                            f"{fbf}.in{row_index}{col_index}"
                        )

                cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30", force=True)
                cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)

    def soft_ik(self):

        """
        Setup soft IK for the leg module.
        """

        # --- Stretchy IK Controllers ---
        cmds.addAttr(self.ik_controllers[0], longName = "STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.STRETCHY", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_controllers[0], shortName="upperLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="lowerLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="Stretch", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], longName = "SOFT", niceName="SOFT ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.SOFT", lock=True, keyable=False, channelBox=True)
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

        # IkHandle manager sin nodo DAG: el parentMatrix ya da el worldMatrix
        # del antiguo {side}_legIkHandleManager_TRN (su local era identidad)
        parent_matrix = cmds.createNode("parentMatrix", name=f"{self.side}_legSoftIkHDL_PM", ss=True)
        ankle_wM = cmds.getAttr(f"{self.ik_chain[2]}.worldMatrix[0]")
        cmds.setAttr(f"{parent_matrix}.inputMatrix", ankle_wM, type="matrix")
        cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", offset_matrix, type="matrix")
        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        soft_ik_handle_matrix = f"{parent_matrix}.outputMatrix"

        aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_legSoftOff_AMT", ss=True)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{aim_matrix}.inputMatrix")
        cmds.connectAttr(soft_ik_handle_matrix, f"{aim_matrix}.primary.primaryTargetMatrix")
        absolut_primary_axis = tuple(abs(x) for x in self.primary_axis)
        cmds.setAttr(f"{aim_matrix}.primaryInputAxis", *absolut_primary_axis, type="double3")
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", *self.secondary_axis, type="double3")
        cmds.setAttr(f"{aim_matrix}.primaryMode", 1)

        # Soft sin nodos DAG: composeMatrix(tx soft) * aimMatrix replica el
        # worldMatrix del antiguo {side}_legSoft_TRN (hijo de {side}_legSoft_OFF;
        # el tobillo cae sobre el eje primario del aim, así que ty/tz eran 0)
        self.soft_cmx = cmds.createNode("composeMatrix", name=f"{self.side}_legSoft_CMX", ss=True)
        self.soft_mmx = cmds.createNode("multMatrix", name=f"{self.side}_legSoft_MMX", ss=True)
        cmds.connectAttr(f"{self.soft_cmx}.outputMatrix", f"{self.soft_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{self.soft_mmx}.matrixIn[1]")

        nodes_to_create = {
        f"{self.side}_legDistanceToControl_DBT": ("distanceBetween", None),  # 0
        f"{self.side}_legDistanceToControlNormalized_DIV": ("divide", None),  # 1
        f"{self.side}_legSoftValue_RMV": ("remapValue", None),  # 2
        f"{self.side}_legDistanceToControlMinusSoftDistance_SUB": ("subtract", None),  # 3
        f"{self.side}_legUpperLength_MUL": ("multiply", None),  # 4
        f"{self.side}_legDistanceToControlMinusSoftDistanceDividedBySoftValue_DIV": ("divide", None),  # 5
        f"{self.side}_legFullLength_SUM": ("sum", None),  # 6
        f"{self.side}_legDistanceToControlMinusSoftDistanceDividedBySoftValueNegate_MUL": ("multiply", None),  # 7
        f"{self.side}_legSoftDistance_SUB": ("subtract", None),  # 8
        f"{self.side}_legSoftEPower_POW": ("power", None),  # 9
        f"{self.side}_legLowerLength_MUL": ("multiply", None),  # 10
        f"{self.side}_legSoftOneMinusEPower_SUB": ("subtract", None),  # 11
        f"{self.side}_legSoftOneMinusEPowerSoftValueEnable_MUL": ("multiply", None),  # 12
        f"{self.side}_legSoftConstant_SUM": ("sum", None),  # 13
        f"{self.side}_legLengthRatio_DIV": ("divide", None),  # 14
        f"{self.side}_legSoftRatio_DIV": ("divide", None),  # 15
        f"{self.side}_legDistanceToControlDividedByTheLengthRatio_DIV": ("divide", None),  # 16
        f"{self.side}_legSoftEffectorDistance_MUL": ("multiply", None),  # 17
        f"{self.side}_legSoftCondition_CON": ("condition", None),  # 18
        f"{self.side}_legUpperLengthStretch_MUL": ("multiply", None),  # 19
        f"{self.side}_legDistanceToControlDividedByTheSoftEffector_DIV": ("divide", None),  # 20
        f"{self.side}_legDistanceToControlDividedByTheSoftEffectorMinusOne_SUB": ("subtract", None),  # 21
        f"{self.side}_legDistanceToControlDividedByTheSoftEffectorMinusOneMultipliedByTheStretch_MUL": ("multiply", None),  # 22
        f"{self.side}_legStretchFactor_SUM": ("sum", None),  # 23
        f"{self.side}_legSoftEffectStretchDistance_MUL": ("multiply", None),  # 24
        f"{self.side}_legLowerLengthStretch_MUL": ("multiply", None),  # 25
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
        cmds.setAttr(f"{self.created_nodes[10]}.input[1]", abs(cmds.getAttr(f"{self.ik_chain[2]}.translateX")))
        cmds.setAttr(f"{self.created_nodes[2]}.outputMin", 0.001)
        cmds.setAttr(f"{self.created_nodes[2]}.outputMax", soft_distance)
        cmds.setAttr(f"{self.created_nodes[7]}.input[1]", -1.0)
        cmds.setAttr(f"{self.created_nodes[18]}.operation", 2)
        cmds.setAttr(f"{self.created_nodes[11]}.input1", 1.0)  # 1 - e^x
        cmds.setAttr(f"{self.created_nodes[21]}.input2", 1.0)  # x - 1
        cmds.setAttr(f"{self.created_nodes[23]}.input[1]", 1.0)  # 1 + stretch delta

        cmds.connectAttr(f"{self.ik_controllers[0]}.upperLengthMult", f"{self.created_nodes[4]}.input[0]")
        cmds.connectAttr(f"{self.ik_controllers[0]}.lowerLengthMult", f"{self.created_nodes[10]}.input[0]")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Stretch", f"{self.created_nodes[22]}.input[1]")
        cmds.connectAttr(soft_ik_handle_matrix, f"{self.created_nodes[0]}.inMatrix2")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Soft", f"{self.created_nodes[2]}.inputValue")

        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{self.created_nodes[0]}.inMatrix1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.created_nodes[1]}.input2")

        # El translateX del IK chain lo conduce knee_pin_setup (lee el valor del
        # stretch en created_nodes[18] y lo mezcla con el pinning), así que aquí
        # NO se conecta: lo pisaría igualmente con force=True y dejaría estos
        # negates como nodos muertos.

        cmds.connectAttr(f"{self.created_nodes[18]}.outColorR", f"{self.soft_cmx}.inputTranslateX")

        cmds.connectAttr(f"{self.soft_mmx}.matrixSum", f"{self.ik_handle}.offsetParentMatrix", force=True)

    def knee_pin_setup(self):
        """
        Setup knee pinning for the leg module.
        """
        # Add attributes to PV controller
        cmds.addAttr(self.pv_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.pv_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, longName="Pin", niceName="Knee Pin", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        # Pinning setup
        upper_distance = cmds.createNode("distanceBetween", name=f"{self.side}_legKneePinUpper_DBT", ss=True)
        lower_distance = cmds.createNode("distanceBetween", name=f"{self.side}_legKneePinLower_DBT", ss=True)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{upper_distance}.inMatrix1")
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{upper_distance}.inMatrix2")
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{lower_distance}.inMatrix1")
        cmds.connectAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]", f"{lower_distance}.inMatrix2")

        upper_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_legKneePinUpper_BTA", ss=True)
        lower_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_legKneePinLower_BTA", ss=True)

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
            negate_upper = cmds.createNode("multiply", name=f"{self.side}_legElbowPinUpperNegate_MUL", ss=True)
            negate_lower = cmds.createNode("multiply", name=f"{self.side}_legElbowPinLowerNegate_MUL", ss=True)
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

        nonRollAlign = cmds.createNode("blendMatrix", name=f"{self.side}_legNonRollAlign_BLM", ss=True)
        nonRollAim = cmds.createNode("aimMatrix", name=f"{self.side}_legNonRollAim_AMX", ss=True)
        blend_matrix_nodes = cmds.createNode("blendMatrix", name=f"{self.side}_legNonRollControllers_BLM", ss=True)

        cmds.connectAttr(f"{self.root_ik_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.inputMatrix")
        cmds.connectAttr(f"{self.fk_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{blend_matrix_nodes}.target[0].weight")

        cmds.connectAttr(f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAlign}.inputMatrix")
        cmds.connectAttr(f"{blend_matrix_nodes}.outputMatrix", f"{nonRollAlign}.target[0].targetMatrix")
        cmds.setAttr(f"{nonRollAlign}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].translateWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].shearWeight", 0)
        

        cmds.connectAttr(f"{nonRollAlign}.outputMatrix", f"{nonRollAim}.inputMatrix")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{nonRollAim}.primaryTargetMatrix")
        cmds.setAttr(f"{nonRollAim}.primaryInputAxis", *self.primary_axis, type="double3")
       

        # ----- Roll setup via swing-twist (quaternion), composed entirely with
        # MATRIX nodes so the roll is no longer a DAG joint chain that slows the
        # rig (no joints, no ikSC handles, no flips).
        aim_letter = ['x', 'y', 'z'][[abs(v) for v in self.primary_axis].index(1)]
        aim_comp = aim_letter.upper()

        knee = om.MVector(cmds.xform(self.leg_chain[1], q=True, ws=True, t=True))
        ankle = om.MVector(cmds.xform(self.leg_chain[2], q=True, ws=True, t=True))
        shin_len = (ankle - knee).length()
        shin_len = shin_len if self.side == "L" else -shin_len

        # UPPER — twisted hip frame (rotation only) feeding the up-roll blend.
        # Quaternion fed straight into composeMatrix.inputQuat (useEulerRotation=0):
        # avoids the matrix->rotate->matrix round-trip (no quatToEuler).
        upper_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAim}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_legUpper", return_quat=True)
        upper_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_legUpperRollTwist_CMP", ss=True)
        cmds.setAttr(f"{upper_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{upper_twist}.outputQuat", f"{upper_twist_cmp}.inputQuat")
        upper_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_legUpperRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{upper_twist_cmp}.outputMatrix", f"{upper_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{nonRollAim}.outputMatrix", f"{upper_twist_mm}.matrixIn[1]")

        # LOWER — twisted shin frame offset to the ankle (aim target for the ribbon)
        lower_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[2][0]}.outputMatrix", f"{self.blend_matrices[1][0]}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_legLower", return_quat=True)
        lower_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_legLowerRollTwist_CMP", ss=True)
        cmds.setAttr(f"{lower_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{lower_twist}.outputQuat", f"{lower_twist_cmp}.inputQuat")
        cmds.setAttr(f"{lower_twist_cmp}.inputTranslate{aim_comp}", shin_len)
        lower_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_legLowerRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{lower_twist_cmp}.outputMatrix", f"{lower_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{lower_twist_mm}.matrixIn[1]")
        # Far anchor must track the REAL ankle position (so it follows stretch),
        # taking only the twisted shin rotation — mirrors the upper's up_roll_blm.
        lower_roll_pm = cmds.createNode("blendMatrix", name=f"{self.side}_legLowerRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[2][0]}.outputMatrix", f"{lower_roll_pm}.inputMatrix")
        cmds.connectAttr(f"{lower_twist_mm}.matrixSum", f"{lower_roll_pm}.target[0].targetMatrix")
        cmds.setAttr(f"{lower_roll_pm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].shearWeight", 0)

        # Up Roll Blend Matrix — replaces the hip rotation with the twisted frame
        up_roll_blm = cmds.createNode("blendMatrix", name=f"{self.side}_legUpperRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{up_roll_blm}.inputMatrix")
        cmds.connectAttr(f"{upper_twist_mm}.matrixSum", f"{up_roll_blm}.target[0].targetMatrix")
        cmds.setAttr(f"{up_roll_blm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].rotateWeight", 1)
        cmds.setAttr(f"{up_roll_blm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].shearWeight", 0)

        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout([nonRollAim], [up_roll_blm], "Upper", skinning_joint_numbers)
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], [lower_roll_pm], "Lower", skinning_joint_numbers)

        # Create ball and ankle skinning joints
        ankle_skinning_jnt = cmds.createNode("joint", name=f"{self.module_name}AnkleSkinning_JNT", p=self.skeleton_grp)
        ball_skinning_jnt = cmds.createNode("joint", name=f"{self.module_name}BallSkinning_JNT", p=self.skeleton_grp)
        cmds.connectAttr(f"{self.blend_matrices[3][0]}.outputMatrix", f"{ball_skinning_jnt}.offsetParentMatrix")
        cmds.connectAttr(f"{self.blend_matrices[2][0]}.outputMatrix", f"{ankle_skinning_jnt}.offsetParentMatrix")
 

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

        cmds.setAttr(f"{aim_matrix}.primaryInputAxis", *self.primary_axis, type="double3") # Aim X+
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", *self.secondary_axis, type="double3")

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
                cmds.addAttr(ctl, longName="Height", attributeType="float", defaultValue=0.5, minValue=0, maxValue=1, keyable=True)
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

        # Create ribbon

        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis=self.aim_axis_signed, up_axis=self.up_axis_signed, skeleton_grp=self.skeleton_grp, num_joints=skinning_joint_numbers)

        for t in temp:
            cmds.delete(t)

        return output_joints

        