import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from biped.utils import data_manager
from biped.utils import guides_manager
from biped.utils import curve_tool

from biped.autorig.utilities import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)

class JawModule(object):

    def __init__(self):

        """
        Initialize the jawModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    
    def make(self, side):

        """ 
        Create the jaw module structure and controllers. Call this method with the side ('L' or 'R') to create the respective jaw module.
        Args:
            side (str): The side of the jaw ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_jaw"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        cmds.addAttr(self.face_ctl, longName="Jaw", attributeType="long", defaultValue=1, max=2, min=0, keyable=True)
        cmds.addAttr(self.face_ctl, longName="Lips", attributeType="long", defaultValue=2, max=3, min=0, keyable=True)

        self.load_guides()
        self.create_controllers()
        self.collision_setup()
        self.create_lips_setup()

        cmds.parent(self.controllers_grp, self.face_ctl)

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
        Load the guide positions for the jaw module.
        Returns:
            dict: A dictionary containing the guide positions.
        """

        self.jaw_guides = guides_manager.get_guides("C_jaw_JNT") # Jaw father, l_jaw_JNT, r_jaw_JNT and c_chin_JNT

        for guide in self.jaw_guides:
            cmds.parent(guide, self.module_trn)
        
        self.jaw_jnt = self.jaw_guides[0]
    def create_controllers(self):
        
        """
        Create the controllers for the jaw module.  
        """

        self.jaw_guide = cmds.createNode("transform", name="C_jaw_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.jaw_guide, self.jaw_guides[0], pos=True) # Only position

        self.jaw_nodes, self.jaw_ctl = curve_tool.create_controller("C_jaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.jaw_guide}.worldMatrix[0]", f"{self.jaw_nodes[0]}.offsetParentMatrix")
        self.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])
        jaw_skinning_trn = cmds.createNode("transform", name="C_jawSkinning_TRN", ss=True, p=self.module_trn)
        mult_matrix_jaw = cmds.createNode("multMatrix", name="C_jawSkinning_MMX")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_jaw}.matrixSum", f"{jaw_skinning_trn}.offsetParentMatrix")
        jaw_skinning = cmds.createNode("joint", name="C_jawSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{jaw_skinning_trn}.worldMatrix[0]", f"{jaw_skinning}.offsetParentMatrix")

        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.jaw_guide}.worldMatrix[0]", f"{self.upper_jaw_nodes[0]}.offsetParentMatrix")
        self.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])
        upper_jaw_skinning_trn = cmds.createNode("transform", name="C_upperJawLocal_TRN", ss=True, p=self.module_trn)
        mult_matrix_upper_jaw = cmds.createNode("multMatrix", name="C_upperJawLocal_MMX")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_upper_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_upper_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.upper_jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_upper_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_upper_jaw}.matrixSum", f"{upper_jaw_skinning_trn}.offsetParentMatrix")
        upper_jaw_skinning = cmds.createNode("joint", name="C_upperJawSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{upper_jaw_skinning_trn}.worldMatrix[0]", f"{upper_jaw_skinning}.offsetParentMatrix")

        self.chin_nodes, self.chin_ctl = curve_tool.create_controller("C_chin", offset=["GRP"], parent=self.jaw_ctl)
        cmds.matchTransform(self.chin_nodes[0], self.chin_nodes[0].replace("C_chin_GRP", "C_chin_JNT"))
        self.lock_attributes(self.chin_ctl, ["v"])
        chin_skinning_grp = cmds.createNode("transform", name="C_chinLocal_GRP", ss=True, p=self.module_trn)
        chin_skinning_trn = cmds.createNode("transform", name="C_chinLocal_TRN", ss=True, p=chin_skinning_grp)
        mult_matrix_chin = cmds.createNode("multMatrix", name="C_chinLocal_MMX")
        cmds.connectAttr(f"{self.chin_ctl}.worldMatrix[0]", f"{mult_matrix_chin}.matrixIn[0]")
        cmds.connectAttr(f"{self.chin_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_chin}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.chin_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_chin}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_chin}.matrixSum", f"{chin_skinning_trn}.offsetParentMatrix")
        chin_skinning = cmds.createNode("joint", name="C_chinSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{chin_skinning_trn}.worldMatrix[0]", f"{chin_skinning}.offsetParentMatrix")

        self.jaw_child = [chin_skinning_trn]
        for side in ["L", "R"]:
            self.side_jaw_nodes, self.side_jaw_ctl = curve_tool.create_controller(f"{side}_jaw", offset=["GRP"], parent=self.jaw_ctl)
            cmds.matchTransform(self.side_jaw_nodes[0], self.side_jaw_nodes[0].replace(f"{side}_jaw_GRP", f"{side}_jaw_JNT"))
            self.lock_attributes(self.side_jaw_ctl, ["sx", "sy", "sz", "v"])
            side_jaw_skinning_grp = cmds.createNode("transform", name=f"{side}_jawLocal_GRP", ss=True, p=self.module_trn)
            side_jaw_skinning_trn = cmds.createNode("transform", name=f"{side}_jawLocal_TRN", ss=True, p=side_jaw_skinning_grp)
            cmds.matchTransform(side_jaw_skinning_grp, self.side_jaw_nodes[0])
            mult_matrix_side_jaw = cmds.createNode("multMatrix", name=f"{side}_jawLocal_MMX")
            cmds.connectAttr(f"{self.side_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_side_jaw}.matrixIn[0]") 
            cmds.connectAttr(f"{self.side_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_side_jaw}.matrixIn[1]")
            # cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{mult_matrix_side_jaw}.matrixIn[2]") # Add jaw 
            cmds.connectAttr(f"{mult_matrix_side_jaw}.matrixSum", f"{side_jaw_skinning_trn}.offsetParentMatrix")
            side_jaw_skinning = cmds.createNode("joint", name=f"{side}_jawSkinning_JNT", ss=True, p=self.skeleton_grp)
            cmds.connectAttr(f"{side_jaw_skinning_trn}.worldMatrix[0]", f"{side_jaw_skinning}.offsetParentMatrix")
            self.jaw_child.append(side_jaw_skinning_trn)


    def collision_setup(self):

        """
        Set up collision detection for the jaw module.
        """

        # Add attribute to the jaw controller
        cmds.addAttr(self.jaw_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
        cmds.setAttr(f"{self.jaw_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.jaw_ctl, longName="Auto_Collision", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)

        # Create nodes for collision detection
        sum_matrix_jaw = cmds.createNode("sum", name=f"{self.module_name}_collisionJaw_SMM")
        cmds.connectAttr(f"{self.jaw_ctl}.rotateX", f"{sum_matrix_jaw}.input[0]")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.rotateX", f"{sum_matrix_jaw}.input[1]")


        clamp_jaw = cmds.createNode("clamp", name=f"{self.module_name}_collisionJaw_CLP")
        cmds.setAttr(f"{clamp_jaw}.minR", -360)
        cmds.connectAttr(f"{sum_matrix_jaw}.output", f"{clamp_jaw}.inputR")

        float_constant_0 = cmds.createNode("floatConstant", name=f"{self.module_name}_collisionJaw_FC0")
        cmds.setAttr(f"{float_constant_0}.inFloat", 0)

        attribute_blender = cmds.createNode("blendTwoAttr", name=f"{self.module_name}_collisionJaw_BTA")
        cmds.connectAttr(f"{self.jaw_ctl}.Auto_Collision", f"{attribute_blender}.attributesBlender")
        cmds.connectAttr(f"{float_constant_0}.outFloat", f"{attribute_blender}.input[0]")
        cmds.connectAttr(f"{clamp_jaw}.outputR", f"{attribute_blender}.input[1]")
        self.compose_matrix_jaw = cmds.createNode("composeMatrix", name=f"{self.module_name}_collisionJaw_CMP")
        cmds.connectAttr(f"{attribute_blender}.output", f"{self.compose_matrix_jaw}.inputRotateX")
        cmds.connectAttr(f"{self.compose_matrix_jaw}.outputMatrix", f"{self.upper_jaw_ctl}.offsetParentMatrix")  # Connect the output of the blendTwoAttr to the rotateX of the upper jaw controller

        # Create set driven keyframes to improve jaw movement
        cmds.select(self.jaw_nodes[1])
        cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=0, v=0)
        cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=15, v=0)
        cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=35, v=0)
        cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=45, v=0)
        cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=60, v=0)
        cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=90, v=0)

        cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=0, v=0)
        cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=15, v=2)
        cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=30, v=1.75)
        cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=45, v=1.5)
        cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=60, v=1.25)
        cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=90, v=-3.5)

        cmds.setDrivenKeyframe(at="translateZ", cd=f"{self.jaw_ctl}.rotateX", dv=0, v=0)
        cmds.setDrivenKeyframe(at="translateZ", cd=f"{self.jaw_ctl}.rotateX", dv=45, v=2)
        cmds.setDrivenKeyframe(at="translateZ", cd=f"{self.jaw_ctl}.rotateX", dv=90, v=15)


    def create_lips_setup(self):

        """
        Create lip curves for the jaw module.
        """
             
        # Load guides
        self.upper_linear_lip_curve = guides_manager.get_guides("C_upperLipLinear_CRVShape", parent=self.module_trn)
        self.lower_linear_lip_curve = guides_manager.get_guides("C_lowerLipLinear_CRVShape", parent=self.module_trn)


        # Create NURBS surface
        self.sphere = guides_manager.get_guides("C_jaw_NURBShape", parent=self.module_trn) # NURBS surface guide
        cmds.hide(self.sphere)
        self.sphere_guide = cmds.createNode("transform", name="C_jawSlideGuide_GUIDE", ss=True, p=self.module_trn)

        # Jaw local joint
        cmds.delete(self.jaw_jnt)
        self.jaw_jnt = cmds.createNode("joint", name="C_jaw_JNT", ss=True, p=self.module_trn)
        mult_matrix_jaw_local = cmds.createNode("multMatrix", name="C_jawLocal_MMT")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_jaw_local}.matrixSum", f"{self.jaw_jnt}.offsetParentMatrix")

        # for child in self.jaw_child:
        #     cmds.parent(child, self.jaw_jnt)

        # Upper jaw local joint
        self.upper_jaw_jnt = cmds.createNode("joint", name="C_upperJaw_JNT", ss=True, p=self.module_trn)
        mult_matrix_upper_jaw_local = cmds.createNode("multMatrix", name="C_upperJawLocal_MMT")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_upper_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_upper_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.upper_jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_upper_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_upper_jaw_local}.matrixSum", f"{self.upper_jaw_jnt}.offsetParentMatrix")


        # Create constraints to upper and lower jaws
        jaw_nurbs_skin_cluster = cmds.skinCluster(
                self.sphere,
                self.jaw_jnt,
                self.upper_jaw_jnt,
                toSelectedBones=True,
                bindMethod=0,
                normalizeWeights=1,
                weightDistribution=0,
                maximumInfluences=2,
                dropoffRate=4,
                removeUnusedInfluence=False,
                name="C_jawSlideNRB_SKIN"
            )[0]
        
        u_spans = cmds.getAttr(f"{self.sphere}.spansU")
        v_spans = cmds.getAttr(f"{self.sphere}.spansV")
        degU = cmds.getAttr(f"{self.sphere}.degreeU")
        degV = cmds.getAttr(f"{self.sphere}.degreeV")

        u_count = u_spans + degU
        v_count = v_spans + degV
        half = int(u_count) // 2

        for u in range(u_count):
            for v in range(v_count):
                
                if u > half:
                    upper_w = 1.0
                    jaw_w = 0.0
                elif u == half:
                    jaw_w = 0.5
                    upper_w = 0.5
                else:
                    jaw_w = 1.0
                    upper_w = 0.0

                cv = f"{self.sphere}.cv[{u}][{v}]"
                
                cmds.skinPercent(jaw_nurbs_skin_cluster, cv, transformValue=[
                    (self.jaw_jnt, jaw_w),
                    (self.upper_jaw_jnt, upper_w)
                ])
        
        # Create main lip controllers
        lips_controllers_grp = cmds.createNode("transform", name="C_lipsControllers_GRP", ss=True, p=self.controllers_grp)
        main_lips_controllers = cmds.createNode("transform", name="C_primaryLipsControllers_GRP", ss=True, p=lips_controllers_grp)
        # Create upper controller
        upper_lip_nodes, upper_lip_ctl = curve_tool.create_controller("C_upperLip", offset=["GRP", "OFF"], parent=main_lips_controllers)
        self.lock_attributes(upper_lip_ctl, ["v"])
        mtp_upper_lip = cmds.createNode("motionPath", name="C_upperLip_MTP", ss=True) 
        cmds.connectAttr(f"{self.upper_linear_lip_curve}.worldSpace[0]", f"{mtp_upper_lip}.geometryPath")
        cmds.setAttr(f"{mtp_upper_lip}.uValue", 0.5)
        cmds.setAttr(f"{mtp_upper_lip}.fractionMode", 1)
        fbf_upper_lip = cmds.createNode("fourByFourMatrix", name="C_upperLip_FBF", ss=True)
        cmds.connectAttr(f"{mtp_upper_lip}.allCoordinates.xCoordinate", f"{fbf_upper_lip}.in30")
        cmds.connectAttr(f"{mtp_upper_lip}.allCoordinates.yCoordinate", f"{fbf_upper_lip}.in31")
        cmds.connectAttr(f"{mtp_upper_lip}.allCoordinates.zCoordinate", f"{fbf_upper_lip}.in32")
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{upper_lip_nodes[0]}.offsetParentMatrix")
        upper_local_jnt = cmds.createNode("joint", name="C_upperLip_JNT", ss=True, p=self.module_trn)
        mmx_upper_local = cmds.createNode("multMatrix", name="C_upperLipLocal_MMT")
        cmds.connectAttr(f"{upper_lip_ctl}.worldMatrix[0]", f"{mmx_upper_local}.matrixIn[0]")
        cmds.connectAttr(f"{upper_lip_nodes[0]}.worldInverseMatrix[0]", f"{mmx_upper_local}.matrixIn[1]")
        grp_wm = cmds.getAttr(f"{upper_lip_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mmx_upper_local}.matrixIn[2]", grp_wm, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mmx_upper_local}.matrixSum", f"{upper_local_jnt}.offsetParentMatrix")
        upper_lip_parent_wm = cmds.createNode("parentMatrix", name="C_upperLip_PMX", ss=True)
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{upper_lip_parent_wm}.inputMatrix")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{upper_lip_parent_wm}.target[0].targetMatrix")
        cmds.setAttr(f"{upper_lip_parent_wm}.target[0].offsetMatrix", self.get_offset_matrix(upper_lip_nodes[0], self.upper_jaw_ctl), type="matrix")
        mult_matrix_offset_upper = cmds.createNode("multMatrix", name="C_upperLipOffset_MMT", ss=True)
        cmds.connectAttr(f"{upper_lip_parent_wm}.outputMatrix", f"{mult_matrix_offset_upper}.matrixIn[0]")
        cmds.connectAttr(f"{upper_lip_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_offset_upper}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix_offset_upper}.matrixSum", f"{upper_lip_nodes[1]}.offsetParentMatrix")

        # Create lower controller
        lower_lip_nodes, lower_lip_ctl = curve_tool.create_controller("C_lowerLip", offset=["GRP", "OFF"], parent=main_lips_controllers)
        self.lock_attributes(lower_lip_ctl, ["v"])
        mtp_lower_lip = cmds.createNode("motionPath", name="C_lowerLip_MTP", ss=True) 
        cmds.connectAttr(f"{self.lower_linear_lip_curve}.worldSpace[0]", f"{mtp_lower_lip}.geometryPath")
        cmds.setAttr(f"{mtp_lower_lip}.uValue", 0.5)      
        cmds.setAttr(f"{mtp_lower_lip}.fractionMode", 1)
        fbf_lower_lip = cmds.createNode("fourByFourMatrix", name="C_lowerLip_FBF", ss=True)
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.xCoordinate", f"{fbf_lower_lip}.in30")
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.yCoordinate", f"{fbf_lower_lip}.in31")
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.zCoordinate", f"{fbf_lower_lip}.in32")
        cmds.connectAttr(f"{fbf_lower_lip}.output", f"{lower_lip_nodes[0]}.offsetParentMatrix")
        lower_local_jnt = cmds.createNode("joint", name="C_lowerLip_JNT", ss=True, p=self.module_trn)
        mmx_lower_local = cmds.createNode("multMatrix", name="C_lowerLipLocal_MMT")
        cmds.connectAttr(f"{lower_lip_ctl}.worldMatrix[0]", f"{mmx_lower_local}.matrixIn[0]")
        cmds.connectAttr(f"{lower_lip_nodes[0]}.worldInverseMatrix[0]", f"{mmx_lower_local}.matrixIn[1]")
        grp_wm = cmds.getAttr(f"{lower_lip_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mmx_lower_local}.matrixIn[2]", grp_wm, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mmx_lower_local}.matrixSum", f"{lower_local_jnt}.offsetParentMatrix")
        lower_lip_parent_wm = cmds.createNode("parentMatrix", name="C_lowerLip_PMX", ss=True)
        cmds.connectAttr(f"{fbf_lower_lip}.output", f"{lower_lip_parent_wm}.inputMatrix")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{lower_lip_parent_wm}.target[0].targetMatrix")
        cmds.setAttr(f"{lower_lip_parent_wm}.target[0].offsetMatrix", self.get_offset_matrix(lower_lip_nodes[0], self.jaw_ctl), type="matrix")
        mult_matrix_offset_lower = cmds.createNode("multMatrix", name="C_lowerLipOffset_MMT", ss=True)
        cmds.connectAttr(f"{lower_lip_parent_wm}.outputMatrix", f"{mult_matrix_offset_lower}.matrixIn[0]")
        cmds.connectAttr(f"{lower_lip_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_offset_lower}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix_offset_lower}.matrixSum", f"{lower_lip_nodes[1]}.offsetParentMatrix")

        upper_local_jnts = []
        lower_local_jnts = []

        corner_nodes_ctls = []

        # Create corner controllers
        for side in ["L", "R"]:
            
            # Create corner controller and place them

            corner_nodes, corner_ctl = curve_tool.create_controller(f"{side}_lipCorner", offset=["GRP", "OFF"], parent=main_lips_controllers)
            self.lock_attributes(corner_ctl, ["sx", "sz", "v"])
            mtp_corner_lip = cmds.createNode("motionPath", name=f"{side}_lipCorner_MTP", ss=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.worldSpace[0]", f"{mtp_corner_lip}.geometryPath")
            corner_nodes_ctls.append(corner_nodes[0])

            if side == "L":
                cmds.setAttr(f"{mtp_corner_lip}.uValue", 1)

            else:

                cmds.setAttr(f"{mtp_corner_lip}.uValue", 0)

            cmds.setAttr(f"{mtp_corner_lip}.fractionMode", 1)
            fbf_corner_lip = cmds.createNode("fourByFourMatrix", name=f"{side}_lipCorner_FBF", ss=True)
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.xCoordinate", f"{fbf_corner_lip}.in30")
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.yCoordinate", f"{fbf_corner_lip}.in31")
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.zCoordinate", f"{fbf_corner_lip}.in32")
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{corner_nodes[0]}.offsetParentMatrix")

            if side == "R":

                cmds.setAttr(f"{fbf_corner_lip}.in00", -1)  # Invert X axis for right corner

            # Create blending between upper and lower lips
            cmds.addAttr(corner_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
            cmds.setAttr(f"{corner_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
            cmds.addAttr(corner_ctl, longName="Jaw_Blend", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)
            cmds.addAttr(corner_ctl, longName="Zip", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

            parent_matrix_blender = cmds.createNode("parentMatrix", name=f"{side}_lipCorner_PMX", ss=True)
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{parent_matrix_blender}.inputMatrix")
            cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{parent_matrix_blender}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{parent_matrix_blender}.target[1].targetMatrix")
            reverse_blender = cmds.createNode("reverse", name=f"{side}_lipCorner_REV", ss=True)
            cmds.connectAttr(f"{corner_ctl}.Jaw_Blend", f"{reverse_blender}.inputX")
            cmds.connectAttr(f"{reverse_blender}.outputX", f"{parent_matrix_blender}.target[0].weight")
            cmds.connectAttr(f"{corner_ctl}.Jaw_Blend", f"{parent_matrix_blender}.target[1].weight")
            mult_matrix_corner_offset = cmds.createNode("multMatrix", name=f"{side}_lipCornerOffset_MMT", ss=True)
            cmds.connectAttr(f"{parent_matrix_blender}.outputMatrix", f"{mult_matrix_corner_offset}.matrixIn[0]")
            cmds.connectAttr(f"{corner_nodes[0]}.parentInverseMatrix[0]", f"{mult_matrix_corner_offset}.matrixIn[1]")
            cmds.connectAttr(f"{mult_matrix_corner_offset}.matrixSum", f"{corner_nodes[1]}.offsetParentMatrix")
            cmds.setAttr(f"{parent_matrix_blender}.target[0].offsetMatrix", self.get_offset_matrix(corner_nodes[0], self.jaw_ctl), type="matrix")
            cmds.setAttr(f"{parent_matrix_blender}.target[1].offsetMatrix", self.get_offset_matrix(corner_nodes[0], self.upper_jaw_ctl), type="matrix")

            # Corner local
            row_matrix_corner_local = cmds.createNode("rowFromMatrix", name=f"{side}_lipCornerLocal_RMF")
            cmds.setAttr(f"{row_matrix_corner_local}.input", 3)
            mult_matrix_corner_local = cmds.createNode("multMatrix", name=f"{side}_lipCornerLocal_MMT")
            cmds.connectAttr(f"{corner_ctl}.worldMatrix[0]", f"{mult_matrix_corner_local}.matrixIn[0]")
            cmds.connectAttr(f"{corner_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_corner_local}.matrixIn[1]")
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{mult_matrix_corner_local}.matrixIn[2]")
            cmds.connectAttr(f"{mult_matrix_corner_local}.matrixSum", f"{row_matrix_corner_local}.matrix")
            closest_point_corner = cmds.createNode("closestPointOnSurface", name=f"{side}_lipCorner_CPOS", ss=True)
            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{closest_point_corner}.inputSurface")
            cmds.connectAttr(f"{row_matrix_corner_local}.outputX", f"{closest_point_corner}.inPositionX")
            cmds.connectAttr(f"{row_matrix_corner_local}.outputY", f"{closest_point_corner}.inPositionY")
            cmds.connectAttr(f"{row_matrix_corner_local}.outputZ", f"{closest_point_corner}.inPositionZ")
            corner_local_jnt = cmds.createNode("joint", name=f"{side}_lipCorner_JNT", ss=True, p=self.module_trn)
            cmds.connectAttr(f"{closest_point_corner}.position", f"{corner_local_jnt}.translate")
            upper_local_jnts.append(corner_local_jnt)
            lower_local_jnts.append(corner_local_jnt)
            if side == "L":
                upper_local_jnts.append(upper_local_jnt)
                lower_local_jnts.append(lower_local_jnt)
            
            # Aim constraint to keep corner oriented correctly
            aim = cmds.aimConstraint(
                upper_lip_ctl,
                corner_nodes[0],
                aimVector=(-1, 0, 0),
                upVector=(0, 1, 0),
                worldUpType="scene",
                name=f"{side}_lipCorner_AIM"
            )[0]
            cmds.delete(aim)


        # Rebuild curves for better deformation
        self.upper_rebuild_lip_curve = cmds.rebuildCurve(self.upper_linear_lip_curve, ch=0, rpo=0, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=4, d=3, tol=0.01, name="C_upperLip_CRV")[0]
        self.lower_rebuild_lip_curve = cmds.rebuildCurve(self.lower_linear_lip_curve, ch=0, rpo=0, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=4, d=3, tol=0.01, name="C_lowerLip_CRV")[0]
        cmds.parent(self.upper_rebuild_lip_curve, self.lower_rebuild_lip_curve, self.module_trn)

        # Skin cluster to local joints
        self.upper_skin_cluster = cmds.skinCluster(upper_local_jnts, self.upper_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_upperLip_SKIN")[0]
        self.lower_skin_cluster = cmds.skinCluster(lower_local_jnts, self.lower_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_lowerLip_SKIN")[0]

        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[0]", transformValue=[upper_local_jnts[2], 1.0])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[1]", transformValue=[(upper_local_jnts[2], 0.5), (upper_local_jnts[1], 0.5)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[2]", transformValue=[(upper_local_jnts[2], 0.2), (upper_local_jnts[1], 0.8)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[3]", transformValue=[upper_local_jnts[1], 1.0])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[4]", transformValue=[(upper_local_jnts[1], 0.8), (upper_local_jnts[0], 0.2)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[5]", transformValue=[(upper_local_jnts[1], 0.5), (upper_local_jnts[0], 0.5)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[6]", transformValue=[upper_local_jnts[0], 1.0])

        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[0]", transformValue=[lower_local_jnts[2], 1.0])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[1]", transformValue=[(lower_local_jnts[2], 0.5), (lower_local_jnts[1], 0.5)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[2]", transformValue=[(lower_local_jnts[2], 0.2), (lower_local_jnts[1], 0.8)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[3]", transformValue=[lower_local_jnts[1], 1.0])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[4]", transformValue=[(lower_local_jnts[1], 0.8), (lower_local_jnts[0], 0.2)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[5]", transformValue=[(lower_local_jnts[1], 0.5), (lower_local_jnts[0], 0.5)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[6]", transformValue=[lower_local_jnts[0], 1.0])
        # Make rebuilded bezier
        upper_bezier_curve = cmds.duplicate(self.upper_rebuild_lip_curve, name=self.upper_rebuild_lip_curve.replace("_CRV", "Bezier_CRV"), renameChildren=True)[0]
        cmds.select(upper_bezier_curve, r=True)
        cmds.nurbsCurveToBezier()
        cmds.select(clear=True)

        lower_bezier_curve = cmds.duplicate(self.lower_rebuild_lip_curve, name=self.lower_rebuild_lip_curve.replace("_CRV", "Bezier_CRV"), renameChildren=True)[0]
        cmds.select(lower_bezier_curve, r=True)
        cmds.nurbsCurveToBezier()
        cmds.select(clear=True)

        # Cvs controllers for lips
        rebuilded_upper_lip_cvs = cmds.ls(f"{upper_bezier_curve}.cv[*]", fl=True)
        rebuilded_lower_lip_cvs = cmds.ls(f"{lower_bezier_curve}.cv[*]", fl=True)

        cvs_ctls_upper = []
        cv_nodes_upper = []
        path_joints_upper = []
        mult_matrix_tangents_upper = []
        tangent_mult_matrices_upper = []

        secondary_controllers_nodes = cmds.createNode("transform", name="C_secondaryLipsControllers_GRP", ss=True, p=lips_controllers_grp)

        dict_parents = {

            0: [1],
            3: [2, 4],
            6: [5, 7],
            9: [8, 10],
            12: [11]
        }

        for i, cv in enumerate(rebuilded_upper_lip_cvs):
            # Set the name based on the index
            if i % 3 == 0:
                name = f"upperLip0{i}"
            else:
                name = f"upperLip0{i}Tan"

            # Determine the side based on the index
            if i < (len(rebuilded_upper_lip_cvs) - 1) / 2:
                side = "R"
            elif i == (len(rebuilded_upper_lip_cvs) -1) / 2 :
                side = "C"
            else:
                side = "L"
            

            # Create controller for the CV
            cv_ctl_nodes, cv_ctl = curve_tool.create_controller(f"{side}_{name}", offset=["GRP", "OFF"], parent=self.controllers_grp)
            self.lock_attributes(cv_ctl, ["sy", "sz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
            
            mtp_cv = cmds.createNode("motionPath", name=f"{side}_{name}_MTP", ss=True)
            cmds.connectAttr(f"{self.upper_rebuild_lip_curve}.worldSpace[0]", f"{mtp_cv}.geometryPath")
            paramU = self.getClosestParamToPosition(self.upper_rebuild_lip_curve, cmds.xform(cv, q=True, ws=True, t=True))
            cmds.setAttr(f"{mtp_cv}.uValue", paramU)
            fbf_cv = cmds.createNode("fourByFourMatrix", name=f"{side}_{name}_FBF", ss=True)
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.xCoordinate", f"{fbf_cv}.in30")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.yCoordinate", f"{fbf_cv}.in31")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.zCoordinate", f"{fbf_cv}.in32")

            cvs_ctls_upper.append(cv_ctl)
            cv_nodes_upper.append(cv_ctl_nodes[0])
            

            local_jnt_cv = cmds.createNode("joint", name=f"{side}_{name}_JNT", ss=True, p=self.module_trn)
            mult_matrix_secondary = cmds.createNode("multMatrix", name=f"{side}_{name}_MMS", ss=True)
            cmds.connectAttr(f"{cv_ctl}.matrix", f"{mult_matrix_secondary}.matrixIn[0]")
            cmds.connectAttr(f"{fbf_cv}.output", f"{mult_matrix_secondary}.matrixIn[1]")
            # ---- Must connect to tangents his parent matrix ----
            tangent_mult_matrices_upper.append(mult_matrix_secondary)
            cmds.connectAttr(f"{mult_matrix_secondary}.matrixSum", f"{local_jnt_cv}.offsetParentMatrix")
            path_joints_upper.append(local_jnt_cv)

            if side == "R" and i != 5:

                cmds.setAttr(f"{fbf_cv}.in00", -1)  # Invert X axis for right side
                
            if i % 3 == 0:
                
                cmds.addAttr(cv_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
                cmds.setAttr(f"{cv_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(cv_ctl, ln="Tan_Controllers_Visibility", at="bool", k=True)
                cmds.setAttr(f"{cv_ctl}.Tan_Controllers_Visibility", k=False, cb=True)
                cmds.connectAttr(f"{fbf_cv}.output", f"{cv_ctl_nodes[0]}.offsetParentMatrix")
                mult_matrix_tangent = None
                
            
            else:
                mult_matrix_tangent = cmds.createNode("multMatrix", name=f"{side}_{name}_MMT", ss=True)
                cmds.connectAttr(f"{fbf_cv}.output", f"{mult_matrix_tangent}.matrixIn[1]")
                cmds.connectAttr(f"{mult_matrix_tangent}.matrixSum", f"{cv_ctl_nodes[0]}.offsetParentMatrix", f=True)

            mult_matrix_tangents_upper.append(mult_matrix_tangent)
            cmds.parent(cv_ctl_nodes[0], secondary_controllers_nodes)
            if i == 0 or i == len(rebuilded_upper_lip_cvs) -1:
                aim = cmds.aimConstraint(
                    upper_lip_ctl,
                    cv_ctl_nodes[0],
                    aimVector=(-1, 0, 0),
                    upVector=(0, 1, 0),
                    worldUpType="scene",
                    name=f"{side}_lipCorner_AIM"
                )[0]
                cmds.delete(aim)

        for index, tangent in dict_parents.items():
            for child_index in tangent:
                cmds.connectAttr(f"{cvs_ctls_upper[index]}.Tan_Controllers_Visibility", f"{cv_nodes_upper[child_index]}.visibility")
                if mult_matrix_tangents_upper[child_index] == None:
                    continue
                else:
                    cmds.connectAttr(f"{cvs_ctls_upper[index]}.matrix", f"{mult_matrix_tangents_upper[child_index]}.matrixIn[0]")
                    cmds.connectAttr(f"{cvs_ctls_upper[index]}.matrix", f"{tangent_mult_matrices_upper[child_index]}.matrixIn[2]") # Added to keep tangent joints aligned

        cvs_ctls_lower = []
        cv_nodes_lower = []
        path_joints_lower = []
        mult_matrix_tangents_lower = []
        tangent_mult_matrices_lower = []

        for i, cv in enumerate(rebuilded_lower_lip_cvs):
            # Set the name based on the index
            if i % 3 == 0:
                name = f"lowerLip0{i}"
            else:
                name = f"lowerLip0{i}Tan"

            # Determine the side based on the index
            if i < (len(rebuilded_lower_lip_cvs) -1) / 2 :
                side = "R"
            elif i == (len(rebuilded_lower_lip_cvs) -1) / 2 :
                side = "C"
            else:
                side = "L"
            

            # Create controller for the CV
            cv_ctl_nodes, cv_ctl = curve_tool.create_controller(f"{side}_{name}", offset=["GRP", "OFF"], parent=self.controllers_grp)
            self.lock_attributes(cv_ctl, ["sy", "sz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
            
            mtp_cv = cmds.createNode("motionPath", name=f"{side}_{name}_MTP", ss=True)
            cmds.connectAttr(f"{self.lower_rebuild_lip_curve}.worldSpace[0]", f"{mtp_cv}.geometryPath")
            paramU = self.getClosestParamToPosition(self.lower_rebuild_lip_curve, cmds.xform(cv, q=True, ws=True, t=True))
            cmds.setAttr(f"{mtp_cv}.uValue", paramU)
            fbf_cv = cmds.createNode("fourByFourMatrix", name=f"{side}_{name}_FBF", ss=True)
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.xCoordinate", f"{fbf_cv}.in30")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.yCoordinate", f"{fbf_cv}.in31")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.zCoordinate", f"{fbf_cv}.in32")

            cvs_ctls_lower.append(cv_ctl)
            cv_nodes_lower.append(cv_ctl_nodes[0])
            

            local_jnt_cv = cmds.createNode("joint", name=f"{side}_{name}_JNT", ss=True, p=self.module_trn)
            mult_matrix_secondary = cmds.createNode("multMatrix", name=f"{side}_{name}_MMS", ss=True)
            cmds.connectAttr(f"{cv_ctl}.matrix", f"{mult_matrix_secondary}.matrixIn[0]")
            cmds.connectAttr(f"{fbf_cv}.output", f"{mult_matrix_secondary}.matrixIn[1]")
            cmds.connectAttr(f"{mult_matrix_secondary}.matrixSum", f"{local_jnt_cv}.offsetParentMatrix")
            path_joints_lower.append(local_jnt_cv)
            tangent_mult_matrices_lower.append(mult_matrix_secondary)

            if side == "R" and i != 5:
                
                cmds.setAttr(f"{fbf_cv}.in00", -1)  # Invert X axis for right side
                
            if i % 3 == 0:
                
                cmds.addAttr(cv_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
                cmds.setAttr(f"{cv_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(cv_ctl, ln="Tan_Controllers_Visibility", at="bool", k=True)
                cmds.setAttr(f"{cv_ctl}.Tan_Controllers_Visibility", k=False, cb=True)
                cmds.connectAttr(f"{fbf_cv}.output", f"{cv_ctl_nodes[0]}.offsetParentMatrix")
                mult_matrix_tangent = None
            
            
            else:
                mult_matrix_tangent = cmds.createNode("multMatrix", name=f"{side}_{name}_MMT", ss=True)
                cmds.connectAttr(f"{fbf_cv}.output", f"{mult_matrix_tangent}.matrixIn[1]")
                cmds.connectAttr(f"{mult_matrix_tangent}.matrixSum", f"{cv_ctl_nodes[0]}.offsetParentMatrix", f=True)
            mult_matrix_tangents_lower.append(mult_matrix_tangent)
            cmds.parent(cv_ctl_nodes[0], secondary_controllers_nodes)
            if i == 0 or i == len(rebuilded_lower_lip_cvs) -1:
                aim = cmds.aimConstraint(
                    lower_lip_ctl,
                    cv_ctl_nodes[0],
                    aimVector=(-1, 0, 0),
                    upVector=(0, 1, 0),
                    worldUpType="scene",
                    name=f"{side}_lipCorner_AIM"
                )[0]
                cmds.delete(aim)

        for index, tangent in dict_parents.items():
            for child_index in tangent:
                cmds.connectAttr(f"{cvs_ctls_lower[index]}.Tan_Controllers_Visibility", f"{cv_nodes_lower[child_index]}.visibility")
                if mult_matrix_tangents_lower[child_index] == None:
                    continue
                else:
                    cmds.connectAttr(f"{cvs_ctls_lower[index]}.matrix", f"{mult_matrix_tangents_lower[child_index]}.matrixIn[0]")
                    cmds.connectAttr(f"{cvs_ctls_lower[index]}.matrix", f"{tangent_mult_matrices_lower[child_index]}.matrixIn[2]") # Added to keep tangent joints aligned
        
        # ----- Sticky lips setup -----
        mid_lip_crv = cmds.duplicate(upper_bezier_curve, name="C_midLips_CRV", renameChildren=True)[0]

        # Blend shape between upper and lower lips
        self.mid_lip_blend_shape = cmds.blendShape(upper_bezier_curve, lower_bezier_curve, mid_lip_crv, name="C_midLips_BS")[0]
        cmds.setAttr(f"{self.mid_lip_blend_shape}.w[0]", 0.5) # Initial blend value
        cmds.setAttr(f"{self.mid_lip_blend_shape}.{upper_bezier_curve}", 0.5)
        cmds.setAttr(f"{self.mid_lip_blend_shape}.{lower_bezier_curve}", 0.5)


        # Skin bezier curves to path joints
        self.upper_bezier_skin_cluster = cmds.skinCluster(path_joints_upper, upper_bezier_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_upperLipBezier_SKIN")[0]
        self.lower_bezier_skin_cluster = cmds.skinCluster(path_joints_lower, lower_bezier_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_lowerLipBezier_SKIN")[0]

        linear_cvs = cmds.ls(f"{self.upper_linear_lip_curve}.cv[*]", fl=True)
        upper_bezier_shape = cmds.listRelatives(upper_bezier_curve, s=True)[0]

        out_controllers = cmds.createNode("transform", name="C_outputControllers_GRP", ss=True, p=lips_controllers_grp)
        # Output joints
        for i, cv in enumerate(cmds.ls(f"{self.upper_linear_lip_curve}.cv[*]", flatten=True)):

            name = "upperLip"

            if i < (len(linear_cvs) -1) / 2 :
                side = "R"
                zip_ctl = "R_lipCorner_CTL"
            elif i == (len(linear_cvs) -1) / 2 :
                side = "C"

            else:
                side = "L"
                zip_ctl = "L_lipCorner_CTL"

            cv_pos = cmds.xform(cv, q=True, ws=True, t=True)
            parameter = self.getClosestParamToPosition(upper_bezier_curve, cv_pos)

            mtp = cmds.createNode("motionPath", n=f"{side}_{name}0{i}_MPA", ss=True)
            fourByFourMatrix = cmds.createNode("fourByFourMatrix", n=f"{side}_{name}0{i}_FBF", ss=True)

            cmds.connectAttr(f"{upper_bezier_curve}Shape.worldSpace[0]", f"{mtp}.geometryPath", f=True)
            
            cmds.setAttr(f"{mtp}.uValue", parameter)
            
            cmds.connectAttr(f"{mtp}.allCoordinates.xCoordinate", f"{fourByFourMatrix}.in30", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.yCoordinate", f"{fourByFourMatrix}.in31", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.zCoordinate", f"{fourByFourMatrix}.in32", f=True)
            if side == "R":
                cmds.setAttr(f"{fourByFourMatrix}.in00", -1)

            fourOrigPos = cmds.createNode("fourByFourMatrix", name=f"{side}_{name}0{i}Orig_4B4", ss=True)
            parent_matrix = cmds.createNode("parentMatrix", name=f"{side}_{name}0{i}_PMX", ss=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{i}].xValueEp", f"{fourOrigPos}.in30", f=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{i}].yValueEp", f"{fourOrigPos}.in31", f=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{i}].zValueEp", f"{fourOrigPos}.in32", f=True)

            cmds.connectAttr(f"{fourByFourMatrix}.output", f"{parent_matrix}.target[0].targetMatrix", f=True)
            cmds.connectAttr(f"{fourOrigPos}.output", f"{parent_matrix}.inputMatrix", f=True)
            joint = cmds.createNode("joint", n=f"{side}_{name}0{i}Skinning_JNT", ss=True, parent = self.skeleton_grp)
            cmds.connectAttr(f"{fourByFourMatrix}.output", f"{joint}.offsetParentMatrix", f=True)
            out_nodes, out_ctl = curve_tool.create_controller(f"{side}_{name}0{i}Out", offset=["GRP"], parent=self.controllers_grp)
            self.lock_attributes(out_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", self.matrix_get_offset_matrix(f"{fourOrigPos}.output", joint), type="matrix")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{out_nodes[0]}.offsetParentMatrix", f=True)
            mult_matrix_skinning = cmds.createNode("multMatrix", name=f"{side}_{name}0{i}_Skinning_MMT", ss=True)
            cmds.connectAttr(f"{out_ctl}.matrix", f"{mult_matrix_skinning}.matrixIn[0]", f=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix_skinning}.matrixIn[1]", f=True)

            cmds.connectAttr(f"{mult_matrix_skinning}.matrixSum", f"{joint}.offsetParentMatrix", f=True)

            # Add four by four martix to the mid lip curve to take the average position
            mid_4b4 = cmds.createNode("fourByFourMatrix", name=f"{side}_{name}0{i}_Mid_4B4", ss=True)
            # ---------- MUST CONNECT LATER TO THE CORRESPONDING CVS ----------
            cmds.connectAttr(f"{mid_lip_crv}Shape.editPoints[{i}].xValueEp", f"{mid_4b4}.in30", f=True)
            cmds.connectAttr(f"{mid_lip_crv}Shape.editPoints[{i}].yValueEp", f"{mid_4b4}.in31", f=True)
            cmds.connectAttr(f"{mid_lip_crv}Shape.editPoints[{i}].zValueEp", f"{mid_4b4}.in32", f=True)
            # Add a blendMartix node to blend between average and original position
            blend_matrix_mid = cmds.createNode("blendMatrix", name=f"{side}_{name}0{i}_Mid_BMT", ss=True)
            cmds.connectAttr(f"{mult_matrix_skinning}.matrixSum", f"{blend_matrix_mid}.inputMatrix")
            remap_value_zip = cmds.createNode("remapValue", name=f"{side}_{name}0{i}_Zip_RMV", ss=True)
            cmds.setAttr(f"{remap_value_zip}.value[0].value_Interp", 2)  # Set to smooth
            cmds.connectAttr(f"{zip_ctl}.Zip", f"{remap_value_zip}.inputValue")
            if side == "R":
                input_min = (i / ((len(linear_cvs) -1) / 2))
            else:
                input_min = 0.5 * (i / ((len(linear_cvs) -1) / 2))

            cmds.setAttr(f"{remap_value_zip}.inputMin", input_min)
            cmds.connectAttr(f"{remap_value_zip}.outValue", f"{blend_matrix_mid}.target[0].weight") # Weight based on Zip attribute
            cmds.connectAttr(f"{mid_4b4}.output", f"{blend_matrix_mid}.target[0].targetMatrix")
            cmds.connectAttr(f"{blend_matrix_mid}.outputMatrix", f"{joint}.offsetParentMatrix", f=True) # Final connection to joint

            cmds.parent(out_nodes[0], out_controllers)

        
        for i, cv in enumerate(cmds.ls(f"{self.lower_linear_lip_curve}.cv[*]", flatten=True)):

            name = "lowerLip"

            if i < (len(linear_cvs) -1) / 2 :
                side = "R"
                zip_ctl = "R_lipCorner_CTL"
            elif i == (len(linear_cvs) -1) / 2 :
                side = "C"
            else:
                side = "L"
                zip_ctl = "L_lipCorner_CTL"
            cv_pos = cmds.xform(cv, q=True, ws=True, t=True)
            parameter = self.getClosestParamToPosition(lower_bezier_curve, cv_pos)

            mtp = cmds.createNode("motionPath", n=f"{side}_{name}0{i}_MPA", ss=True)
            fourByFourMatrix = cmds.createNode("fourByFourMatrix", n=f"{side}_{name}0{i}_FBF", ss=True)

            cmds.connectAttr(f"{lower_bezier_curve}Shape.worldSpace[0]", f"{mtp}.geometryPath", f=True)
            
            cmds.setAttr(f"{mtp}.uValue", parameter)
            
            cmds.connectAttr(f"{mtp}.allCoordinates.xCoordinate", f"{fourByFourMatrix}.in30", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.yCoordinate", f"{fourByFourMatrix}.in31", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.zCoordinate", f"{fourByFourMatrix}.in32", f=True)
            if side == "R":
                cmds.setAttr(f"{fourByFourMatrix}.in00", -1)

            fourOrigPos = cmds.createNode("fourByFourMatrix", name=f"{side}_{name}0{i}Orig_4B4", ss=True)
            parent_matrix = cmds.createNode("parentMatrix", name=f"{side}_{name}0{i}_PMX", ss=True)
            cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{i}].xValueEp", f"{fourOrigPos}.in30", f=True)
            cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{i}].yValueEp", f"{fourOrigPos}.in31", f=True)
            cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{i}].zValueEp", f"{fourOrigPos}.in32", f=True)

            cmds.connectAttr(f"{fourByFourMatrix}.output", f"{parent_matrix}.target[0].targetMatrix", f=True)
            cmds.connectAttr(f"{fourOrigPos}.output", f"{parent_matrix}.inputMatrix", f=True)
            joint = cmds.createNode("joint", n=f"{side}_{name}0{i}Skinning_JNT", ss=True, parent = self.skeleton_grp)
            cmds.connectAttr(f"{fourByFourMatrix}.output", f"{joint}.offsetParentMatrix", f=True)
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", self.matrix_get_offset_matrix(f"{fourOrigPos}.output", joint), type="matrix")
            out_nodes, out_ctl = curve_tool.create_controller(f"{side}_{name}0{i}Out", offset=["GRP"], parent=secondary_controllers_nodes)
            self.lock_attributes(out_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{out_nodes[0]}.offsetParentMatrix", f=True)
            mult_matrix_skinning = cmds.createNode("multMatrix", name=f"{side}_{name}0{i}_Skinning_MMT", ss=True)
            cmds.connectAttr(f"{out_ctl}.matrix", f"{mult_matrix_skinning}.matrixIn[0]", f=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix_skinning}.matrixIn[1]", f=True)
            cmds.connectAttr(f"{mult_matrix_skinning}.matrixSum", f"{joint}.offsetParentMatrix", f=True)

            # Add four by four martix to the mid lip curve to take the average position
            mid_4b4 = cmds.createNode("fourByFourMatrix", name=f"{side}_{name}0{i}_Mid_4B4", ss=True)
            # ---------- MUST CONNECT LATER TO THE CORRESPONDING CVS ---------- 
            cmds.connectAttr(f"{mid_lip_crv}Shape.editPoints[{i}].xValueEp", f"{mid_4b4}.in30", f=True)
            cmds.connectAttr(f"{mid_lip_crv}Shape.editPoints[{i}].yValueEp", f"{mid_4b4}.in31", f=True)
            cmds.connectAttr(f"{mid_lip_crv}Shape.editPoints[{i}].zValueEp", f"{mid_4b4}.in32", f=True)
            # Add a blendMartix node to blend between average and original position
            blend_matrix_mid = cmds.createNode("blendMatrix", name=f"{side}_{name}0{i}_Mid_BMT", ss=True)
            cmds.connectAttr(f"{mult_matrix_skinning}.matrixSum", f"{blend_matrix_mid}.inputMatrix")
            remap_value_zip = cmds.createNode("remapValue", name=f"{side}_{name}0{i}_Zip_RMV", ss=True)
            cmds.setAttr(f"{remap_value_zip}.value[0].value_Interp", 2)  # Set to smooth
            cmds.connectAttr(f"{zip_ctl}.Zip", f"{remap_value_zip}.inputValue")
            if side == "R":
                input_min = (i / ((len(linear_cvs) -1) / 2))
            else:
                input_min = 0.5 * (i / ((len(linear_cvs) -1) / 2))
            cmds.setAttr(f"{remap_value_zip}.inputMin", input_min)
            cmds.connectAttr(f"{remap_value_zip}.outValue", f"{blend_matrix_mid}.target[0].weight") # Weight based on Zip attribute
            cmds.connectAttr(f"{mid_4b4}.output", f"{blend_matrix_mid}.target[0].targetMatrix")
            cmds.connectAttr(f"{blend_matrix_mid}.outputMatrix", f"{joint}.offsetParentMatrix", f=True) # Final connection to joint
            cmds.parent(out_nodes[0], out_controllers)


        condition_primary = cmds.createNode("condition", name="C_lipsPrimaryControllers_COND", ss=True)
        cmds.setAttr(f"{condition_primary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_primary}.secondTerm", 1)
        cmds.setAttr(f"{condition_primary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_primary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Lips", f"{condition_primary}.firstTerm")
        cmds.connectAttr(f"{condition_primary}.outColorR", f"{main_lips_controllers}.visibility", f=True)
        condition_secondary = cmds.createNode("condition", name="C_lipsSecondaryControllers_COND", ss=True)
        cmds.setAttr(f"{condition_secondary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_secondary}.secondTerm", 2)
        cmds.setAttr(f"{condition_secondary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_secondary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Lips", f"{condition_secondary}.firstTerm")
        cmds.connectAttr(f"{condition_secondary}.outColorR", f"{secondary_controllers_nodes}.visibility", f=True)
        condition_all = cmds.createNode("condition", name="C_lipsAllControllers_COND", ss=True)
        cmds.setAttr(f"{condition_all}.operation", 0)  # Equal
        cmds.setAttr(f"{condition_all}.secondTerm", 3)
        cmds.setAttr(f"{condition_all}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_all}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Lips", f"{condition_all}.firstTerm")
        cmds.connectAttr(f"{condition_all}.outColorR", f"{out_controllers}.visibility", f=True)

        condition_jaw = cmds.createNode("condition", name="C_jawControllers_COND", ss=True)
        cmds.setAttr(f"{condition_jaw}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_jaw}.secondTerm", 1)
        cmds.setAttr(f"{condition_jaw}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_jaw}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Jaw", f"{condition_jaw}.firstTerm")
        cmds.connectAttr(f"{condition_jaw}.outColorR", f"{self.jaw_nodes[0]}.visibility")
        cmds.connectAttr(f"{condition_jaw}.outColorR", f"{self.upper_jaw_nodes[0]}.visibility")

        secondary_condition_jaw = cmds.createNode("condition", name="C_jawSecondaryControllers_COND", ss=True)
        cmds.setAttr(f"{secondary_condition_jaw}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{secondary_condition_jaw}.secondTerm", 2)
        cmds.setAttr(f"{secondary_condition_jaw}.colorIfTrueR", 1)
        cmds.setAttr(f"{secondary_condition_jaw}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Jaw", f"{secondary_condition_jaw}.firstTerm")
        cmds.connectAttr(f"{secondary_condition_jaw}.outColorR", f"{'L_jaw_GRP'}.visibility")
        cmds.connectAttr(f"{secondary_condition_jaw}.outColorR", f"{'R_jaw_GRP'}.visibility")

    
        self.upper_bezier = upper_bezier_curve
        self.lower_bezier = lower_bezier_curve

        
    def get_offset_matrix(self, child, parent):

        """
        Calculate the offset matrix between a child and parent transform in Maya.
        Args:
            child (str): The name of the child transform.
            parent (str): The name of the parent transform. 
        Returns:
            om.MMatrix: The offset matrix that transforms the child into the parent's space.
        """
        child_dag = om.MSelectionList().add(child).getDagPath(0)
        parent_dag = om.MSelectionList().add(parent).getDagPath(0)

        child_world_matrix = child_dag.inclusiveMatrix()
        parent_world_matrix = parent_dag.inclusiveMatrix()
        
        offset_matrix = child_world_matrix * parent_world_matrix.inverse()

        
        return offset_matrix
    
    def matrix_get_offset_matrix(self, child, parent):
        """
        Calculate the offset matrix between a child and parent transform in Maya.
        Args:
            child (str): The name of the child transform or matrix attribute.
            parent (str): The name of the parent transform or matrix attribute. 
        Returns:
            list: The offset matrix as a flat list of 16 floats in row-major order that transforms the child into the parent's space.
        """
        def get_world_matrix(node):
            try:
                dag = om.MSelectionList().add(node).getDagPath(0)
                return dag.inclusiveMatrix()
            except:
                matrix = cmds.getAttr(node)
                return om.MMatrix(matrix)

        child_world_matrix = get_world_matrix(child)
        parent_world_matrix = get_world_matrix(parent)

        offset_matrix = child_world_matrix * parent_world_matrix.inverse()

        # Convert to Python list (row-major order)
        offset_matrix_list = list(offset_matrix)

        return offset_matrix_list
    
    def getClosestParamToPosition(self, curve, position):
        """
        Returns the closest parameter (u) on the given NURBS curve to a world-space position.
        
        Args:
            curve (str or MObject or MDagPath): The curve to evaluate.
            position (list or tuple): A 3D world-space position [x, y, z].

        Returns:
            float: The parameter (u) value on the curve closest to the given position.
        """
        if isinstance(curve, str):
            sel = om.MSelectionList()
            sel.add(curve)
            curve_dag_path = sel.getDagPath(0)
        elif isinstance(curve, om.MObject):
            curve_dag_path = om.MDagPath.getAPathTo(curve)
        elif isinstance(curve, om.MDagPath):
            curve_dag_path = curve
        else:
            raise TypeError("Curve must be a string name, MObject, or MDagPath.")

        curve_fn = om.MFnNurbsCurve(curve_dag_path)

        point = om.MPoint(*position)

        closest_point, paramU = curve_fn.closestPoint(point, space=om.MSpace.kWorld)

        return paramU