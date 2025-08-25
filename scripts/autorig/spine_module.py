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

class SpineModule(object):

    def __init__(self):

        """
        Initialize the SpineModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleX")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleY")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleZ")
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.ik_setup()
        self.controller_creation()
        self.stretch_callback(self.spine_chain, self.spine_crv)
        self.reversed_spine()
        self.attatched_fk()
        self.squash()
        
        data_manager.DataExport().append_data("basic_structure",
                            {
                                "local_hip_ctl": self.local_hip_ctl,
                                "body_ctl": self.body_ctl,
                                "local_chest_ctl": self.local_chest_ctl
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

        """
        Load the spine guides for the specified side and parent them to the module transform.
        """

        self.spine_chain = guides_manager.get_guides(f"{self.side}_spine00_JNT")
        cmds.parent(self.spine_chain[0], self.module_trn)

    def ik_setup(self):

        """
        Set up the IK system for the spine module.
        """

        # Get positions for first, second, mid, penultimate, and last joints
        num_joints = len(self.spine_chain)
        self.indices = [0, 1, num_joints // 2, num_joints - 2, num_joints - 1]
        positions = [cmds.xform(self.spine_chain[i], q=True, ws=True, t=True) for i in self.indices]
        self.spine_crv = cmds.curve(n=f"{self.side}_spine_CRV", d=3, p=positions)
        spine_crv_shape = cmds.listRelatives(self.spine_crv, shapes=True)[0]
        cmds.rename(spine_crv_shape, f"{self.side}_spineShape_CRV")
        self.ik_handle = cmds.ikHandle(sj=self.spine_chain[0], ee=self.spine_chain[-1], name=f"{self.side}_spine_HDL", sol="ikSplineSolver", c=self.spine_crv, ccv=False)
        cmds.parent(self.ik_handle[0], self.module_trn)
        cmds.setAttr(f"{self.ik_handle[0]}.dTwistControlEnable", 1)
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpType", 4)
        cmds.setAttr(f"{self.ik_handle[0]}.dForwardAxis", 2) # Y points next joint
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpAxis", 6) # X makes world position
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpVectorX", 1)
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpVectorY", 0)
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpVectorZ", 0)
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpVectorEndX", 1)
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpVectorEndY", 0)
        cmds.setAttr(f"{self.ik_handle[0]}.dWorldUpVectorEndZ", 0)
       

    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC"])
        self.lock_attributes(self.body_ctl, ["sx", "sy", "sz", "v"])
        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_localHip", offset=["GRP", "SPC"])
        self.lock_attributes(self.local_hip_ctl, ["sx", "sy", "sz", "v"])
        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC"])
        self.lock_attributes(self.local_chest_ctl, ["sx", "sy", "sz", "v"])
        cmds.matchTransform(self.body_nodes[0], self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.connectAttr(f"{self.body_ctl}.worldMatrix[0]", f"{self.local_hip_nodes[0]}.offsetParentMatrix")
        cmds.parent(self.body_nodes[0], self.controllers_grp)
        cmds.parent(self.local_hip_nodes[0], self.controllers_grp)
        cmds.parent(self.local_chest_nodes[0], self.controllers_grp)

        # Create the local hip joint
        cmds.select(clear=True)
        local_hip_jnt = cmds.joint(name=f"{self.side}_localHip_JNT")
        cmds.parent(local_hip_jnt, self.module_trn)
        decompose_translation_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_localHipTranslation_DCM")
        cmds.connectAttr(f"{self.spine_chain[0]}.worldMatrix[0]", f"{decompose_translation_node}.inputMatrix")
        decompose_rotation_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_localHipRotation_DCM")
        cmds.connectAttr(f"{self.local_hip_ctl}.worldMatrix[0]", f"{decompose_rotation_node}.inputMatrix")
        compose_matrix = cmds.createNode("composeMatrix", name=f"{self.side}_localHip_CMP")
        cmds.connectAttr(f"{decompose_translation_node}.outputTranslate", f"{compose_matrix}.inputTranslate")
        cmds.connectAttr(f"{decompose_rotation_node}.outputRotate", f"{compose_matrix}.inputRotate")
        cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{local_hip_jnt}.offsetParentMatrix")
        local_hip_skinning_jnt = cmds.joint(name=f"{self.side}_localHipSkinning_JNT")
        cmds.connectAttr(f"{local_hip_jnt}.worldMatrix[0]", f"{local_hip_skinning_jnt}.offsetParentMatrix")
        cmds.setAttr(f"{self.local_hip_nodes[0]}.inheritsTransform", 0)
        cmds.parent(local_hip_skinning_jnt, self.skeleton_grp)

        

        self.spine_nodes = []
        self.spine_ctls = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            if i == 0 or i == len(self.spine_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])
                
                cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 0:

                    cmds.parent(corner_nodes[0], self.body_ctl)

                else:

                    cmds.parent(self.spine_nodes[-1], corner_ctl)
                    cmds.parent(corner_nodes[0], self.spine_ctls[(len(self.spine_ctls) // 2)])

                self.spine_nodes.append(corner_nodes[0])
                self.spine_ctls.append(corner_ctl)

            if i == (len(self.spine_chain) - 1) // 2:

                mid_nodes, mid_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])

                cmds.parent(mid_nodes[0], self.spine_ctls[0])
                cmds.matchTransform(mid_nodes[0], self.spine_chain[(len(self.spine_chain) // 2) - 1], pos=True, rot=True, scl=False)
                self.spine_nodes.append(mid_nodes[0])
                self.spine_ctls.append(mid_ctl)

            
            if i == 1 or i == len(self.spine_chain) - 2:

                tan_nodes, tan_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "Tan"), offset=["GRP"])

                cmds.matchTransform(tan_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 1:

                    cmds.parent(tan_nodes[0], self.spine_ctls[-1])

                self.spine_nodes.append(tan_nodes[0])
                self.spine_ctls.append(tan_ctl)

        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{self.ik_handle[0]}.dWorldUpMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{self.ik_handle[0]}.dWorldUpMatrixEnd")
        decompose_rotation_node_local_chest = cmds.createNode("decomposeMatrix", name=f"{self.side}_localChestRotation_DCM")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{decompose_rotation_node_local_chest}.inputMatrix")
        decompose_translation_node_local_chest = cmds.createNode("decomposeMatrix", name=f"{self.side}_localChestTranslation_DCM")
        cmds.connectAttr(f"{self.spine_chain[-1]}.worldMatrix[0]", f"{decompose_translation_node_local_chest}.inputMatrix")
        compose_matrix_local_chest = cmds.createNode("composeMatrix", name=f"{self.side}_localChest_CMP")
        cmds.connectAttr(f"{decompose_translation_node_local_chest}.outputTranslate", f"{compose_matrix_local_chest}.inputTranslate")
        cmds.connectAttr(f"{decompose_rotation_node_local_chest}.outputRotate", f"{compose_matrix_local_chest}.inputRotate")
        cmds.connectAttr(f"{compose_matrix_local_chest}.outputMatrix", f"{self.local_chest_nodes[0]}.offsetParentMatrix")
        cmds.select(clear=True)
        local_chest_jnt = cmds.joint(name=f"{self.side}_localChest_JNT")
        cmds.parent(local_chest_jnt, self.module_trn)
        cmds.connectAttr(f"{self.local_chest_nodes[0]}.worldMatrix[0]", f"{local_chest_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        local_chest_skinning_jnt = cmds.joint(name=f"{self.side}_localChestSkinning_JNT")
        cmds.connectAttr(f"{local_chest_jnt}.worldMatrix[0]", f"{local_chest_skinning_jnt}.offsetParentMatrix")
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.parent(local_chest_skinning_jnt, self.skeleton_grp)

        for i , ctl in enumerate(self.spine_ctls):
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            decompose_node = cmds.createNode("decomposeMatrix", name=ctl.replace("_CTL", "_DCM"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{decompose_node}.inputMatrix")
            cmds.connectAttr(f"{decompose_node}.outputTranslate", f"{self.spine_crv}.controlPoints[{i}]")

    def stretch_callback(self, chain, crv):

        """
        Set up the stretch functionality for the spine module.
        """

        # Create the attribute for stretch in the body controller
        if not cmds.attributeQuery("STRETCH", node=self.body_ctl, exists=True):
            cmds.addAttr(self.body_ctl, longName="STRETCH", attributeType="enum", enumName="____", keyable=True)
            cmds.setAttr(f"{self.body_ctl}.STRETCH", lock=True, keyable=False, channelBox=True)
            cmds.addAttr(self.body_ctl, longName="spineStretch", niceName="Spine Stretch", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
            cmds.addAttr(self.body_ctl, longName="Stretch_Min", niceName="Stretch Min", attributeType="float", min=0, max=1, defaultValue=0.8, keyable=True)
            cmds.addAttr(self.body_ctl, longName="Stretch_Max", niceName="Stretch Max", attributeType="float", min=1, defaultValue=1.2, keyable=True)
            cmds.addAttr(self.body_ctl, longName="Offset", niceName="Offset", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        else:
            pass

        # Create connections
        curve_info_node = cmds.createNode("curveInfo", name=f"{self.side}_spineCurve_CIN")
        cmds.connectAttr(f"{crv}.worldSpace[0]", f"{curve_info_node}.inputCurve")

        float_math_arc_length_node = cmds.createNode("floatMath", name=f"{self.side}_spineArcLength_FLM")
        cmds.setAttr(f"{float_math_arc_length_node}.operation", 2)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{float_math_arc_length_node}.floatA")
        cmds.setAttr(f"{float_math_arc_length_node}.floatB", cmds.getAttr(f"{curve_info_node}.arcLength")) # This is the original arc length of the curve

        float_math_stretch_factor_node = cmds.createNode("floatMath", name=f"{self.side}_spineStretchFactor_FLM")
        cmds.setAttr(f"{float_math_stretch_factor_node}.operation", 3)
        cmds.connectAttr(f"{curve_info_node}.arcLength", f"{float_math_stretch_factor_node}.floatA")
        cmds.connectAttr(f"{float_math_arc_length_node}.outFloat", f"{float_math_stretch_factor_node}.floatB")

        spine_clamp_node = cmds.createNode("clamp", name=f"{self.side}_spineStretchFactor_CLP")
        cmds.connectAttr(f"{self.body_ctl}.Stretch_Min", f"{spine_clamp_node}.minR")
        cmds.connectAttr(f"{self.body_ctl}.Stretch_Max", f"{spine_clamp_node}.maxR")
        cmds.connectAttr(f"{float_math_stretch_factor_node}.outFloat", f"{spine_clamp_node}.inputR")

        float_constant_node = cmds.createNode("floatConstant", name=f"{self.side}_spineStretchFactor_FCT")
        cmds.setAttr(f"{float_constant_node}.inFloat", 1)

        attributes_blender_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineStretch_BTA")
        cmds.connectAttr(f"{float_constant_node}.outFloat", f"{attributes_blender_node}.input[0]")
        cmds.connectAttr(f"{spine_clamp_node}.outputR", f"{attributes_blender_node}.input[1]")
        cmds.connectAttr(f"{self.body_ctl}.spineStretch", f"{attributes_blender_node}.attributesBlender")

        spine_stretch_value_float_math_node = cmds.createNode("floatMath", name=f"{self.side}_spineStretchValue_FLM")
        cmds.setAttr(f"{spine_stretch_value_float_math_node}.operation", 2)
        cmds.connectAttr(f"{attributes_blender_node}.output", f"{spine_stretch_value_float_math_node}.floatA")
        cmds.setAttr(f"{spine_stretch_value_float_math_node}.floatB", cmds.getAttr(f"{self.spine_chain[1]}.translateY"))

        for jnt in chain:
            cmds.connectAttr(f"{spine_stretch_value_float_math_node}.outFloat", f"{jnt}.translateY")

    def reversed_spine(self):

        """
        Reverse the spine chain to create a mirrored version for the opposite side.
        """
        cmds.select(clear=True)
        reversed_module_trn = cmds.createNode("transform", name=f"{self.side}_spineReverseModule_GRP", ss=True, p=self.module_trn)
        reversed_spine_chain = []

        for i, jnt in enumerate(reversed(self.spine_chain)):
            
            new_jnt = cmds.joint(name=f"{self.side}_spine0{i}Reverse_JNT")
            cmds.matchTransform(new_jnt, jnt, pos=True, rot=True, scl=False)
            reversed_spine_chain.append(new_jnt)

        cmds.parent(reversed_spine_chain[0], reversed_module_trn)
        
        reversed_spine_crv = cmds.reverseCurve(self.spine_crv, name=f"{self.side}_spineReverse_CRV", ch=True, rpo=False)
        reversed_ik_handle = cmds.ikHandle(sj=reversed_spine_chain[0], ee=reversed_spine_chain[-1], name=f"{self.side}_spineReverse_HDL", sol="ikSplineSolver", c=reversed_spine_crv[0], ccv=False)
        cmds.parent(reversed_ik_handle[0], reversed_module_trn)

        offset_npc_node = cmds.createNode("nearestPointOnCurve", name=f"{self.side}_spineReverse_NPC")
        cmds.connectAttr(f"{self.spine_crv}.worldSpace[0]", f"{offset_npc_node}.inputCurve")
        decompose_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_spineReverse_DCM")
        cmds.connectAttr(f"{reversed_spine_chain[-1]}.worldMatrix[0]", f"{decompose_node}.inputMatrix")
        cmds.connectAttr(f"{decompose_node}.outputTranslate", f"{offset_npc_node}.inPosition")

        float_constant_node = cmds.createNode("floatConstant", name=f"{self.side}_spineReverseOffsetInitialValue_FCT")
        cmds.setAttr(f"{float_constant_node}.inFloat", 0)

        blend_two_attr_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineReverseOffset_BTA")
        cmds.connectAttr(f"{float_constant_node}.outFloat", f"{blend_two_attr_node}.input[0]")
        cmds.connectAttr(f"{offset_npc_node}.parameter", f"{blend_two_attr_node}.input[1]")
        cmds.connectAttr(f"{self.body_ctl}.Offset", f"{blend_two_attr_node}.attributesBlender")
        cmds.connectAttr(f"{blend_two_attr_node}.output", f"{self.ik_handle[0]}.offset")

        self.stretch_callback(reversed_spine_chain, reversed_spine_crv[0])

    def attatched_fk(self):

        """
        Set up the FK functionality for the spine module.
        """
        # Create the attribute for FK in the body controller
        cmds.addAttr(self.body_ctl, longName="FK", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        fk_controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineFKControllers_GRP", ss=True, p=self.body_ctl)
        cmds.setAttr(f"{fk_controllers_grp}.inheritsTransform", 0)
        cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_controllers_grp}.visibility")

        # Create the FK controllers
        fk_nodes = []
        fk_controllers = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "FK"), offset=["GRP"])
            cmds.parent(fk_node[0], fk_controllers_grp)
            self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            
            if i == 0:

                cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{fk_node[0]}.offsetParentMatrix")

            else:

                mult_matrix_node = cmds.createNode("multMatrix", name=jnt.replace("_JNT", "_MMX"))
                cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{mult_matrix_node}.matrixIn[0]")
                cmds.connectAttr(f"{self.spine_chain[i-1]}.worldInverseMatrix[0]", f"{mult_matrix_node}.matrixIn[1]")
                cmds.connectAttr(f"{fk_controllers[-1]}.worldMatrix[0]", f"{mult_matrix_node}.matrixIn[2]")
                cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{fk_node[0]}.offsetParentMatrix")

            fk_nodes.append(fk_node[0])
            fk_controllers.append(fk_ctl)

        self.fk_joints = []
        self.skinning_joints = []

        fk_joints_grp = cmds.createNode("transform", name=f"{self.side}_spineFkJoints_GRP", ss=True, p=self.module_trn)

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
        Set up the squash functionality for the spine module.
        """
        # Create the attribute for squash in the body controller
        cmds.addAttr(self.body_ctl, longName="SQUASH", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.SQUASH", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="Volume_Preservation", niceName="Volume Preservation", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.body_ctl, longName="Falloff", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.body_ctl, longName="Max_Pos", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)

        squash_crv = cmds.duplicate(self.spine_crv, name=f"{self.side}_spineSquash_CRV")[0]
        
        for i, ctl in enumerate(self.spine_ctls):

            decompose_node = cmds.createNode("decomposeMatrix", name=ctl.replace("_CTL", "Squash_DCM"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{decompose_node}.inputMatrix")
            cmds.connectAttr(f"{decompose_node}.outputTranslate", f"{squash_crv}.controlPoints[{i}]")

        spine_trn = cmds.createNode("transform", name=f"{self.side}_spineSquash_TRN", ss=True, p=self.module_trn)
        self.lock_attributes(spine_trn, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(spine_trn, longName="Max_Stretch_Length", attributeType="float", min=1, defaultValue=2, keyable=True)
        cmds.addAttr(spine_trn, longName="Min_Stretch_Length", attributeType="float", min=0, defaultValue=0.5, max=1, keyable=True)
        cmds.addAttr(spine_trn, longName="Min_Stretch_Effect", attributeType="float", min=1,  defaultValue=2, keyable=True)
        cmds.addAttr(spine_trn, longName="Max_Stretch_Effect", attributeType="float", min=0, defaultValue=0.5, max=1, keyable=True)
        cmds.addAttr(spine_trn, longName="VOLUME", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{spine_trn}.VOLUME", lock=True, keyable=False, channelBox=True)
        for i, jnt in enumerate(self.spine_chain):
            if i == 0:
                value = 0.05
            elif i == len(self.spine_chain) - 1:
                value = 0.95
            else:
                value = 1 / (len(self.spine_chain) - 1) * i
            cmds.addAttr(spine_trn, longName=f"Spine0{i}_Squash_Percentage", attributeType="float", min=0, max=1, defaultValue=value, keyable=True)

        # First part
        curve_info_node = cmds.createNode("curveInfo", name=f"{self.side}_spineSquashCurve_CIN", ss=True)
        cmds.connectAttr(f"{squash_crv}.worldSpace[0]", f"{curve_info_node}.inputCurve")
        
        squash_base_length = cmds.createNode("floatMath", name=f"{self.side}_spineSquashBaseLength_FLM", ss=True)
        cmds.setAttr(f"{squash_base_length}.operation", 2)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{squash_base_length}.floatA")
        cmds.setAttr(f"{squash_base_length}.floatB", cmds.getAttr(f"{curve_info_node}.arcLength"))
        
        spine_squash_factor_node = cmds.createNode("floatMath", name=f"{self.side}_spineSquashFactor_FLM", ss=True)
        cmds.setAttr(f"{spine_squash_factor_node}.operation", 3)
        cmds.connectAttr(f"{curve_info_node}.arcLength", f"{spine_squash_factor_node}.floatA")
        cmds.connectAttr(f"{squash_base_length}.outFloat", f"{spine_squash_factor_node}.floatB")

        # Second part
        volume_high_bound_node = cmds.createNode("remapValue", name=f"{self.side}_spineVolumeHighBound_RMV", ss=True)
        cmds.connectAttr(f"{self.body_ctl}.Falloff", f"{volume_high_bound_node}.inputValue")
        cmds.connectAttr(f"{self.body_ctl}.Max_Pos", f"{volume_high_bound_node}.outputMin")
        cmds.setAttr(f"{volume_high_bound_node}.outputMax", 0.99)  # Set the output max to 0.99

        volume_low_bound_node = cmds.createNode("remapValue", name=f"{self.side}_spineVolumeLowBound_RMV", ss=True)
        cmds.connectAttr(f"{self.body_ctl}.Falloff", f"{volume_low_bound_node}.inputValue")
        cmds.connectAttr(f"{self.body_ctl}.Max_Pos", f"{volume_low_bound_node}.outputMin")
        cmds.setAttr(f"{volume_low_bound_node}.outputMax", 0.01)  # Set the output max to 0.01

        volume_high_bound_negative_node = cmds.createNode("floatMath", name=f"{self.side}_spineVolumeHighBoundNegative_FLM", ss=True)
        cmds.setAttr(f"{volume_high_bound_negative_node}.operation", 1)  # Negate the value
        cmds.setAttr(f"{volume_high_bound_negative_node}.floatA", 2)
        cmds.connectAttr(f"{volume_high_bound_node}.outValue", f"{volume_high_bound_negative_node}.floatB")

        volume_low_bound_negative_node = cmds.createNode("floatMath", name=f"{self.side}_spineVolumeLowBoundNegative_FLM", ss=True)
        cmds.setAttr(f"{volume_low_bound_negative_node}.operation", 1)  # Negate the value
        cmds.setAttr(f"{volume_low_bound_negative_node}.floatA", 0) 
        cmds.connectAttr(f"{volume_low_bound_node}.outValue", f"{volume_low_bound_negative_node}.floatB")

        volume_stretch_delta_node = cmds.createNode("floatMath", name=f"{self.side}_spineVolumeStretchDelta_FLM", ss=True)
        cmds.setAttr(f"{volume_stretch_delta_node}.operation", 1)  # Subtract the values
        cmds.setAttr(f"{volume_stretch_delta_node}.floatA", 1)  # Set the first value to 1
        cmds.connectAttr(f"{spine_trn}.Max_Stretch_Effect", f"{volume_stretch_delta_node}.floatB")

        volume_squash_delta_node = cmds.createNode("floatMath", name=f"{self.side}_spineVolumeSquashDelta_FLM", ss=True)
        cmds.setAttr(f"{volume_squash_delta_node}.operation", 1)  # Subtract the values
        cmds.setAttr(f"{volume_squash_delta_node}.floatB", 1)  # Set the first value to 1
        cmds.connectAttr(f"{spine_trn}.Min_Stretch_Effect", f"{volume_stretch_delta_node}.floatA")


        for i, jnt in enumerate(self.fk_joints):

            spine_volume_factor_node = cmds.createNode("remapValue", name=f"{self.side}_spineVolumeFactor0{i}_RMV", ss=True)
            cmds.setAttr(f"{spine_volume_factor_node}.inputMin", 0)
            cmds.setAttr(f"{spine_volume_factor_node}.inputMax", 1)
            cmds.setAttr(f"{spine_volume_factor_node}.outputMin", 0)
            cmds.setAttr(f"{spine_volume_factor_node}.outputMax", 1)
            cmds.connectAttr(f"{spine_trn}.Spine0{i}_Squash_Percentage", f"{spine_volume_factor_node}.inputValue")
            cmds.connectAttr(f"{volume_low_bound_negative_node}.outFloat", f"{spine_volume_factor_node}.value[0].value_Position")
            cmds.connectAttr(f"{volume_low_bound_node}.outValue", f"{spine_volume_factor_node}.value[1].value_Position")
            cmds.connectAttr(f"{volume_high_bound_node}.outValue", f"{spine_volume_factor_node}.value[2].value_Position")
            cmds.connectAttr(f"{volume_high_bound_negative_node}.outFloat", f"{spine_volume_factor_node}.value[3].value_Position")

            stretch_factor_node = cmds.createNode("floatMath", name=f"{self.side}_spineVolumeStretchFactor0{i}_FLM", ss=True)
            cmds.setAttr(f"{stretch_factor_node}.operation", 2)
            cmds.connectAttr(f"{spine_volume_factor_node}.outValue", f"{stretch_factor_node}.floatA")
            cmds.connectAttr(f"{volume_stretch_delta_node}.outFloat", f"{stretch_factor_node}.floatB")

            squash_factor_node = cmds.createNode("floatMath", name=f"{self.side}_spineVolumeSquashFactor0{i}_FLM", ss=True)
            cmds.setAttr(f"{squash_factor_node}.operation", 2)
            cmds.connectAttr(f"{spine_volume_factor_node}.outValue", f"{squash_factor_node}.floatA")
            cmds.connectAttr(f"{volume_squash_delta_node}.outFloat", f"{squash_factor_node}.floatB")

            stretch_full_value_node = cmds.createNode("floatMath", name=f"{self.side}_spineStretchFullValue0{i}_FLM", ss=True)
            cmds.setAttr(f"{stretch_full_value_node}.operation", 1)  
            cmds.setAttr(f"{stretch_full_value_node}.floatA", 1)
            cmds.connectAttr(f"{stretch_factor_node}.outFloat", f"{stretch_full_value_node}.floatB")

            squash_full_value_node = cmds.createNode("floatMath", name=f"{self.side}_spineSquashFullValue0{i}_FLM", ss=True)
            cmds.setAttr(f"{squash_full_value_node}.operation", 1)
            cmds.setAttr(f"{squash_full_value_node}.floatB", 1)
            cmds.connectAttr(f"{squash_factor_node}.outFloat", f"{squash_full_value_node}.floatA")

            volume_node = cmds.createNode("remapValue", name=f"{self.side}_spineVolume0{i}_RMV", ss=True)
            cmds.connectAttr(f"{spine_squash_factor_node}.outFloat", f"{volume_node}.inputValue")
            cmds.connectAttr(f"{spine_trn}.Min_Stretch_Length", f"{volume_node}.value[0].value_Position")
            cmds.connectAttr(f"{stretch_full_value_node}.outFloat", f"{volume_node}.value[0].value_FloatValue")
            cmds.setAttr(f"{volume_node}.value[1].value_Position", 1)
            cmds.setAttr(f"{volume_node}.value[1].value_FloatValue", 1)
            cmds.connectAttr(f"{spine_trn}.Max_Stretch_Length", f"{volume_node}.value[2].value_Position")
            cmds.connectAttr(f"{squash_full_value_node}.outFloat", f"{volume_node}.value[2].value_FloatValue")

            condition_node = cmds.createNode("condition", name=f"{self.side}_spineVolumeCondition0{i}_CND", ss=True)
            cmds.setAttr(f"{condition_node}.operation", 0)
            cmds.setAttr(f"{condition_node}.secondTerm", 1)
            float_constant_node = cmds.createNode("floatConstant", name=f"{self.side}_spineVolumeConditionInitialValue0{i}_FCT", ss=True)
            cmds.connectAttr(f"{self.body_ctl}.Volume_Preservation", f"{condition_node}.firstTerm")
            cmds.connectAttr(f"{float_constant_node}.outFloat", f"{condition_node}.colorIfFalseR")
            cmds.connectAttr(f"{volume_node}.outValue", f"{condition_node}.colorIfTrueR")

            cmds.connectAttr(f"{condition_node}.outColorR", f"{jnt}.scaleX")
            cmds.connectAttr(f"{condition_node}.outColorR", f"{jnt}.scaleZ")







        

        

