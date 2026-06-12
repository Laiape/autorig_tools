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

    def make(self, side, spine_skinning_jnts, spine_controllers):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').

        """
        self.spine_skinning_jnts = spine_skinning_jnts
        self.spine_controllers = spine_controllers
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.controller_creation()
        self.local_hip_chest_setup()
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

        # Matrices horneadas de las guías (estáticas) en lugar de transforms _GUIDE vivos
        self.body_guide_matrix = cmds.getAttr(f"{self.spine_chain[0]}.worldMatrix[0]")
        self.chest_guide_matrix = cmds.getAttr(f"{self.spine_chain[-1]}.worldMatrix[0]")

    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC"])
        cmds.setAttr(f"{self.body_nodes[0]}.offsetParentMatrix", self.body_guide_matrix, type="matrix")
        cmds.xform(self.body_nodes[0], m=om.MMatrix.kIdentity)
        cmds.parent(self.body_nodes[0], self.controllers_grp)

        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_localHip", offset=["GRP", "SPC"])
        cmds.setAttr(f"{self.local_hip_nodes[0]}.offsetParentMatrix", self.body_guide_matrix, type="matrix")
        cmds.xform(self.local_hip_nodes[0], m=om.MMatrix.kIdentity)
        cmds.parent(self.local_hip_nodes[0], self.controllers_grp)

        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC"])
        cmds.parent(self.local_chest_nodes[0], self.controllers_grp)

        self.lock_attributes(self.body_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_hip_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_chest_ctl, ["v"])

        self.spine_nodes = []
        self.spine_ctls = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            if i == 0 or i == len(self.spine_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP", "ANM"])
                self.lock_attributes(corner_ctl, [ "v"])
                
                if i == len(self.spine_chain) - 1:
                    cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 0:

                    cmds.connectAttr(f"{self.body_ctl}.worldMatrix[0]", f"{corner_nodes[0]}.offsetParentMatrix") # Parent the first spine ctl to body ctl
                    cmds.setAttr(f"{corner_nodes[0]}.inheritsTransform", 0) # Don't inherit the transform from body ctl
                    cmds.parent(corner_nodes[0], self.controllers_grp)
                    cmds.addAttr(corner_ctl, longName="tanControllers", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
                    cmds.setAttr(f"{corner_ctl}.tanControllers", lock=True, keyable=False, channelBox=True)
                    cmds.addAttr(corner_ctl, longName="tanVisibility", niceName="Tangent Controllers Visibility", attributeType="bool", defaultValue=True, keyable=True)
                    cmds.setAttr(f"{corner_ctl}.tanVisibility", lock=False, keyable=False, channelBox=True)

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

                tan_nodes, tan_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "Tan"), offset=["GRP", "ANM"])
                self.lock_attributes(tan_ctl, ["v"])

                cmds.matchTransform(tan_nodes[0], jnt, pos=True, rot=True, scl=False)
                cmds.connectAttr(f"{self.spine_ctls[0]}.tanVisibility", f"{tan_nodes[0]}.visibility")

                if i == 1:

                    cmds.parent(tan_nodes[0], self.spine_ctls[-1])


                self.spine_nodes.append(tan_nodes[0])
                self.spine_ctls.append(tan_ctl)

    def local_hip_chest_setup(self):

        # ------ Local hip setup ------
        cmds.select(clear=True)
        local_hip_skinning_jnt = cmds.joint(name=f"{self.side}_localHipSkinning_JNT")
        # rowFromMatrix + fourByFourMatrix, behaviour-preserving: rows 0-2 are the
        # hip ctl rotation rows NORMALIZED (drop the hip scale, like the rotation
        # decompose did) and rescaled with the spine ctl row lengths (= its
        # outputScale); row 3 is the spine ctl translation.
        four_by_four = cmds.createNode("fourByFourMatrix", name=f"{self.side}_localHip_FBF")
        row_translation = cmds.createNode("rowFromMatrix", name=f"{self.side}_localHipTranslation_RFM")
        cmds.setAttr(f"{row_translation}.input", 3)
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{row_translation}.matrix")
        for col_index, axis in enumerate("XYZ"):
            cmds.connectAttr(f"{row_translation}.output{axis}", f"{four_by_four}.in3{col_index}")

        for row_index in range(3):
            row_rotation = cmds.createNode("rowFromMatrix", name=f"{self.side}_localHipRotation0{row_index}_RFM")
            cmds.setAttr(f"{row_rotation}.input", row_index)
            cmds.connectAttr(f"{self.local_hip_ctl}.worldMatrix[0]", f"{row_rotation}.matrix")
            normalize_row = cmds.createNode("normalize", name=f"{self.side}_localHipRotation0{row_index}_NRM")

            row_scale = cmds.createNode("rowFromMatrix", name=f"{self.side}_localHipScale0{row_index}_RFM")
            cmds.setAttr(f"{row_scale}.input", row_index)
            cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{row_scale}.matrix")
            scale_length = cmds.createNode("length", name=f"{self.side}_localHipScale0{row_index}_LEN")

            for axis in "XYZ":
                cmds.connectAttr(f"{row_rotation}.output{axis}", f"{normalize_row}.input{axis}")
                cmds.connectAttr(f"{row_scale}.output{axis}", f"{scale_length}.input{axis}")

            for col_index, axis in enumerate("XYZ"):
                mult = cmds.createNode("multiply", name=f"{self.side}_localHipRow{row_index}{axis}_MUL")
                cmds.connectAttr(f"{normalize_row}.output{axis}", f"{mult}.input[0]")
                cmds.connectAttr(f"{scale_length}.output", f"{mult}.input[1]")
                cmds.connectAttr(f"{mult}.output", f"{four_by_four}.in{row_index}{col_index}")

        cmds.connectAttr(f"{four_by_four}.output", f"{local_hip_skinning_jnt}.offsetParentMatrix")
        
        cmds.setAttr(f"{self.local_hip_nodes[0]}.inheritsTransform", 0)
        cmds.parent(local_hip_skinning_jnt, self.skeleton_grp)

        # ----- Local chest setup ------
        blend_matrix_node = cmds.createNode("blendMatrix", name=f"{self.side}_localChest_BLM")
        cmds.connectAttr(f"{self.spine_chain[-1]}.worldMatrix[0]", f"{blend_matrix_node}.inputMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{blend_matrix_node}.target[0].targetMatrix")
        cmds.connectAttr(f"{blend_matrix_node}.outputMatrix", f"{self.local_chest_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{blend_matrix_node}.target[0].translateWeight", 0)
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.xform(self.local_chest_nodes[0], m=om.MMatrix.kIdentity)

        local_chest_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_localChestSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{self.local_chest_ctl}.worldMatrix[0]", f"{local_chest_skinning_jnt}.offsetParentMatrix")

        # Create a space switch in the last controller
        cmds.addAttr(self.spine_ctls[-1], longName="follow", niceName="Follow", attributeType="enum", enumName="Local:World", keyable=True, dv=0)
        last_spine_space_switch_parentMatrix = cmds.createNode("parentMatrix", name=f"{self.side}_lastSpineSpaceSwitch_PMX")
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_lastSpineSpaceSwitch_REV")
        cmds.setAttr(f"{last_spine_space_switch_parentMatrix}.inputMatrix", self.chest_guide_matrix, type="matrix")
        cmds.connectAttr(f"{self.spine_ctls[len(self.spine_ctls) // 2]}.worldMatrix[0]", f"{last_spine_space_switch_parentMatrix}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.follow", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{last_spine_space_switch_parentMatrix}.target[0].weight")
        cmds.connectAttr(f"{last_spine_space_switch_parentMatrix}.outputMatrix", f"{self.spine_nodes[-1]}.offsetParentMatrix")
        chest_offset = om.MMatrix(self.chest_guide_matrix) * om.MMatrix(cmds.getAttr(f"{self.spine_nodes[len(self.spine_ctls) // 2]}.worldMatrix[0]")).inverse()
        cmds.setAttr(f"{last_spine_space_switch_parentMatrix}.target[0].offsetMatrix", list(chest_offset), type="matrix")

        # En modo World (peso del target[0] = 0) el parentMatrix devolvía la matriz
        # de reposo estática y, con inheritsTransform=0, el chest ignoraba el
        # masterwalk (posición y escala global). El modo World ahora sigue al
        # masterwalk como segundo target.
        chest_masterwalk_offset = om.MMatrix(self.chest_guide_matrix) * om.MMatrix(cmds.getAttr(f"{self.masterwalk_ctl}.worldMatrix[0]")).inverse()
        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{last_spine_space_switch_parentMatrix}.target[1].targetMatrix")
        cmds.setAttr(f"{last_spine_space_switch_parentMatrix}.target[1].offsetMatrix", list(chest_masterwalk_offset), type="matrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.follow", f"{last_spine_space_switch_parentMatrix}.target[1].weight")
        cmds.setAttr(f"{self.spine_nodes[-1]}.inheritsTransform", 0)
        cmds.xform(self.spine_nodes[-1], m=om.MMatrix.kIdentity)

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
            
            row_from_matrix = cmds.createNode("rowFromMatrix", name=f"{self.side}_spine0{i}Translation_RFM")
            cmds.setAttr(f"{row_from_matrix}.input", 3) #Translate
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{row_from_matrix}.matrix")
            cmds.connectAttr(f"{row_from_matrix}.outputX", f"{ik_curve}.controlPoints[{i}].xValue")
            cmds.connectAttr(f"{row_from_matrix}.outputY", f"{ik_curve}.controlPoints[{i}].yValue")
            cmds.connectAttr(f"{row_from_matrix}.outputZ", f"{ik_curve}.controlPoints[{i}].zValue")

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
        cmds.addAttr(self.body_ctl, longName="spineStretch", niceName="Auto Stretch", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
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
        cmds.connectAttr(f"{self.body_ctl}.spineStretchMin", f"{stretch_factor_clamp}.minR")
        cmds.connectAttr(f"{self.body_ctl}.spineStretchMax", f"{stretch_factor_clamp}.maxR")

        cmds.connectAttr(f"{self.body_ctl}.spineStretch", f"{stretch_blend_node}.attributesBlender")
        cmds.connectAttr(f"{base_stretch_constant}.outFloat", f"{stretch_blend_node}.input[0]")
        cmds.connectAttr(f"{stretch_factor_clamp}.outputR", f"{stretch_blend_node}.input[1]")

        cmds.connectAttr(f"{stretch_blend_node}.output", f"{strecth_value_mult}.input[0]")
        cmds.setAttr(f"{strecth_value_mult}.input[1]", cmds.getAttr(f"{self.spine_chain[1]}.translateY"))

        cmds.connectAttr(f"{strecth_value_mult}.output", f"{stretch_value_negate}.input[0]")

        # El translateY de la cadena va en unidades locales pero la curva IK vive
        # en espacio world (con la escala del masterwalk): sin multiplicar por
        # globalScale la cadena solo cubre 1/escala de la curva y el volume
        # preservation se dispara. La cadena reversed usa la curva estática del
        # módulo (sin escala), así que conserva el valor sin escalar.
        stretch_value_scaled = cmds.createNode("multiply", name=f"{self.side}_spineStretchValueScaled_MUL")
        cmds.connectAttr(f"{strecth_value_mult}.output", f"{stretch_value_scaled}.input[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{stretch_value_scaled}.input[1]")

        for jnt in self.spine_chain[1:]:
            cmds.connectAttr(f"{stretch_value_scaled}.output", f"{jnt}.translateY")
        
        for jnt in reversed_spine_chain[1:]:
            cmds.connectAttr(f"{stretch_value_negate}.output", f"{jnt}.translateY")

        last_jnt_default_ty = cmds.getAttr(f"{self.spine_chain[-1]}.translateY")
        last_jnt_stretch_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineLastJntStretch_B2A")
        last_jnt_default_const = cmds.createNode("floatConstant", name=f"{self.side}_spineLastJntDefault_FLC")
        cmds.setAttr(f"{last_jnt_default_const}.inFloat", last_jnt_default_ty)

        cmds.connectAttr(f"{self.body_ctl}.spineStretch", f"{last_jnt_stretch_blend}.attributesBlender")
        cmds.connectAttr(f"{last_jnt_default_const}.outFloat", f"{last_jnt_stretch_blend}.input[0]")
        cmds.connectAttr(f"{strecth_value_mult}.output", f"{last_jnt_stretch_blend}.input[1]")

        # Mismo ajuste de globalScale para la última joint (su blend trabaja en
        # unidades locales de reposo)
        last_jnt_stretch_scaled = cmds.createNode("multiply", name=f"{self.side}_spineLastJntStretchScaled_MUL")
        cmds.connectAttr(f"{last_jnt_stretch_blend}.output", f"{last_jnt_stretch_scaled}.input[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{last_jnt_stretch_scaled}.input[1]")
        cmds.connectAttr(f"{last_jnt_stretch_scaled}.output", f"{self.spine_chain[-1]}.translateY", force=True) # Override the connection

        # ------ Offset setup ------
        nearest_point_node = cmds.createNode("nearestPointOnCurve", name=f"{self.side}_spineOffset_NPC")
        cmds.connectAttr(f"{ik_curve}.worldSpace[0]", f"{nearest_point_node}.inputCurve")
        cmds.connectAttr(f"{row_from_matrix}.outputX", f"{nearest_point_node}.inPositionX")
        cmds.connectAttr(f"{row_from_matrix}.outputY", f"{nearest_point_node}.inPositionY")
        cmds.connectAttr(f"{row_from_matrix}.outputZ", f"{nearest_point_node}.inPositionZ")
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
        cmds.addAttr(self.body_ctl, longName="volumePreservation", niceName="Auto Squash", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineFalloff", niceName="Falloff", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.body_ctl, longName="spineSquashMaxPos", niceName="Max Pos", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)

        # ----- Attatched FK attributes ------
        cmds.addAttr(self.body_ctl, longName="FK", niceName="SPINE VISIBILITY ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="bool", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.body_ctl, longName="IK_Vis", niceName="IK Controllers Visibility", attributeType="bool", min=0, max=1, defaultValue=1, keyable=True)
        cmds.addAttr(self.body_ctl, longName="Hip_Vis", niceName="Local Hip Visibility", attributeType="bool", min=0, max=1, defaultValue=1, keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK_Vis", lock=False, keyable=False, channelBox=True)
        cmds.setAttr(f"{self.body_ctl}.IK_Vis", lock=False, keyable=False, channelBox=True)
        cmds.setAttr(f"{self.body_ctl}.Hip_Vis", lock=False, keyable=False, channelBox=True)

        cmds.connectAttr(f"{self.body_ctl}.IK_Vis", f"{self.spine_nodes[0]}.visibility")
        cmds.connectAttr(f"{self.body_ctl}.Hip_Vis", f"{self.local_hip_nodes[0]}.visibility")

        # ------ Attatched FK setup ------
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i, jnt in enumerate(self.spine_chain):
            fk_name = f"{self.side}_spine{str(i+1).zfill(2)}AttatchedFk"
            fk_node, fk_ctl = curve_tool.create_controller(name=fk_name, offset=["GRP", "ANM"], locked_attrs=["sx", "sy", "sz", "v"])
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

        if (self.spine_skinning_jnts) > 1:
            step = (val_end - val_start) / (self.spine_skinning_jnts - 1)
            squash_values = [val_start + (i * step) for i in range(self.spine_skinning_jnts)]
        else:
            squash_values = [val_start]

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
        global_scale_cmx = cmds.createNode("fourByFourMatrix", name=f"{self.side}_spineSkinningGlobalScale_FBF", ss=True)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{global_scale_cmx}.in00")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{global_scale_cmx}.in11")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{global_scale_cmx}.in22")

        output_joints = []

        for i, ctl in enumerate(self.fk_controllers):

            jnt = cmds.createNode("joint", name=f"{ctl.replace('AttatchedFk_CTL', 'Skinning_JNT')}", ss=True, p=self.skeleton_grp)
            scale_mmx = cmds.createNode("multMatrix", name=f"{ctl.replace('AttatchedFk_CTL', 'SkinningScale_MMX')}", ss=True)
            cmds.connectAttr(f"{global_scale_cmx}.output", f"{scale_mmx}.matrixIn[0]")
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{scale_mmx}.matrixIn[1]")
            cmds.connectAttr(f"{scale_mmx}.matrixSum", f"{jnt}.offsetParentMatrix")
            output_joints.append(jnt)
        
        translations = []

        for joint in self.spine_chain:
            translation = cmds.xform(f"{joint}", query=True, worldSpace=True, translation=True)
            translations.append(translation)
        squash_curve = cmds.curve(p=translations, d=1, n="C_spineSquash_CRV")
        cmds.setAttr(squash_curve+".inheritsTransform", 0)
        cmds.parent(squash_curve, self.module_trn)
        

        for i, joint in enumerate(self.spine_chain):
            rfm = cmds.createNode("rowFromMatrix", n=f"C_{joint}Squash_RFM")
            cmds.setAttr(f"{rfm}.input", 3)  # translation row
            cmds.connectAttr(f"{joint}.worldMatrix[0]", f"{rfm}.matrix")
            for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
                cmds.connectAttr(f"{rfm}.output{axis}", f"{squash_curve}.controlPoints[{i}].{value}")

        nodes_to_create = {
            "C_spineSquash_CIN": ("curveInfo", None),
            "C_spineSquashBaseLength_MUL": ("multiply", None),
            "C_spineSquashFactor_DIV": ("divide", None),
        }

        created_nodes = []
        for node_name, (node_type, operation) in nodes_to_create.items():
            node = cmds.createNode(node_type, name=node_name)
            created_nodes.append(node)
            if operation is not None:   
                cmds.setAttr(f'{node}.operation', operation)

        cmds.connectAttr(f"{squash_curve}.worldSpace[0]", created_nodes[0]+".inputCurve")
        cmds.connectAttr(created_nodes[0] + ".arcLength", created_nodes[2]+".input1")
        cmds.connectAttr(created_nodes[1] + ".output", created_nodes[2]+".input2")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", created_nodes[1]+".input[0]")
        cmds.setAttr(created_nodes[1]+".input[1]", cmds.getAttr(created_nodes[0]+".arcLength"))

        self.squash_factor_div = created_nodes[2]

        nodes_to_create = {
            "C_spineVolumeLowBound_RMV": ("remapValue", None),# 0
            "C_spineVolumeHighBound_RMV": ("remapValue", None),# 1
            "C_spineVolumeLowBoundNegative_SUB": ("subtract", None),# 2
            "C_spineVolumeHighBoundNegative_SUB": ("subtract", None),# 3
            "C_spineVolumeSquashDelta_SUB": ("subtract", None), # 4
            "C_spineVolumeStretchDelta_SUB": ("subtract", None), # 5
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
            cmds.connectAttr(f"{main_created_nodes[i]}.outValue", f"{main_created_nodes[i+2]}.input2")

        cmds.setAttr(f"{main_created_nodes[2]}.input1", 0)
        cmds.setAttr(f"{main_created_nodes[3]}.input1", 2)
        cmds.setAttr(f"{main_created_nodes[4]}.input2", 1)
        cmds.setAttr(f"{main_created_nodes[5]}.input1", 1)
        cmds.connectAttr(f"{spine_settings_trn}.maxStretchEffect", f"{main_created_nodes[4]}.input1")
        cmds.connectAttr(f"{spine_settings_trn}.minStretchEffect", f"{main_created_nodes[5]}.input2")

        for i, joint in enumerate(output_joints):
            nodes_to_create = {
                f"C_spineVolumeSquashFactor0{i+1}_MUL": ("multiply", None), # 0
                f"C_spineVolumeStretchFactor0{i+1}_MUL": ("multiply", None), # 1
                f"C_spineVolumeStretchFullValue0{i+1}_SUB": ("subtract", None), # 2
                f"C_spineVolumeSquashFullValue0{i+1}_SUM": ("sum", None), # 3
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
            cmds.connectAttr(f"{main_created_nodes[2]}.output", f"{created_nodes[5]}.value[0].value_Position")
            cmds.connectAttr(f"{main_created_nodes[0]}.outValue", f"{created_nodes[5]}.value[1].value_Position")
            cmds.connectAttr(f"{main_created_nodes[1]}.outValue", f"{created_nodes[5]}.value[2].value_Position")
            cmds.connectAttr(f"{main_created_nodes[3]}.output", f"{created_nodes[5]}.value[3].value_Position")


            cmds.connectAttr(created_nodes[0] + ".output", created_nodes[3]+".input[0]")
            cmds.connectAttr(created_nodes[1] + ".output", created_nodes[2]+".input2")
            cmds.connectAttr(created_nodes[2] + ".output", created_nodes[4]+".value[2].value_FloatValue")
            cmds.connectAttr(created_nodes[3] + ".output", created_nodes[4]+".value[0].value_FloatValue")
            cmds.connectAttr(self.squash_factor_div + ".output", created_nodes[4]+".inputValue")
            cmds.setAttr(f"{created_nodes[3]}.input[1]", 1)
            cmds.setAttr(f"{created_nodes[2]}.input1", 1)

            cmds.connectAttr(f"{main_created_nodes[4]}.output", created_nodes[0]+".input[0]")
            cmds.connectAttr(f"{main_created_nodes[5]}.output", created_nodes[1]+".input[0]")
            cmds.connectAttr(f"{created_nodes[5]}.outValue", created_nodes[0]+".input[1]")
            cmds.connectAttr(f"{created_nodes[5]}.outValue", created_nodes[1]+".input[1]")

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
