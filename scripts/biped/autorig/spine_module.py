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

class SpineModule(object):

    def __init__(self):

        """
        Initialize the spineModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.controller_creation()
        self.local_hip_chest_setup()
        # self.stretch_activate()
        # self.ribbon_setup()
        self.ik_spine()

        data_manager.DataExportBiped().append_data("spine_module",
                            {
                                "local_hip_ctl": self.local_hip_ctl,
                                "body_ctl": self.body_ctl,
                                "local_chest_ctl": self.local_chest_ctl,
                                "last_spine_jnt": self.spine_chain[-1]
                            })
        

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:source_matrices
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

       

    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC"])
        cmds.matchTransform(self.body_nodes[0], self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.parent(self.body_nodes[0], self.controllers_grp)

        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_localHip", offset=["GRP", "SPC"])
        cmds.matchTransform(self.local_hip_nodes[0], self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.parent(self.local_hip_nodes[0], self.controllers_grp)

        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC"])
        cmds.parent(self.local_chest_nodes[0], self.controllers_grp)

        self.lock_attributes(self.body_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_hip_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_chest_ctl, ["sx", "sy", "sz", "v"])

        self.spine_nodes = []
        self.spine_ctls = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            if i == 0 or i == len(self.spine_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])
                self.lock_attributes(corner_ctl, [ "v"])
                
                if i == len(self.spine_chain) - 1:
                    cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 0:

                    cmds.connectAttr(f"{self.body_ctl}.worldMatrix[0]", f"{corner_nodes[0]}.offsetParentMatrix") # Parent the first spine ctl to body ctl
                    cmds.setAttr(f"{corner_nodes[0]}.inheritsTransform", 0) # Don't inherit the transform from body ctl
                    cmds.parent(corner_nodes[0], self.controllers_grp)

                else:

                    cmds.parent(self.spine_nodes[-1], corner_ctl)
                    cmds.parent(corner_nodes[0], self.spine_ctls[(len(self.spine_ctls) // 2)])

                self.spine_nodes.append(corner_nodes[0])
                self.spine_ctls.append(corner_ctl)

            if i == (len(self.spine_chain) - 1) // 2:

                mid_nodes, mid_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])
                self.lock_attributes(mid_ctl, [ "v"])

                cmds.parent(mid_nodes[0], self.spine_ctls[0])
                cmds.matchTransform(mid_nodes[0], self.spine_chain[(len(self.spine_chain) // 2) - 1], pos=True, rot=True, scl=False)
                self.spine_nodes.append(mid_nodes[0])
                self.spine_ctls.append(mid_ctl)

            
            if i == 1 or i == len(self.spine_chain) - 2:

                tan_nodes, tan_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "Tan"), offset=["GRP"])
                self.lock_attributes(tan_ctl, ["v"])

                cmds.matchTransform(tan_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 1:

                    cmds.parent(tan_nodes[0], self.spine_ctls[-1])

                self.spine_nodes.append(tan_nodes[0])
                self.spine_ctls.append(tan_ctl)

    def local_hip_chest_setup(self):

        # ------ Local hip setup ------
        cmds.select(clear=True)
        local_hip_skinning_jnt = cmds.joint(name=f"{self.side}_localHipSkinning_JNT")
        decompose_translation_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_localHipTranslation_DCM")
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{decompose_translation_node}.inputMatrix")
        decompose_rotation_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_localHipRotation_DCM")
        cmds.connectAttr(f"{self.local_hip_ctl}.worldMatrix[0]", f"{decompose_rotation_node}.inputMatrix")
        compose_matrix = cmds.createNode("composeMatrix", name=f"{self.side}_localHip_CMP")
        cmds.connectAttr(f"{decompose_translation_node}.outputTranslate", f"{compose_matrix}.inputTranslate")
        cmds.connectAttr(f"{decompose_translation_node}.outputScale", f"{compose_matrix}.inputScale")
        cmds.connectAttr(f"{decompose_rotation_node}.outputRotate", f"{compose_matrix}.inputRotate")
        cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{local_hip_skinning_jnt}.offsetParentMatrix")
        
        cmds.setAttr(f"{self.local_hip_nodes[0]}.inheritsTransform", 0)
        cmds.parent(local_hip_skinning_jnt, self.skeleton_grp)

        # ----- Local chest setup ------
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{self.local_chest_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.select(clear=True)
        local_chest_skinning_jnt = cmds.joint(name=f"{self.side}_localChestSkinning_JNT")
        cmds.setAttr(f"{local_chest_skinning_jnt}.inheritsTransform", 0)
        cmds.connectAttr(f"{self.local_chest_ctl}.worldMatrix[0]", f"{local_chest_skinning_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        
        cmds.parent(local_chest_skinning_jnt, self.skeleton_grp)

    def ribbon_setup(self):

        """
        Set up the ribbon for the spine module.
        """
        # Create the attribute for FK in the body controller
        cmds.addAttr(self.body_ctl, longName="FK", niceName="ATTACHED FK ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)


        # Create the FK controllers
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "FK"), offset=["GRP"])
            if i == 0:
                cmds.setAttr(f"{fk_node[0]}.inheritsTransform", 0)
                cmds.parent(fk_node[0], self.controllers_grp)
                cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_node[0]}.visibility")

            self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])
            self.fk_nodes.append(fk_node)
            self.fk_controllers.append(fk_ctl)

        sel = (self.spine_ctls[0], self.spine_ctls[1], self.spine_ctls[2], self.spine_ctls[3], self.spine_ctls[4])
        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_spineSkinning", aim_axis="y", up_axis="z", num_joints=len(self.spine_chain), skeleton_grp=self.skeleton_grp) # Do the ribbon setup, with the created controllers
        for t in temp:
            cmds.delete(t)
    
        jnt_connections = []
        for i, jnt in enumerate(output_joints): # Use the output joints from the ribbon setup to connect to the FK controllers

            jnt_connection = cmds.listConnections(jnt, source=True, destination=True, plugs=True)[0]

            if jnt_connection:
                
                mult_matrix_node = cmds.createNode("multMatrix", name=jnt.replace("_JNT", "_MMX"))
                cmds.connectAttr(jnt_connection, f"{mult_matrix_node}.matrixIn[0]")
                if i != 0:
                    inverse_matrix_node = cmds.createNode("inverseMatrix", name=jnt.replace("_JNT", "_INV"))
                    cmds.connectAttr(jnt_connections[-1], f"{inverse_matrix_node}.inputMatrix")
                    cmds.connectAttr(f"{inverse_matrix_node}.outputMatrix", f"{mult_matrix_node}.matrixIn[1]")
                    cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{self.fk_nodes[i][0]}.offsetParentMatrix")
                elif i == 0:
                    cmds.connectAttr(jnt_connection, f"{self.fk_nodes[i][0]}.offsetParentMatrix")
                
                cmds.connectAttr(f"{self.fk_controllers[i]}.worldMatrix[0]", f"{jnt}.offsetParentMatrix", force=True)
                jnt_connections.append(jnt_connection)

        # Clean up
        cmds.delete(self.spine_chain[0])

    def stretch_activate(self):

        """
        Stretch activate
        """
        # Create the guides for the aim and blend matrix nodes
        guide_00 = cmds.createNode("transform", name=f"{self.side}_spine00_Guide", ss=True, p=self.module_trn)
        guide_01 = cmds.createNode("transform", name=f"{self.side}_spine01_Guide", ss=True, p=self.module_trn)
        cmds.matchTransform(guide_00, self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.matchTransform(guide_01, self.spine_chain[-1], pos=True, rot=True, scl=False)

        aim_matrix_spine_00 = cmds.createNode("aimMatrix", name=f"{self.side}_spine00_AIM", ss=True)
        cmds.setAttr(f"{aim_matrix_spine_00}.primaryInputAxis", 0, 1, 0, type="double3")
        cmds.connectAttr(f"{guide_00}.worldMatrix[0]", f"{aim_matrix_spine_00}.inputMatrix")
        cmds.connectAttr(f"{guide_01}.worldMatrix[0]", f"{aim_matrix_spine_00}.primaryTargetMatrix") # Aim at the next guide

        blend_matrix_guide_04 = cmds.createNode("blendMatrix", name=f"{self.side}_spine04_BLM", ss=True)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].shearWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].translateWeight", 0)
        cmds.connectAttr(f"{guide_01}.worldMatrix[0]", f"{blend_matrix_guide_04}.inputMatrix") # First target is the guide itself
        cmds.connectAttr(f"{aim_matrix_spine_00}.outputMatrix", f"{blend_matrix_guide_04}.target[0].targetMatrix")

        blend_matrix_spine = cmds.createNode("blendMatrix", name=f"{self.side}_spine_BLM", ss=True)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].shearWeight", 0)
        cmds.connectAttr(f"{aim_matrix_spine_00}.outputMatrix", f"{blend_matrix_spine}.inputMatrix") # First target is the guide itself
        cmds.connectAttr(f"{guide_01}.worldMatrix[0]", f"{blend_matrix_spine}.target[0].targetMatrix")

        # Create the stretch attribute in the body controller
        cmds.addAttr(self.body_ctl, longName="STRETCH", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.STRETCH", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="Stretch", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        # Create the nodes to drive the stretch
        distance_node = cmds.createNode("distanceBetween", name=f"{self.side}_spineStretch_DTB")
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{distance_node}.inMatrix1")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{distance_node}.inMatrix2") # Distance between the first and last spine joint

        divide_node = cmds.createNode("divide", name=f"{self.side}_spineStretch_DIV")
        cmds.connectAttr(f"{distance_node}.distance", f"{divide_node}.input1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{divide_node}.input2")

        distance_matrix_node = cmds.createNode("distanceBetween", name=f"{self.side}_spineStretchMatrix_DTB")
        cmds.connectAttr(f"{aim_matrix_spine_00}.outputMatrix", f"{distance_matrix_node}.inMatrix1")
        cmds.connectAttr(f"{blend_matrix_guide_04}.outputMatrix", f"{distance_matrix_node}.inMatrix2") # Distance between the first aim matrix and the last blend matrix

        blend_two_attr_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineStretch_B2A")
        cmds.connectAttr(f"{self.body_ctl}.Stretch", f"{blend_two_attr_node}.attributesBlender")
        cmds.connectAttr(f"{divide_node}.output", f"{blend_two_attr_node}.input[0]")   
        cmds.connectAttr(f"{distance_matrix_node}.distance", f"{blend_two_attr_node}.input[1]") # Blend between no stretch and full stretch

        four_by_four_matrix_node = cmds.createNode("fourByFourMatrix", name=f"{self.side}_spineStretch_44M", ss=True)
        cmds.connectAttr(f"{blend_two_attr_node}.output", f"{four_by_four_matrix_node}.in31")

        blend_matrix_ctls = cmds.createNode("aimMatrix", name=f"{self.side}_spineStretch_AIM", ss=True)
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{blend_matrix_ctls}.inputMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{blend_matrix_ctls}.primaryTargetMatrix") # Second target is the stretch matrix
        cmds.setAttr(f"{blend_matrix_ctls}.primaryInputAxis", 0, 1, 0, type="double3")
        
        mult_matrix_stretch_node = cmds.createNode("multMatrix", name=f"{self.side}_spineStretch_MMX", ss=True)
        cmds.connectAttr(f"{blend_matrix_ctls}.outputMatrix", f"{mult_matrix_stretch_node}.matrixIn[0]")
        cmds.connectAttr(f"{four_by_four_matrix_node}.output", f"{mult_matrix_stretch_node}.matrixIn[1]") # Apply the stretch to the final blend matrix

        

        index = [1, 1- 1/len(self.spine_chain), 0.5, 1/len(self.spine_chain),  0]

        self.blend_matrices = []
        for i, ctl in enumerate(self.spine_ctls):
            
            blend_matrix_node = cmds.createNode("blendMatrix", name=ctl.replace("CTL", "BLM"), ss=True)
            cmds.setAttr(f"{blend_matrix_node}.target[0].weight", index[i])
            cmds.setAttr(f"{blend_matrix_node}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{blend_matrix_node}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{blend_matrix_node}.target[0].shearWeight", 0)
            cmds.connectAttr(f"{mult_matrix_stretch_node}.matrixSum", f"{blend_matrix_node}.inputMatrix", force=True)
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend_matrix_node}.target[0].targetMatrix", force=True) # Second target is the aim matrix
            self.blend_matrices.append(blend_matrix_node)

    

    def ik_spine(self):

        """
        IK spine setup
        """
        # ------ Create the IK main setup ------
        ik_curve = cmds.curve(name=f"{self.side}_spineIK_CRV", degree=3, point= [cmds.xform(ctl, q=True, ws=True, t=True) for ctl in self.spine_ctls])
        ik_curve_shape = cmds.listRelatives(ik_curve, shapes=True)[0]
        cmds.rename(ik_curve_shape, f"{self.side}_spineIK_CRVShape")
        ik_handle = cmds.ikHandle(name=f"{self.side}_spineIK_HDL", startJoint=self.spine_chain[0], endEffector=self.spine_chain[-1], solver="ikSplineSolver", curve=ik_curve, createCurve=False)[0]
        cmds.parent(ik_handle, self.module_trn)

        cmds.setAttr(f"{ik_handle}.dTwistControlEnable", 1)
        cmds.setAttr(f"{ik_handle}.dWorldUpType", 4) # Start/End Object Up
        cmds.setAttr(f"{ik_handle}.dForwardAxis", 2) # Y Axis positive
        cmds.setAttr(f"{ik_handle}.dWorldUpAxis", 6) # X Axis positive
        cmds.setAttr(f"{ik_handle}.dWorldUpVectorX", 1)
        cmds.setAttr(f"{ik_handle}.dWorldUpVectorY", 0)
        cmds.setAttr(f"{ik_handle}.dWorldUpVectorZ", 0)
        cmds.setAttr(f"{ik_handle}.dWorldUpVectorEndX", 1)
        cmds.setAttr(f"{ik_handle}.dWorldUpVectorEndY", 0)
        cmds.setAttr(f"{ik_handle}.dWorldUpVectorEndZ", 0)
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{ik_handle}.dWorldUpMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{ik_handle}.dWorldUpMatrixEnd")

        for i, ctl in enumerate(self.spine_ctls):
            
            decompose_matrix = cmds.createNode("decomposeMatrix", name=ctl.replace("_CTL", "_DCM"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{decompose_matrix}.inputMatrix")
            cmds.connectAttr(f"{decompose_matrix}.outputTranslate", f"{ik_curve}.controlPoints[{i}]")

        # ------ Create the IK reversed setup ------
        reversed_spine_chain = []
        for jnt in reversed(self.spine_chain):
            reversed_jnt = cmds.joint(name=jnt.replace("_JNT", "Reversed_JNT"))
            cmds.matchTransform(reversed_jnt, jnt, pos=True, rot=True, scl=False)
            reversed_spine_chain.append(reversed_jnt)
        cmds.parent(reversed_spine_chain[0], self.module_trn)

        ik_reversed_curve = cmds.curve(name=f"{self.side}_spineReversedIK_CRV", degree=3, point= [cmds.xform(ctl, q=True, ws=True, t=True) for ctl in reversed(self.spine_ctls)])
        ik_reversed_curve_shape = cmds.listRelatives(ik_reversed_curve, shapes=True)[0]
        cmds.rename(ik_reversed_curve_shape, f"{self.side}_spineReversedIK_CRVShape")
        ik_reversed_handle = cmds.ikHandle(name=f"{self.side}_spineReversedIK_HDL", startJoint=reversed_spine_chain[0], endEffector=reversed_spine_chain[-1], solver="ikSplineSolver", curve=ik_reversed_curve, createCurve=False)[0]
        cmds.parent(ik_reversed_handle, self.module_trn)

        # ------ Create stretch attributes ------
        cmds.addAttr(self.body_ctl, longName="spineStretchSep", niceName="STRETCH ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.spineStretchSep", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="spineStretch", niceName="Stretch", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineStretchMin", niceName="Stretch Min", attributeType="float", min=0, max=1, defaultValue=0.8, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineStretchMax", niceName="Stretch Max", attributeType="float", min=0, defaultValue=1.2, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineOffset", niceName="Offset", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        # ------ Create stretch setup ------
        ik_curve_info = cmds.createNode("curveInfo", name=f"{self.side}_spineIK_CIN")
        initial_length_multiply = cmds.createNode("multiply", name=f"{self.side}_spineIKInitialLength_MUL")
        initial_length_constant = cmds.createNode("floatConstant", name=f"{self.side}_spineIKInitialLength_FLC")
        strecht_factor_divide = cmds.createNode("divide", name=f"{self.side}_spineStretchFactor_DIV")
        stretch_factor_clamp = cmds.createNode("clamp", name=f"{self.side}_spineStretchFactor_CLP")
        base_stretch_constant = cmds.createNode("floatConstant", name=f"{self.side}_spineBaseStretch_FLC")
        cmds.setAttr(f"{base_stretch_constant}.inFloat", 1)
        stretch_blend_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineStretch_B2A")
        strecth_value_mult = cmds.createNode("multiply", name=f"{self.side}_spineStretchValue_MUL")
        stretch_value_negate = cmds.createNode("multiply", name=f"{self.side}_spineStretchValue_NEG")
        cmds.setAttr(f"{stretch_value_negate}.input[1]", -1)


        # Connect the nodes
        cmds.connectAttr(f"{ik_curve}.worldSpace[0]", f"{ik_curve_info}.inputCurve")
        cmds.setAttr(f"{initial_length_constant}.inFloat", cmds.getAttr(f"{ik_curve_info}.arcLength"))

        cmds.connectAttr(f"{initial_length_constant}.outFloat", f"{initial_length_multiply}.input[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{initial_length_multiply}.input[1]")

        cmds.connectAttr(f"{ik_curve_info}.arcLength", f"{strecht_factor_divide}.input1")
        cmds.connectAttr(f"{initial_length_multiply}.output", f"{strecht_factor_divide}.input2")

        cmds.connectAttr(f"{strecht_factor_divide}.output", f"{stretch_factor_clamp}.inputR")
        cmds.setAttr(f"{stretch_factor_clamp}.minR", cmds.getAttr(f"{self.body_ctl}.spineStretchMin"))
        cmds.setAttr(f"{stretch_factor_clamp}.maxR", cmds.getAttr(f"{self.body_ctl}.spineStretchMax"))

        cmds.connectAttr(f"{self.body_ctl}.spineStretch", f"{stretch_blend_node}.attributesBlender")
        cmds.connectAttr(f"{base_stretch_constant}.outFloat", f"{stretch_blend_node}.input[0]")
        cmds.connectAttr(f"{stretch_factor_clamp}.outputR", f"{stretch_blend_node}.input[1]")

        cmds.connectAttr(f"{stretch_blend_node}.output", f"{strecth_value_mult}.input[0]")
        cmds.setAttr(f"{strecth_value_mult}.input[1]", cmds.getAttr(f"{self.spine_chain[1]}.translateY"))

        cmds.connectAttr(f"{strecth_value_mult}.output", f"{stretch_value_negate}.input[0]")

        for jnt in self.spine_chain[1:]:
            cmds.connectAttr(f"{strecth_value_mult}.output", f"{jnt}.translateY")
        
        for jnt in reversed_spine_chain[1:]:
            cmds.connectAttr(f"{stretch_value_negate}.output", f"{jnt}.translateY")


        # ------ Offset setup ------
        nearest_point_node = cmds.createNode("nearestPointOnCurve", name=f"{self.side}_spineOffset_NPC")
        cmds.connectAttr(f"{ik_curve}.worldSpace[0]", f"{nearest_point_node}.inputCurve")
        cmds.connectAttr(f"{decompose_matrix}.outputTranslate", f"{nearest_point_node}.inPosition")
        attributes_blender = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineOffset_B2A")
        cmds.connectAttr(f"{self.body_ctl}.spineOffset", f"{attributes_blender}.attributesBlender")
        cmds.connectAttr(f"{nearest_point_node}.parameter", f"{attributes_blender}.input[1]")
        float_value_0 = cmds.createNode("floatConstant", name=f"{self.side}_spineOffset_FLC")
        cmds.setAttr(f"{float_value_0}.inFloat", 0)
        cmds.connectAttr(f"{float_value_0}.outFloat", f"{attributes_blender}.input[0]")
        cmds.connectAttr(f"{attributes_blender}.output", f"{ik_handle}.offset")

        # ------ Squash attributes ------
        cmds.addAttr(self.body_ctl, longName="spineSquashSep", niceName="SQUASH ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.spineSquashSep", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="volumePreservation", niceName="Squash", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineFalloff", niceName="Falloff", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineSquashMaxPos", niceName="Max Pos", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)

        # ----- Attatched FK attributes ------
        cmds.addAttr(self.body_ctl, longName="FK", niceName="ATTACHED FK ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        # ------ Attatched FK setup ------
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "AttatchedFk"), offset=["GRP", "ANM"], locked_attrs=["sx", "sy", "sz", "v"])
            if i == 0:
                cmds.setAttr(f"{fk_node[0]}.inheritsTransform", 0)
                cmds.parent(fk_node[0], self.controllers_grp)
                cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_node[0]}.visibility")
                cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{fk_node[0]}.offsetParentMatrix")
            else:
                mmx = cmds.createNode("multMatrix", name=f"{jnt.replace('_JNT', 'AttachedFK_MMX')}")
                cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
                cmds.connectAttr(f"{self.spine_chain[i-1]}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
                cmds.connectAttr(f"{mmx}.matrixSum", f"{fk_node[0]}.offsetParentMatrix")

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])
            cmds.xform(fk_node[0], m=om.MMatrix.kIdentity)
            self.fk_nodes.append(fk_node)
            self.fk_controllers.append(fk_ctl)
            

        # ------ Squash setup ------
        spine_settings_trn = cmds.createNode("transform", name=f"{self.side}_spineSettings_TRN", ss=True, p=self.module_trn)

        cmds.addAttr(spine_settings_trn, ln="maxStretchLength", sn="maxStrLen", at="double", dv=2.0, k=True)
        cmds.addAttr(spine_settings_trn, ln="minStretchLength", sn="minStrLen", at="double", dv=0.5, k=True)
        cmds.addAttr(spine_settings_trn, ln="minStretchEffect", sn="minStrEff", at="double", dv=2.0, k=True)
        cmds.addAttr(spine_settings_trn, ln="maxStretchEffect", sn="maxStrEff", at="double", dv=0.5, k=True)

        cmds.addAttr(spine_settings_trn, ln="volume", sn="vol", nn="__________", at="enum", en="Volume", k=True)
        cmds.setAttr(f"{spine_settings_trn}.volume", l=True) 
        
        val_start = 0.05
        val_end = 0.95

        if len(self.spine_chain) > 1:
            step = (val_end - val_start) / (len(self.spine_chain) - 1)
            squash_values = [val_start + (i * step) for i in range(len(self.spine_chain))]
        else:
            squash_values = [val_start] # Caso borde: solo un joint

        for i, val in enumerate(squash_values, 1):
            suffix = str(i).zfill(2)
            attr_name = f"spine{suffix}SquashPercentage"
            
            if not cmds.attributeQuery(attr_name, node=spine_settings_trn, exists=True):
                cmds.addAttr(spine_settings_trn, ln=attr_name, at="double", dv=val, k=True)
            else:
                cmds.setAttr(f"{spine_settings_trn}.{attr_name}", val)

        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v']:
            cmds.setAttr(f"{spine_settings_trn}.{attr}", k=False, l=True, cb=False)

        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v']:
            cmds.setAttr(f"{spine_settings_trn}.{attr}", k=False, l=True, cb=False)

        # ----- Output joints ------
        output_joints = []

        for i, ctl in enumerate(self.fk_controllers):
            
            jnt = cmds.createNode("joint", name=f"{ctl.replace('AttatchedFk_CTL', 'Skinning_JNT')}", ss=True, p=self.skeleton_grp)
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")
            output_joints.append(jnt)
        
        translations = []

        for joint in self.spine_chain:
            translation = cmds.xform(f"{joint}", query=True, worldSpace=True, translation=True)
            translations.append(translation)
        squash_curve = cmds.curve(p=translations, d=1, n="C_spineSquash_CRV")
        cmds.setAttr(squash_curve+".inheritsTransform", 0)
        cmds.parent(squash_curve, self.module_trn)
        

        for i, joint in enumerate(self.spine_chain):
            dcm = cmds.createNode("decomposeMatrix", n=f"C_{joint}Squash_DCM")
            cmds.connectAttr(f"{joint}.worldMatrix[0]", f"{dcm}.inputMatrix")
            cmds.connectAttr(f"{dcm}.outputTranslate", f"{squash_curve}.controlPoints[{i}]")

        nodes_to_create = {
            "C_spineSquash_CIN": ("curveInfo", None),
            "C_spineSquashBaseLength_FLM": ("floatMath", 2),
            "C_spineSquashFactor_FLM": ("floatMath", 3),
        }

        created_nodes = []
        for node_name, (node_type, operation) in nodes_to_create.items():
            node = cmds.createNode(node_type, name=node_name)
            created_nodes.append(node)
            if operation is not None:   
                cmds.setAttr(f'{node}.operation', operation)

        cmds.connectAttr(f"{squash_curve}.worldSpace[0]", created_nodes[0]+".inputCurve")
        cmds.connectAttr(created_nodes[0] + ".arcLength", created_nodes[2]+".floatA")
        cmds.connectAttr(created_nodes[1] + ".outFloat", created_nodes[2]+".floatB") 
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", created_nodes[1]+".floatA") 
        cmds.setAttr(created_nodes[1]+".floatB", cmds.getAttr(created_nodes[0]+".arcLength"))

        self.squash_factor_fml = created_nodes[2]

        nodes_to_create = {
            "C_spineVolumeLowBound_RMV": ("remapValue", None),# 0
            "C_spineVolumeHighBound_RMV": ("remapValue", None),# 1
            "C_spineVolumeLowBoundNegative_FLM": ("floatMath", 1),# 2
            "C_spineVolumeHighBoundNegative_FLM": ("floatMath", 1),# 3
            "C_spineVolumeSquashDelta_FLM": ("floatMath", 1), # 4
            "C_spineVolumeStretchDelta_FLM": ("floatMath", 1), # 5
        } 

        main_created_nodes = []
        for node_name, (node_type, operation) in nodes_to_create.items():
            node = cmds.createNode(node_type, name=node_name)
            main_created_nodes.append(node)
            if operation is not None:
                cmds.setAttr(f'{node}.operation', operation)
        values = [0.001, 0.999]
        for i in range(0,2):
            cmds.connectAttr(f"{self.body_ctl}.spineFalloff", f"{main_created_nodes[i]}.inputValue")
            cmds.connectAttr(f"{self.body_ctl}.spineSquashMaxPos", f"{main_created_nodes[i]}.outputMin")
            cmds.setAttr(f"{main_created_nodes[i]}.outputMax", values[i])
            cmds.connectAttr(f"{main_created_nodes[i]}.outValue", f"{main_created_nodes[i+2]}.floatB")

        cmds.setAttr(f"{main_created_nodes[2]}.floatA", 0)
        cmds.setAttr(f"{main_created_nodes[3]}.floatA", 2)
        cmds.setAttr(f"{main_created_nodes[4]}.floatB", 1)
        cmds.setAttr(f"{main_created_nodes[5]}.floatA", 1)
        cmds.connectAttr(f"{spine_settings_trn}.maxStretchEffect", f"{main_created_nodes[4]}.floatA")
        cmds.connectAttr(f"{spine_settings_trn}.minStretchEffect", f"{main_created_nodes[5]}.floatB")

        for i, joint in enumerate(output_joints):
            nodes_to_create = {
                f"C_spineVolumeSquashFactor0{i+1}_FLM": ("floatMath", 2), # 0
                f"C_spineVolumeStretchFactor0{i+1}_FLM": ("floatMath", 2), # 1
                f"C_spineVolumeStretchFullValue0{i+1}_FLM": ("floatMath", 1), # 2
                f"C_spineVolumeSquashFullValue0{i+1}_FLM": ("floatMath", 0), # 3
                f"C_spineVolume0{i+1}_RMV": ("remapValue", None), # 4
                f"C_spineVolumeFactor0{i+1}_RMV": ("remapValue", None), # 5
            }

            created_nodes = []
            for node_name, (node_type, operation) in nodes_to_create.items():
                node = cmds.createNode(node_type, name=node_name)
                created_nodes.append(node)
                if operation is not None:
                    cmds.setAttr(f'{node}.operation', operation)

            cmds.connectAttr(f"{spine_settings_trn}.spine0{i+1}SquashPercentage", f"{created_nodes[5]}.inputValue")
            cmds.connectAttr(f"{main_created_nodes[2]}.outFloat", f"{created_nodes[5]}.value[0].value_Position")
            cmds.connectAttr(f"{main_created_nodes[0]}.outValue", f"{created_nodes[5]}.value[1].value_Position")
            cmds.connectAttr(f"{main_created_nodes[1]}.outValue", f"{created_nodes[5]}.value[2].value_Position")
            cmds.connectAttr(f"{main_created_nodes[3]}.outFloat", f"{created_nodes[5]}.value[3].value_Position")


            cmds.connectAttr(created_nodes[0] + ".outFloat", created_nodes[3]+".floatA")
            cmds.connectAttr(created_nodes[1] + ".outFloat", created_nodes[2]+".floatB")
            cmds.connectAttr(created_nodes[2] + ".outFloat", created_nodes[4]+".value[2].value_FloatValue")
            cmds.connectAttr(created_nodes[3] + ".outFloat", created_nodes[4]+".value[0].value_FloatValue")
            cmds.connectAttr(self.squash_factor_fml + ".outFloat", created_nodes[4]+".inputValue")
            cmds.setAttr(f"{created_nodes[3]}.floatB", 1)
            cmds.setAttr(f"{created_nodes[2]}.floatA", 1)

            cmds.connectAttr(f"{main_created_nodes[4]}.outFloat", created_nodes[0]+".floatA")
            cmds.connectAttr(f"{main_created_nodes[5]}.outFloat", created_nodes[1]+".floatA")
            cmds.connectAttr(f"{created_nodes[5]}.outValue", created_nodes[0]+".floatB")
            cmds.connectAttr(f"{created_nodes[5]}.outValue", created_nodes[1]+".floatB")

            cmds.connectAttr(f"{spine_settings_trn}.maxStretchLength", f"{created_nodes[4]}.value[2].value_Position")
            cmds.connectAttr(f"{spine_settings_trn}.minStretchLength", f"{created_nodes[4]}.value[0].value_Position")   

            floatConstant = cmds.createNode("floatConstant", name=f"C_spineVolume0{i+1}_FLC", ss=True)
            blendTwoAttr = cmds.createNode("blendTwoAttr", name=f"C_spineVolume0{i+1}_BTA", ss=True)
            cmds.connectAttr(f"{created_nodes[4]}.outValue", f"{blendTwoAttr}.input[1]")
            cmds.connectAttr(f"{floatConstant}.outFloat", f"{blendTwoAttr}.input[0]")
            cmds.connectAttr(f"{self.body_ctl}.volumePreservation", f"{blendTwoAttr}.attributesBlender")

            cmds.connectAttr(f"{blendTwoAttr}.output",f"{joint}.scaleX")   
            cmds.connectAttr(f"{blendTwoAttr}.output",f"{joint}.scaleZ")   


            values = [-1, 1, 1, -1]
            for i in range(0,4):
                cmds.setAttr(f"{created_nodes[5]}.value[{i}].value_Interp", 2)
                cmds.setAttr(f"{created_nodes[5]}.value[{i}].value_FloatValue", values[i])
