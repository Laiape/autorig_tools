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

class NeckModule(object):

    def __init__(self):

        """
        Initialize the neckModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the neck module structure and controllers. Call this method with the side ('L' or 'R') to create the respective neck module.
        Args:
            side (str): The side of the neck ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_neckModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_neckSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.controller_creation()
        self.local_head()
        self.ribbon_setup()
        # self.stretch_callback(self.neck_chain, self.neck_crv)
        # self.reversed_neck()
        # self.attatched_fk()
        # self.squash()
        

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

        """
        Load the neck guides for the specified side and parent them to the module transform.
        """

        self.neck_chain = guides_manager.get_guides(f"{self.side}_neck00_JNT")
        cmds.parent(self.neck_chain[0], self.module_trn)

       

    def controller_creation(self):

        """
        Create controllers for the neck module.
        """

        self.neck_nodes = []
        self.neck_ctls = []
        
        for i, jnt in enumerate(self.neck_chain):

            if i == 0:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])
                cmds.connectAttr(f"{corner_ctl}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")
                
            if i == len(self.neck_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_head", offset=["GRP"])

            if i == 0 or i == len(self.neck_chain) - 1:

                cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)
                cmds.parent(corner_nodes[0], self.controllers_grp)
                
            
                self.neck_nodes.append(corner_nodes[0])
                self.neck_ctls.append(corner_ctl)


        cmds.xform(self.neck_chain[0], m=om.MMatrix.kIdentity)
        for i , ctl in enumerate(self.neck_ctls):
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])


    def ribbon_setup(self):

        """
        Set up the ribbon for the neck module.
        """
        sel = (self.neck_chain[0], self.neck_chain[-1])
        self.ribbon = ribbon.de_boor_ribbon(sel, name=f"{self.side}_neckSkinning", aim_axis="y", up_axis="z")

    def stretch_callback(self, chain, crv):

        """
        Set up the stretch functionality for the neck module.
        """

        # Create the attribute for stretch in the neck controller
        if not cmds.attributeQuery("STRETCH", node=self.neck_ctls[0], exists=True):
            cmds.addAttr(self.neck_ctls[0], longName="STRETCH", attributeType="enum", enumName="____", keyable=True)
            cmds.setAttr(f"{self.neck_ctls[0]}.STRETCH", lock=True, keyable=False, channelBox=True)
            cmds.addAttr(self.neck_ctls[0], longName="neckStretch", niceName="Neck Stretch", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
            cmds.addAttr(self.neck_ctls[0], longName="Stretch_Min", niceName="Stretch Min", attributeType="float", min=0, max=1, defaultValue=0.8, keyable=True)
            cmds.addAttr(self.neck_ctls[0], longName="Stretch_Max", niceName="Stretch Max", attributeType="float", min=1, defaultValue=1.2, keyable=True)
            cmds.addAttr(self.neck_ctls[0], longName="Offset", niceName="Offset", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        else:
            pass

        # Create connections
        curve_info_node = cmds.createNode("curveInfo", name=f"{self.side}_neckCurve_CIN")
        cmds.connectAttr(f"{crv}.worldSpace[0]", f"{curve_info_node}.inputCurve")

        float_math_arc_length_node = cmds.createNode("floatMath", name=f"{self.side}_neckArcLength_FLM")
        cmds.setAttr(f"{float_math_arc_length_node}.operation", 2)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{float_math_arc_length_node}.floatA")
        cmds.setAttr(f"{float_math_arc_length_node}.floatB", cmds.getAttr(f"{curve_info_node}.arcLength")) # This is the original arc length of the curve

        float_math_stretch_factor_node = cmds.createNode("floatMath", name=f"{self.side}_neckStretchFactor_FLM")
        cmds.setAttr(f"{float_math_stretch_factor_node}.operation", 3)
        cmds.connectAttr(f"{curve_info_node}.arcLength", f"{float_math_stretch_factor_node}.floatA")
        cmds.connectAttr(f"{float_math_arc_length_node}.outFloat", f"{float_math_stretch_factor_node}.floatB")

        neck_clamp_node = cmds.createNode("clamp", name=f"{self.side}_neckStretchFactor_CLP")
        cmds.connectAttr(f"{self.neck_ctls[0]}.Stretch_Min", f"{neck_clamp_node}.minR")
        cmds.connectAttr(f"{self.neck_ctls[0]}.Stretch_Max", f"{neck_clamp_node}.maxR")
        cmds.connectAttr(f"{float_math_stretch_factor_node}.outFloat", f"{neck_clamp_node}.inputR")

        float_constant_node = cmds.createNode("floatConstant", name=f"{self.side}_neckStretchFactor_FCT")
        cmds.setAttr(f"{float_constant_node}.inFloat", 1)

        attributes_blender_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_neckStretch_BTA")
        cmds.connectAttr(f"{float_constant_node}.outFloat", f"{attributes_blender_node}.input[0]")
        cmds.connectAttr(f"{neck_clamp_node}.outputR", f"{attributes_blender_node}.input[1]")
        cmds.connectAttr(f"{self.neck_ctls[0]}.neckStretch", f"{attributes_blender_node}.attributesBlender")

        neck_stretch_value_float_math_node = cmds.createNode("floatMath", name=f"{self.side}_neckStretchValue_FLM")
        cmds.setAttr(f"{neck_stretch_value_float_math_node}.operation", 2)
        cmds.connectAttr(f"{attributes_blender_node}.output", f"{neck_stretch_value_float_math_node}.floatA")
        cmds.setAttr(f"{neck_stretch_value_float_math_node}.floatB", cmds.getAttr(f"{self.neck_chain[1]}.translateY"))

        for jnt in chain:
            cmds.connectAttr(f"{neck_stretch_value_float_math_node}.outFloat", f"{jnt}.translateY")

    def reversed_neck(self):

        """
        Reverse the neck chain to create a mirrored version for the opposite side.
        """
        cmds.select(clear=True)
        reversed_module_trn = cmds.createNode("transform", name=f"{self.side}_neckReverseModule_GRP", ss=True, p=self.module_trn)
        reversed_neck_chain = []

        for i, jnt in enumerate(reversed(self.neck_chain)):
            
            new_jnt = cmds.joint(name=f"{self.side}_neck0{i}Reverse_JNT")
            cmds.matchTransform(new_jnt, jnt, pos=True, rot=True, scl=False)
            reversed_neck_chain.append(new_jnt)

        cmds.parent(reversed_neck_chain[0], reversed_module_trn)
        
        reversed_neck_crv = cmds.reverseCurve(self.neck_crv, name=f"{self.side}_neckReverse_CRV", ch=True, rpo=False)
        reversed_ik_handle = cmds.ikHandle(sj=reversed_neck_chain[0], ee=reversed_neck_chain[-1], name=f"{self.side}_neckReverse_HDL", sol="ikSplineSolver", c=reversed_neck_crv[0], ccv=False)
        cmds.parent(reversed_ik_handle[0], reversed_module_trn)

        offset_npc_node = cmds.createNode("nearestPointOnCurve", name=f"{self.side}_neckReverse_NPC")
        cmds.connectAttr(f"{self.neck_crv}.worldSpace[0]", f"{offset_npc_node}.inputCurve")
        decompose_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_neckReverse_DCM")
        cmds.connectAttr(f"{reversed_neck_chain[-1]}.worldMatrix[0]", f"{decompose_node}.inputMatrix")
        cmds.connectAttr(f"{decompose_node}.outputTranslate", f"{offset_npc_node}.inPosition")

        float_constant_node = cmds.createNode("floatConstant", name=f"{self.side}_neckReverseOffsetInitialValue_FCT")
        cmds.setAttr(f"{float_constant_node}.inFloat", 0)

        blend_two_attr_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_neckReverseOffset_BTA")
        cmds.connectAttr(f"{float_constant_node}.outFloat", f"{blend_two_attr_node}.input[0]")
        cmds.connectAttr(f"{offset_npc_node}.parameter", f"{blend_two_attr_node}.input[1]")
        cmds.connectAttr(f"{self.neck_ctls[0]}.Offset", f"{blend_two_attr_node}.attributesBlender")
        cmds.connectAttr(f"{blend_two_attr_node}.output", f"{self.ik_handle[0]}.offset")

        self.stretch_callback(reversed_neck_chain, reversed_neck_crv[0])

    def attatched_fk(self):

        """
        Set up the FK functionality for the neck module.
        """
        # Create the attribute for FK in the neck controller
        cmds.addAttr(self.neck_ctls[0], longName="FK", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.neck_ctls[0]}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.neck_ctls[0], longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        fk_controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckFKControllers_GRP", ss=True, p=self.neck_ctls[0])
        cmds.setAttr(f"{fk_controllers_grp}.inheritsTransform", 0)
        cmds.connectAttr(f"{self.neck_ctls[0]}.FK_Vis", f"{fk_controllers_grp}.visibility")

        # Create the FK controllers
        fk_nodes = []
        fk_controllers = []
        
        for i, jnt in enumerate(self.neck_chain):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "FK"), offset=["GRP"])
            cmds.parent(fk_node[0], fk_controllers_grp)
            self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            
            if i == 0:

                cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{fk_node[0]}.offsetParentMatrix")

            else:

                mult_matrix_node = cmds.createNode("multMatrix", name=jnt.replace("_JNT", "_MMX"))
                cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{mult_matrix_node}.matrixIn[0]")
                cmds.connectAttr(f"{self.neck_chain[i-1]}.worldInverseMatrix[0]", f"{mult_matrix_node}.matrixIn[1]")
                cmds.connectAttr(f"{fk_controllers[-1]}.worldMatrix[0]", f"{mult_matrix_node}.matrixIn[2]")
                cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{fk_node[0]}.offsetParentMatrix")

            fk_nodes.append(fk_node[0])
            fk_controllers.append(fk_ctl)

        self.fk_joints = []
        self.skinning_joints = []

        fk_joints_grp = cmds.createNode("transform", name=f"{self.side}_neckFkJoints_GRP", ss=True, p=self.module_trn)

        for ctl in fk_controllers:

            cmds.select(clear=True)
            jnt = cmds.joint(name=ctl.replace("_CTL", "_JNT"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")
            self.fk_joints.append(jnt)
            cmds.parent(jnt, fk_joints_grp)
            cmds.setAttr(f"{jnt}.inheritsTransform", 0)

            skinning_jnt = cmds.duplicate(jnt, name=jnt.replace("FK_JNT", "Skinning_JNT"))[0]
            cmds.parent(skinning_jnt, self.skeleton_grp)
            cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")
            self.skinning_joints.append(skinning_jnt)

        
    
    def squash(self):

        """
        Set up the squash functionality for the neck module.
        """
        # Create the attribute for squash in the body controller
        cmds.addAttr(self.neck_ctls[0], longName="SQUASH", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.neck_ctls[0]}.SQUASH", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.neck_ctls[0], longName="Volume_Preservation", niceName="Volume Preservation", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.neck_ctls[0], longName="Falloff", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.neck_ctls[0], longName="Max_Pos", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)

        squash_crv = cmds.duplicate(self.neck_crv, name=f"{self.side}_neckSquash_CRV")[0]
        
        for i, ctl in enumerate(self.neck_ctls):

            decompose_node = cmds.createNode("decomposeMatrix", name=ctl.replace("_CTL", "Squash_DCM"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{decompose_node}.inputMatrix")
            if i == 0:
                cmds.connectAttr(f"{decompose_node}.outputTranslate", f"{squash_crv}.controlPoints[{i}]")
            else:
                cmds.connectAttr(f"{decompose_node}.outputTranslate", f"{squash_crv}.controlPoints[{self.indices[-1]}]")

        neck_trn = cmds.createNode("transform", name=f"{self.side}_neckSquash_TRN", ss=True, p=self.module_trn)
        self.lock_attributes(neck_trn, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(neck_trn, longName="Max_Stretch_Length", attributeType="float", min=1, defaultValue=2, keyable=True)
        cmds.addAttr(neck_trn, longName="Min_Stretch_Length", attributeType="float", min=0, defaultValue=0.5, max=1, keyable=True)
        cmds.addAttr(neck_trn, longName="Min_Stretch_Effect", attributeType="float", min=1,  defaultValue=2, keyable=True)
        cmds.addAttr(neck_trn, longName="Max_Stretch_Effect", attributeType="float", min=0, defaultValue=0.5, max=1, keyable=True)
        cmds.addAttr(neck_trn, longName="VOLUME", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{neck_trn}.VOLUME", lock=True, keyable=False, channelBox=True)
        for i, jnt in enumerate(self.neck_chain):
            if i == 0:
                value = 0.05
            elif i == len(self.neck_chain) - 1:
                value = 0.95
            else:
                value = 1 / (len(self.neck_chain) - 1) * i
            cmds.addAttr(neck_trn, longName=f"neck0{i}_Squash_Percentage", attributeType="float", min=0, max=1, defaultValue=value, keyable=True)

        # First part
        curve_info_node = cmds.createNode("curveInfo", name=f"{self.side}_neckSquashCurve_CIN", ss=True)
        cmds.connectAttr(f"{squash_crv}.worldSpace[0]", f"{curve_info_node}.inputCurve")
        
        squash_base_length = cmds.createNode("floatMath", name=f"{self.side}_neckSquashBaseLength_FLM", ss=True)
        cmds.setAttr(f"{squash_base_length}.operation", 2)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{squash_base_length}.floatA")
        cmds.setAttr(f"{squash_base_length}.floatB", cmds.getAttr(f"{curve_info_node}.arcLength"))
        
        neck_squash_factor_node = cmds.createNode("floatMath", name=f"{self.side}_neckSquashFactor_FLM", ss=True)
        cmds.setAttr(f"{neck_squash_factor_node}.operation", 3)
        cmds.connectAttr(f"{curve_info_node}.arcLength", f"{neck_squash_factor_node}.floatA")
        cmds.connectAttr(f"{squash_base_length}.outFloat", f"{neck_squash_factor_node}.floatB")

        # Second part
        volume_high_bound_node = cmds.createNode("remapValue", name=f"{self.side}_neckVolumeHighBound_RMV", ss=True)
        cmds.connectAttr(f"{self.neck_ctls[0]}.Falloff", f"{volume_high_bound_node}.inputValue")
        cmds.connectAttr(f"{self.neck_ctls[0]}.Max_Pos", f"{volume_high_bound_node}.outputMin")
        cmds.setAttr(f"{volume_high_bound_node}.outputMax", 0.99)  # Set the output max to 0.99

        volume_low_bound_node = cmds.createNode("remapValue", name=f"{self.side}_neckVolumeLowBound_RMV", ss=True)
        cmds.connectAttr(f"{self.neck_ctls[0]}.Falloff", f"{volume_low_bound_node}.inputValue")
        cmds.connectAttr(f"{self.neck_ctls[0]}.Max_Pos", f"{volume_low_bound_node}.outputMin")
        cmds.setAttr(f"{volume_low_bound_node}.outputMax", 0.01)  # Set the output max to 0.01

        volume_high_bound_negative_node = cmds.createNode("floatMath", name=f"{self.side}_neckVolumeHighBoundNegative_FLM", ss=True)
        cmds.setAttr(f"{volume_high_bound_negative_node}.operation", 1)  # Negate the value
        cmds.setAttr(f"{volume_high_bound_negative_node}.floatA", 2)
        cmds.connectAttr(f"{volume_high_bound_node}.outValue", f"{volume_high_bound_negative_node}.floatB")

        volume_low_bound_negative_node = cmds.createNode("floatMath", name=f"{self.side}_neckVolumeLowBoundNegative_FLM", ss=True)
        cmds.setAttr(f"{volume_low_bound_negative_node}.operation", 1)  # Negate the value
        cmds.setAttr(f"{volume_low_bound_negative_node}.floatA", 0) 
        cmds.connectAttr(f"{volume_low_bound_node}.outValue", f"{volume_low_bound_negative_node}.floatB")

        volume_stretch_delta_node = cmds.createNode("floatMath", name=f"{self.side}_neckVolumeStretchDelta_FLM", ss=True)
        cmds.setAttr(f"{volume_stretch_delta_node}.operation", 1)  # Subtract the values
        cmds.setAttr(f"{volume_stretch_delta_node}.floatA", 1)  # Set the first value to 1
        cmds.connectAttr(f"{neck_trn}.Max_Stretch_Effect", f"{volume_stretch_delta_node}.floatB")

        volume_squash_delta_node = cmds.createNode("floatMath", name=f"{self.side}_neckVolumeSquashDelta_FLM", ss=True)
        cmds.setAttr(f"{volume_squash_delta_node}.operation", 1)  # Subtract the values
        cmds.setAttr(f"{volume_squash_delta_node}.floatB", 1)  # Set the first value to 1
        cmds.connectAttr(f"{neck_trn}.Min_Stretch_Effect", f"{volume_stretch_delta_node}.floatA")


        for i, jnt in enumerate(self.fk_joints):

            neck_volume_factor_node = cmds.createNode("remapValue", name=f"{self.side}_neckVolumeFactor0{i}_RMV", ss=True)
            cmds.setAttr(f"{neck_volume_factor_node}.inputMin", 0)
            cmds.setAttr(f"{neck_volume_factor_node}.inputMax", 1)
            cmds.setAttr(f"{neck_volume_factor_node}.outputMin", 0)
            cmds.setAttr(f"{neck_volume_factor_node}.outputMax", 1)
            cmds.connectAttr(f"{neck_trn}.neck0{i}_Squash_Percentage", f"{neck_volume_factor_node}.inputValue")
            cmds.connectAttr(f"{volume_low_bound_negative_node}.outFloat", f"{neck_volume_factor_node}.value[0].value_Position")
            cmds.connectAttr(f"{volume_low_bound_node}.outValue", f"{neck_volume_factor_node}.value[1].value_Position")
            cmds.connectAttr(f"{volume_high_bound_node}.outValue", f"{neck_volume_factor_node}.value[2].value_Position")
            cmds.connectAttr(f"{volume_high_bound_negative_node}.outFloat", f"{neck_volume_factor_node}.value[3].value_Position")

            stretch_factor_node = cmds.createNode("floatMath", name=f"{self.side}_neckVolumeStretchFactor0{i}_FLM", ss=True)
            cmds.setAttr(f"{stretch_factor_node}.operation", 2)
            cmds.connectAttr(f"{neck_volume_factor_node}.outValue", f"{stretch_factor_node}.floatA")
            cmds.connectAttr(f"{volume_stretch_delta_node}.outFloat", f"{stretch_factor_node}.floatB")

            squash_factor_node = cmds.createNode("floatMath", name=f"{self.side}_neckVolumeSquashFactor0{i}_FLM", ss=True)
            cmds.setAttr(f"{squash_factor_node}.operation", 2)
            cmds.connectAttr(f"{neck_volume_factor_node}.outValue", f"{squash_factor_node}.floatA")
            cmds.connectAttr(f"{volume_squash_delta_node}.outFloat", f"{squash_factor_node}.floatB")

            stretch_full_value_node = cmds.createNode("floatMath", name=f"{self.side}_neckStretchFullValue0{i}_FLM", ss=True)
            cmds.setAttr(f"{stretch_full_value_node}.operation", 1)  
            cmds.setAttr(f"{stretch_full_value_node}.floatA", 1)
            cmds.connectAttr(f"{stretch_factor_node}.outFloat", f"{stretch_full_value_node}.floatB")

            squash_full_value_node = cmds.createNode("floatMath", name=f"{self.side}_neckSquashFullValue0{i}_FLM", ss=True)
            cmds.setAttr(f"{squash_full_value_node}.operation", 1)
            cmds.setAttr(f"{squash_full_value_node}.floatB", 1)
            cmds.connectAttr(f"{squash_factor_node}.outFloat", f"{squash_full_value_node}.floatA")

            volume_node = cmds.createNode("remapValue", name=f"{self.side}_neckVolume0{i}_RMV", ss=True)
            cmds.connectAttr(f"{neck_squash_factor_node}.outFloat", f"{volume_node}.inputValue")
            cmds.connectAttr(f"{neck_trn}.Min_Stretch_Length", f"{volume_node}.value[0].value_Position")
            cmds.connectAttr(f"{stretch_full_value_node}.outFloat", f"{volume_node}.value[0].value_FloatValue")
            cmds.setAttr(f"{volume_node}.value[1].value_Position", 1)
            cmds.setAttr(f"{volume_node}.value[1].value_FloatValue", 1)
            cmds.connectAttr(f"{neck_trn}.Max_Stretch_Length", f"{volume_node}.value[2].value_Position")
            cmds.connectAttr(f"{squash_full_value_node}.outFloat", f"{volume_node}.value[2].value_FloatValue")

            condition_node = cmds.createNode("condition", name=f"{self.side}_neckVolumeCondition0{i}_CND", ss=True)
            cmds.setAttr(f"{condition_node}.operation", 0)
            cmds.setAttr(f"{condition_node}.secondTerm", 1)
            float_constant_node = cmds.createNode("floatConstant", name=f"{self.side}_neckVolumeConditionInitialValue0{i}_FCT", ss=True)
            cmds.connectAttr(f"{self.neck_ctls[0]}.Volume_Preservation", f"{condition_node}.firstTerm")
            cmds.connectAttr(f"{float_constant_node}.outFloat", f"{condition_node}.colorIfFalseR")
            cmds.connectAttr(f"{volume_node}.outValue", f"{condition_node}.colorIfTrueR")

            cmds.connectAttr(f"{condition_node}.outColorR", f"{jnt}.scaleX")
            cmds.connectAttr(f"{condition_node}.outColorR", f"{jnt}.scaleZ")

    def local_head(self):

        """
        Create the local head setup to have the head follow the neck's movement.
        """

        self.head_jnt = cmds.joint(name=f"{self.side}_head_JNT")
        cmds.parent(self.head_jnt, self.module_trn)

        decompose_translation = cmds.createNode("decomposeMatrix", name=f"{self.side}_headTranslation_DCM")
        cmds.connectAttr(f"{self.neck_chain[-1]}.worldMatrix[0]", f"{decompose_translation}.inputMatrix")
        decompose_rotation = cmds.createNode("decomposeMatrix", name=f"{self.side}_headRotation_DCM")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{decompose_rotation}.inputMatrix")
        compose_head = cmds.createNode("composeMatrix", name=f"{self.side}_head_CMP")
        cmds.connectAttr(f"{decompose_translation}.outputTranslate", f"{compose_head}.inputTranslate")
        cmds.connectAttr(f"{decompose_rotation}.outputRotate", f"{compose_head}.inputRotate")
        cmds.connectAttr(f"{compose_head}.outputMatrix", f"{self.head_jnt}.offsetParentMatrix")

        head_skinning_jnt = cmds.joint(name=f"{self.side}_headSkinning_JNT")
        cmds.parent(head_skinning_jnt, self.skeleton_grp)
        cmds.connectAttr(f"{self.head_jnt}.worldMatrix[0]", f"{head_skinning_jnt}.offsetParentMatrix")

        cmds.addAttr(f"{self.neck_ctls[-1]}", longName="SPACE_SWITCH", attributeType="enum", enumName="____")
        cmds.setAttr(f"{self.neck_ctls[-1]}.SPACE_SWITCH", keyable=False, channelBox=True)
        cmds.addAttr(f"{self.neck_ctls[-1]}", longName="Follow_Neck", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        blend_matrix = cmds.createNode("blendMatrix", name=f"{self.side}_head_BMX")
        neck_offset = cmds.createNode("multMatrix", name=f"{self.side}_neckOffset_MMX")
        cmds.connectAttr(f"{self.neck_ctls[0]}.worldMatrix[0]", f"{neck_offset}.matrixIn[0]")
        cmds.connectAttr(f"{self.neck_nodes[0]}.worldInverseMatrix[0]", f"{neck_offset}.matrixIn[1]")

        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{blend_matrix}.inputMatrix")
        cmds.connectAttr(f"{neck_offset}.matrixSum", f"{blend_matrix}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.Follow_Neck", f"{blend_matrix}.target[0].weight")

        cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{self.neck_nodes[-1]}.offsetParentMatrix")








        

        

