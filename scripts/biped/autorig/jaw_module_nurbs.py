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

        # Clean up
        cmds.delete("L_jaw_JNT", "R_jaw_JNT")

        data_manager.DataExportBiped().append_data("jaw_module", 
                                                
                                                {"jaw_ctl": self.jaw_ctl,
                                                 "upper_jaw_ctl": self.upper_jaw_ctl,
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

        # ---- Jaw controller ----
        self.jaw_guide = cmds.createNode("transform", name="C_jaw_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.jaw_guide, self.jaw_guides[0], pos=True) # Only position

        self.jaw_nodes, self.jaw_ctl = curve_tool.create_controller("C_jaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        jaw_skinning = cmds.createNode("joint", name="C_jawSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{self.jaw_guide}.worldMatrix[0]", f"{self.jaw_nodes[0]}.offsetParentMatrix")
        self.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])

        mult_matrix_jaw = cmds.createNode("multMatrix", name="C_jawSkinning_MMX")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_jaw}.matrixSum", f"{jaw_skinning}.offsetParentMatrix")

        # ---- Upper jaw controller ----
        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.jaw_guide}.worldMatrix[0]", f"{self.upper_jaw_nodes[0]}.offsetParentMatrix")
        self.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])

        upper_jaw_skinning = cmds.createNode("joint", name="C_upperJawSkinning_JNT", ss=True, p=self.skeleton_grp)

        mult_matrix_upper_jaw = cmds.createNode("multMatrix", name="C_upperJawLocal_MMX")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_upper_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_upper_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.upper_jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_upper_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_upper_jaw}.matrixSum", f"{upper_jaw_skinning}.offsetParentMatrix")

        

        for side in ["L", "R"]:
            self.side_jaw_nodes, self.side_jaw_ctl = curve_tool.create_controller(f"{side}_jaw", offset=["GRP"], parent=self.jaw_ctl)
            cmds.matchTransform(self.side_jaw_nodes[0], self.side_jaw_nodes[0].replace(f"{side}_jaw_GRP", f"{side}_jaw_JNT"))
            self.lock_attributes(self.side_jaw_ctl, ["sx", "sy", "sz", "v"])

            side_jaw_skinning = cmds.createNode("joint", name=f"{side}_jawSkinning_JNT", ss=True, p=self.skeleton_grp)

            mult_matrix_side_jaw = cmds.createNode("multMatrix", name=f"{side}_jawLocal_MMX")
            cmds.connectAttr(f"{self.side_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_side_jaw}.matrixIn[0]") 
            cmds.connectAttr(f"{self.side_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_side_jaw}.matrixIn[1]")
            cmds.setAttr(f"{mult_matrix_side_jaw}.matrixIn[2]", cmds.getAttr(f"{self.side_jaw_ctl}.worldMatrix[0]"), type="matrix")
            cmds.connectAttr(f"{mult_matrix_side_jaw}.matrixSum", f"{side_jaw_skinning}.offsetParentMatrix")
            

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
        # cmds.select(self.jaw_nodes[1])
        # cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=0, v=0)
        # cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=15, v=0)
        # cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=35, v=0)
        # cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=45, v=0)
        # cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=60, v=0)s
        # cmds.setDrivenKeyframe(at="rotateX", cd=f"{self.jaw_ctl}.rotateX", dv=90, v=0)

        # cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=0, v=0)
        # cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=15, v=2)
        # cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=30, v=1.75)
        # cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=45, v=1.5)
        # cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=60, v=1.25)
        # cmds.setDrivenKeyframe(at="translateY", cd=f"{self.jaw_ctl}.rotateX", dv=90, v=-3.5)

        # cmds.setDrivenKeyframe(at="translateZ", cd=f"{self.jaw_ctl}.rotateX", dv=0, v=0)
        # cmds.setDrivenKeyframe(at="translateZ", cd=f"{self.jaw_ctl}.rotateX", dv=45, v=2)
        # cmds.setDrivenKeyframe(at="translateZ", cd=f"{self.jaw_ctl}.rotateX", dv=90, v=15)


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
        cmds.parent(self.sphere, self.module_trn)

        # Jaw local joint
        cmds.delete(self.jaw_jnt)
        self.jaw_jnt = cmds.createNode("joint", name="C_jaw_JNT", ss=True, p=self.module_trn)
        mult_matrix_jaw_local = cmds.createNode("multMatrix", name="C_jawLocal_MMT")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_jaw_local}.matrixSum", f"{self.jaw_jnt}.offsetParentMatrix")


        # Upper jaw local joint
        self.upper_jaw_jnt = cmds.createNode("joint", name="C_upperJaw_JNT", ss=True, p=self.module_trn)
        mult_matrix_upper_jaw_local = cmds.createNode("multMatrix", name="C_upperJawLocal_MMT")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_upper_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_upper_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.upper_jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_upper_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_upper_jaw_local}.matrixSum", f"{self.upper_jaw_jnt}.offsetParentMatrix")


        # Create constraints to upper and lower jaws
        # jaw_nurbs_skin_cluster = cmds.skinCluster(
        #         self.sphere,
        #         self.jaw_jnt,
        #         self.upper_jaw_jnt,
        #         toSelectedBones=True,
        #         bindMethod=0,
        #         normalizeWeights=1,
        #         weightDistribution=0,
        #         maximumInfluences=2,
        #         dropoffRate=4,
        #         removeUnusedInfluence=False,
        #         name="C_jawSlideNRB_SKIN"
        #     )[0]
        
        # u_spans = cmds.getAttr(f"{self.sphere}.spansU")
        # v_spans = cmds.getAttr(f"{self.sphere}.spansV")
        # degU = cmds.getAttr(f"{self.sphere}.degreeU")
        # degV = cmds.getAttr(f"{self.sphere}.degreeV")

        # u_count = u_spans + degU
        # v_count = v_spans + degV
        # half = int(u_count) // 2

        # for u in range(u_count):
        #     for v in range(v_count):
                
        #         if u > half:
        #             upper_w = 1.0
        #             jaw_w = 0.0
        #         elif u == half:
        #             jaw_w = 0.5
        #             upper_w = 0.5
        #         else:
        #             jaw_w = 1.0
        #             upper_w = 0.0

        #         cv = f"{self.sphere}.cv[{u}][{v}]"
                
        #         cmds.skinPercent(jaw_nurbs_skin_cluster, cv, transformValue=[
        #             (self.jaw_jnt, jaw_w),
        #             (self.upper_jaw_jnt, upper_w)
        #         ])
        
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
        upper_lip_parent_wm = cmds.createNode("parentMatrix", name="C_upperLip_PMX", ss=True)
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{upper_lip_parent_wm}.inputMatrix")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{upper_lip_parent_wm}.target[0].targetMatrix")
        cmds.connectAttr(f"{upper_lip_parent_wm}.outputMatrix", f"{upper_lip_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{upper_lip_parent_wm}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_upper_lip}.output", self.upper_jaw_ctl), type="matrix")

        # Local joint for upper lip
        upper_local_jnt = cmds.createNode("joint", name="C_upperLip_JNT", ss=True, p=self.module_trn)
        mmx_upper_local = cmds.createNode("multMatrix", name="C_upperLipLocal_MMT", ss=True)
        rfm_upper_local = cmds.createNode("rowFromMatrix", name="C_upperLipLocal_RMF", ss=True)
        cps_upper_local = cmds.createNode("closestPointOnSurface", name="C_upperLipLocal_CPS", ss=True)
        fbf_upper_lip_projected = cmds.createNode("fourByFourMatrix", name="C_upperLipProjected_FBF", ss=True)
        mmx_offset_jaw_pos_up = cmds.createNode("multMatrix", name="C_upperLipOffsetJawPos_MMT", ss=True)
        cmds.setAttr(f"{rfm_upper_local}.input", 3)  # Set rowFromMatrix to output translation

        cmds.connectAttr(f"{upper_lip_ctl}.matrix", f"{mmx_upper_local}.matrixIn[0]")
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{mmx_upper_local}.matrixIn[1]")
        cmds.connectAttr(f"{mmx_upper_local}.matrixSum", f"{rfm_upper_local}.matrix")
        cmds.connectAttr(f"{rfm_upper_local}.outputX", f"{cps_upper_local}.inPositionX")
        cmds.connectAttr(f"{rfm_upper_local}.outputY", f"{cps_upper_local}.inPositionY")
        cmds.connectAttr(f"{rfm_upper_local}.outputZ", f"{cps_upper_local}.inPositionZ")
        cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_upper_local}.inputSurface")
        cmds.connectAttr(f"{cps_upper_local}.positionX", f"{fbf_upper_lip_projected}.in30")
        cmds.connectAttr(f"{cps_upper_local}.positionY", f"{fbf_upper_lip_projected}.in31")
        cmds.connectAttr(f"{cps_upper_local}.positionZ", f"{fbf_upper_lip_projected}.in32")
        cmds.connectAttr(f"{fbf_upper_lip_projected}.output", f"{mmx_offset_jaw_pos_up}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mmx_offset_jaw_pos_up}.matrixIn[1]")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{mmx_offset_jaw_pos_up}.matrixIn[2]")
        cmds.connectAttr(f"{mmx_offset_jaw_pos_up}.matrixSum", f"{upper_local_jnt}.offsetParentMatrix")

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
        lower_lip_parent_wm = cmds.createNode("parentMatrix", name="C_lowerLip_PMX", ss=True)
        cmds.connectAttr(f"{fbf_lower_lip}.output", f"{lower_lip_parent_wm}.inputMatrix")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{lower_lip_parent_wm}.target[0].targetMatrix")
        cmds.connectAttr(f"{lower_lip_parent_wm}.outputMatrix", f"{lower_lip_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{lower_lip_parent_wm}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_lower_lip}.output", self.jaw_ctl), type="matrix")

        # Local joints for lower lips
        lower_local_jnt = cmds.createNode("joint", name="C_lowerLip_JNT", ss=True, p=self.module_trn)
        mmx_lower_local = cmds.createNode("multMatrix", name="C_lowerLipLocal_MMT", ss=True)
        rfm_lower_local = cmds.createNode("rowFromMatrix", name="C_lowerLipLocal_RMF", ss=True)
        cps_lower_local = cmds.createNode("closestPointOnSurface", name="C_lowerLipLocal_CPS", ss=True)
        fbf_lower_lip_projected = cmds.createNode("fourByFourMatrix", name="C_lowerLipProjected_FBF", ss=True)
        mmx_offset_jaw_pos_low = cmds.createNode("multMatrix", name="C_lowerLipOffsetJawPos_MMT", ss=True)
        cmds.setAttr(f"{rfm_lower_local}.input", 3)  # Set rowFromMatrix to output translation

        cmds.connectAttr(f"{lower_lip_ctl}.matrix", f"{mmx_lower_local}.matrixIn[0]")
        cmds.connectAttr(f"{fbf_lower_lip}.output", f"{mmx_lower_local}.matrixIn[1]")
        cmds.connectAttr(f"{mmx_lower_local}.matrixSum", f"{rfm_lower_local}.matrix")
        cmds.connectAttr(f"{rfm_lower_local}.outputX", f"{cps_lower_local}.inPositionX")
        cmds.connectAttr(f"{rfm_lower_local}.outputY", f"{cps_lower_local}.inPositionY")
        cmds.connectAttr(f"{rfm_lower_local}.outputZ", f"{cps_lower_local}.inPositionZ")
        cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_lower_local}.inputSurface")
        cmds.connectAttr(f"{cps_lower_local}.positionX", f"{fbf_lower_lip_projected}.in30")
        cmds.connectAttr(f"{cps_lower_local}.positionY", f"{fbf_lower_lip_projected}.in31")
        cmds.connectAttr(f"{cps_lower_local}.positionZ", f"{fbf_lower_lip_projected}.in32")
        cmds.connectAttr(f"{fbf_lower_lip_projected}.output", f"{mmx_offset_jaw_pos_low}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mmx_offset_jaw_pos_low}.matrixIn[1]")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mmx_offset_jaw_pos_low}.matrixIn[2]")
        cmds.connectAttr(f"{mmx_offset_jaw_pos_low}.matrixSum", f"{lower_local_jnt}.offsetParentMatrix")
        
        

        upper_local_jnts = []
        lower_local_jnts = []

        corner_nodes_ctls = []

        # Create corner controllers
        for side in ["L", "R"]:
            
            # Create corner controller and place them

            corner_nodes, corner_ctl = curve_tool.create_controller(f"{side}_lipCorner", offset=["GRP", "OFF"], parent=main_lips_controllers)
            self.lock_attributes(corner_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
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

            if side == "R":

                cmds.setAttr(f"{fbf_corner_lip}.in00", -1)  # Invert X axis for right corner

            # Create blending between upper and lower lips
            cmds.addAttr(corner_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
            cmds.setAttr(f"{corner_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
            cmds.addAttr(corner_ctl, longName="Height", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)
            cmds.addAttr(corner_ctl, longName="Zip", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
            cmds.addAttr(corner_ctl, longName="Roll", attributeType="float", defaultValue=0, keyable=True)

            parent_matrix_blender = cmds.createNode("parentMatrix", name=f"{side}_lipCorner_PMX", ss=True)
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{parent_matrix_blender}.inputMatrix")
            cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{parent_matrix_blender}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{parent_matrix_blender}.target[1].targetMatrix")
            reverse_blender = cmds.createNode("reverse", name=f"{side}_lipCorner_REV", ss=True)
            cmds.connectAttr(f"{corner_ctl}.Height", f"{reverse_blender}.inputX")
            cmds.connectAttr(f"{reverse_blender}.outputX", f"{parent_matrix_blender}.target[0].weight")
            cmds.connectAttr(f"{corner_ctl}.Height", f"{parent_matrix_blender}.target[1].weight")

            cmds.connectAttr(f"{parent_matrix_blender}.outputMatrix", f"{corner_nodes[0]}.offsetParentMatrix")
            cmds.setAttr(f"{parent_matrix_blender}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_corner_lip}.output", self.jaw_ctl), type="matrix")
            cmds.setAttr(f"{parent_matrix_blender}.target[1].offsetMatrix", self.get_offset_matrix(f"{fbf_corner_lip}.output", self.upper_jaw_ctl), type="matrix")

            local_jnt = cmds.createNode("joint", name=f"{side}_cornerLip_JNT", ss=True, p=self.module_trn)
            mmx_local = cmds.createNode("multMatrix", name=f"{side}_lowerLipLocal_MMT", ss=True)
            rfm_local = cmds.createNode("rowFromMatrix", name=f"{side}_lowerLipLocal_RMF", ss=True)
            cps_local = cmds.createNode("closestPointOnSurface", name=f"{side}_lowerLipLocal_CPS", ss=True)
            fbf_lip_projected = cmds.createNode("fourByFourMatrix", name=f"{side}_lowerLipProjected_FBF", ss=True)
            mmx_offset_jaw_pos = cmds.createNode("multMatrix", name=f"{side}_lowerLipOffsetJawPos_MMT", ss=True)
            cmds.setAttr(f"{rfm_local}.input", 3)  # Set rowFromMatrix to output translation

            cmds.connectAttr(f"{corner_ctl}.matrix", f"{mmx_local}.matrixIn[0]")
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{mmx_local}.matrixIn[1]")
            cmds.connectAttr(f"{mmx_local}.matrixSum", f"{rfm_local}.matrix")
            cmds.connectAttr(f"{rfm_local}.outputX", f"{cps_local}.inPositionX")
            cmds.connectAttr(f"{rfm_local}.outputY", f"{cps_local}.inPositionY")
            cmds.connectAttr(f"{rfm_local}.outputZ", f"{cps_local}.inPositionZ")
            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_local}.inputSurface")
            cmds.connectAttr(f"{cps_local}.positionX", f"{fbf_lip_projected}.in30")
            cmds.connectAttr(f"{cps_local}.positionY", f"{fbf_lip_projected}.in31")
            cmds.connectAttr(f"{cps_local}.positionZ", f"{fbf_lip_projected}.in32")
            cmds.connectAttr(f"{fbf_lip_projected}.output", f"{mmx_offset_jaw_pos}.matrixIn[0]")
            cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mmx_offset_jaw_pos}.matrixIn[1]")
            cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mmx_offset_jaw_pos}.matrixIn[2]")
            cmds.connectAttr(f"{mmx_offset_jaw_pos}.matrixSum", f"{local_jnt}.offsetParentMatrix")

            upper_local_jnts.append(local_jnt)
            lower_local_jnts.append(local_jnt)
            if side == "L":
                upper_local_jnts.append(upper_local_jnt)
                lower_local_jnts.append(lower_local_jnt)
            
            # Aim constraint to keep corner oriented correctly
            if self.side == "L":
                aim_vector = (0, 0, 1)
            else:
                aim_vector = (0, 0, -1)
            
            aim = cmds.aimConstraint(
                self.jaw_ctl,
                corner_nodes[0],
                aimVector=aim_vector,
                upVector=(0, 1, 0),
                worldUpType="scene",
                name=f"{side}_lipCorner_AIM"
            )[0]
            cmds.delete(aim)

        # cmds.delete(temp_joint)

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
        upper_curve_dup = cmds.duplicate(self.upper_rebuild_lip_curve, name="C_upperLipToNurbs_CRV")[0]
        lower_curve_dup = cmds.duplicate(self.lower_rebuild_lip_curve, name="C_lowerLipToNurbs_CRV")[0]

        # Do an offset curve to avoid having the nurbs surface right on top of the rebuild curve, which causes issues when lofting
        upper_offset = cmds.offsetCurve(
            upper_curve_dup,
            distance=1,
            constructionHistory=False,
            reparameterize=False,
            cutLoop=True,
            cutRadius=0.1,
            tolerance=0.001,
            subdivisionDensity=0,
            useGivenNormal=False
    )
    
        upper_offset_curve = upper_offset[0]
        lower_offset = cmds.offsetCurve(
            lower_curve_dup,
            distance=1,
            constructionHistory=False,
            reparameterize=False,
            cutLoop=True,
            cutRadius=0.1,
            tolerance=0.001,
            subdivisionDensity=0,
            useGivenNormal=False
        )
        lower_offset_curve = lower_offset[0]

        upper_nurbs_surface = cmds.loft(
        [upper_offset_curve, self.upper_rebuild_lip_curve], 
        constructionHistory=False,
        uniform=True,
        close=False,
        autoReverse=True,
        degree=3,
        sectionSpans=2,
        reverseSurfaceNormals=True,
        polygon=0,
        name="C_upperLip_NURB"
        )[0]

        lower_nurbs_surface = cmds.loft(
            [lower_offset_curve, self.lower_rebuild_lip_curve],
            constructionHistory=False,
            uniform=True,
            close=False,
            autoReverse=True,
            degree=3,
            sectionSpans=2,
            reverseSurfaceNormals=True,
            polygon=0,
            name="C_lowerLip_NURB"
        )[0]

        cmds.delete(upper_curve_dup, lower_curve_dup, upper_offset_curve, lower_offset_curve)

        # Rebuild nurbs surfaces for better deformation and make it bezier (rt=7)
        self.upper_lip_nurbs = cmds.rebuildSurface(upper_nurbs_surface, ch=0, rpo=1, rt=7, end=1, kr=0, kcp=0, su=1, sv=3, du=3, dv=3, tol=0.01, name="C_upperLip_NURB")[0]
        self.lower_lip_nurbs = cmds.rebuildSurface(lower_nurbs_surface, ch=0, rpo=1, rt=7, end=1, kr=0, kcp=0, su=1, sv=3, du=3, dv=3, tol=0.01, name="C_lowerLip_NURB")[0]
        cmds.parent(self.upper_lip_nurbs, self.lower_lip_nurbs, self.module_trn)

        # Create secondary nodes GRP to control visibility
        secondary_controllers_nodes = cmds.createNode("transform", name="C_secondaryLipsControllers_GRP", ss=True, parent=lips_controllers_grp)

        # ----- Start nurbs setup -----
        upper_nurbs_surface_cvs = cmds.ls(f"{self.upper_lip_nurbs}.cv[*]", flatten=True)
        lower_nurbs_surface_cvs = cmds.ls(f"{self.lower_lip_nurbs}.cv[*]", flatten=True)

        spans_v = cmds.getAttr(f"{self.upper_lip_nurbs}.spansV")
        degree_v = cmds.getAttr(f"{self.upper_lip_nurbs}.degreeV")
        spans_u = cmds.getAttr(f"{self.upper_lip_nurbs}.spansU")
        degree_u = cmds.getAttr(f"{self.upper_lip_nurbs}.degreeU")
        num_cvs_v = spans_v + degree_v
        num_cvs_u = spans_u + degree_u
        max_index_u = num_cvs_u - 1
        max_index_v = num_cvs_v - 1

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):

            cvs = upper_nurbs_surface_cvs if part == "upper" else lower_nurbs_surface_cvs
            curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve

            mid_point = max_index_u // 2

            secondary_grps = []
            secondary_ctls = []
            secondary_local_joints_mmx = []
            secondary_joints = []

            for index in range(0, max_index_u + 1):

                if index < mid_point:
                    side = "R"
                elif index == mid_point:
                    side = "C"
                else:
                    side = "L"

                ctl_name = (
                    f"{side}_{part}Lip{str(index).zfill(2)}"
                    if index % 3 == 0
                    else f"{side}_{part}Lip{str(index).zfill(2)}Tan"
                )

                secondary_nodes, secondary_ctl = curve_tool.create_controller(
                    ctl_name,
                    offset=["GRP", "OFF"],
                    parent=secondary_controllers_nodes
                )
                self.lock_attributes(secondary_ctl, ["v"])

                secondary_local_joint = cmds.createNode(
                    "joint", name=f"{ctl_name}_JNT", ss=True, parent=self.module_trn
                )

                surface_cvs_row = cmds.ls(f"{nurbs}.cv[{index}][*]", flatten=True)

                if not surface_cvs_row:
                    cmds.warning(f"No CVs found for {nurbs}.cv[{index}][*], skipping.")
                    continue

                mid_cv_idx = len(surface_cvs_row) // 2
                ref_cv = surface_cvs_row[mid_cv_idx]
                cv_ws_pos = cmds.xform(ref_cv, query=True, worldSpace=True, translation=True)
                real_param = self.getClosestParamToPosition(curve, cv_ws_pos)

                mp = cmds.createNode("motionPath", name=f"{ctl_name}_MPT", ss=True)
                cmds.setAttr(f"{mp}.fractionMode", False)
                cmds.setAttr(f"{mp}.uValue", real_param)
                cmds.connectAttr(f"{curve}.worldSpace[0]", f"{mp}.geometryPath")

                fbf = cmds.createNode("fourByFourMatrix", name=f"{ctl_name}_FBF", ss=True)
                cmds.connectAttr(f"{mp}.xCoordinate", f"{fbf}.in30")
                cmds.connectAttr(f"{mp}.yCoordinate", f"{fbf}.in31")
                cmds.connectAttr(f"{mp}.zCoordinate", f"{fbf}.in32")

                if side == "R":
                    if mid_point - 1 == index:  # If it's the rightmost controller before the center, invert it
                        print(f"Not inverting {ctl_name} on X axis")
                        pass
                    else:
                        cmds.setAttr(f"{fbf}.in00", -1)

                cmds.connectAttr(f"{fbf}.output", f"{secondary_nodes[0]}.offsetParentMatrix")

                mult_matrix_secondary_local = cmds.createNode(
                    "multMatrix", name=f"{ctl_name}Local_MMX", ss=True
                )
                cmds.connectAttr(f"{secondary_ctl}.matrix", f"{mult_matrix_secondary_local}.matrixIn[0]")
                cmds.connectAttr(f"{fbf}.output", f"{mult_matrix_secondary_local}.matrixIn[1]")
                cmds.connectAttr(
                    f"{mult_matrix_secondary_local}.matrixSum",
                    f"{secondary_local_joint}.offsetParentMatrix"
                )

                if index % 3 == 0:
                    cmds.addAttr(secondary_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
                    cmds.setAttr(f"{secondary_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
                    cmds.addAttr(secondary_ctl, ln="Tan_Controllers_Visibility", at="bool", k=True)
                    cmds.setAttr(f"{secondary_ctl}.Tan_Controllers_Visibility", k=False, cb=True)

                secondary_grps.append(secondary_nodes[0])
                secondary_ctls.append(secondary_ctl)
                secondary_local_joints_mmx.append(mult_matrix_secondary_local)
                secondary_joints.append(secondary_local_joint)

            total_ctls = len(secondary_ctls)
            dict_parents = {}
            for i in range(0, total_ctls, 3):
                neighbors = [n for n in [i - 1, i + 1] if 0 <= n < total_ctls]
                dict_parents[i] = neighbors

            for parent_idx, children in dict_parents.items():
                for child_idx in children:
                    cmds.connectAttr(f"{secondary_ctls[parent_idx]}.Tan_Controllers_Visibility", f"{secondary_grps[child_idx]}.visibility")

                    tan_name = secondary_ctls[child_idx].split("_CTL")[0]

                    parent_connection = cmds.listConnections(f"{secondary_grps[child_idx]}.offsetParentMatrix", source=True, destination=False)[0]

                    mmx_controller = cmds.createNode("multMatrix", name=f"{tan_name}Parent_MMX", ss=True)
                    cmds.connectAttr(f"{secondary_ctls[parent_idx]}.matrix", f"{mmx_controller}.matrixIn[0]")
                    parent_node_type = cmds.nodeType(parent_connection)
                    parent_out_attr = "output" if parent_node_type == "fourByFourMatrix" else "matrixSum"
                    cmds.connectAttr(f"{parent_connection}.{parent_out_attr}", f"{mmx_controller}.matrixIn[1]")
                    cmds.connectAttr(f"{mmx_controller}.matrixSum", f"{secondary_grps[child_idx]}.offsetParentMatrix", f=True)

                    joint_connection = cmds.listConnections(f"{secondary_joints[child_idx]}.offsetParentMatrix", source=True, destination=False)[0]

                    mmx_local = cmds.createNode("multMatrix", name=f"{tan_name}ParentLocal_MMX", ss=True)
                    joint_node_type = cmds.nodeType(joint_connection)
                    joint_out_attr = "output" if joint_node_type == "fourByFourMatrix" else "matrixSum"
                    cmds.connectAttr(f"{secondary_ctls[parent_idx]}.matrix", f"{mmx_local}.matrixIn[0]")
                    cmds.connectAttr(f"{joint_connection}.{joint_out_attr}", f"{mmx_local}.matrixIn[1]")
                    cmds.connectAttr(f"{mmx_local}.matrixSum", f"{secondary_joints[child_idx]}.offsetParentMatrix", f=True)

            
            for i, joint in enumerate(secondary_joints):
                
                joint_name = joint.split("_JNT")[0]
                ctl = secondary_ctls[i]

                input_connections = cmds.listConnections(f"{joint}.offsetParentMatrix", source=True, destination=False)
                if not input_connections:
                    continue
                input_connection = input_connections[0]
                
                pick_matrix = cmds.createNode("pickMatrix", name=f"{joint_name}_PCM", ss=True)
                decompose_matrix = cmds.createNode("decomposeMatrix", name=f"{joint_name}_DCM", ss=True)
                rfm_project = cmds.createNode("rowFromMatrix", name=f"{joint_name}Project_RMF", ss=True)
                cps_project = cmds.createNode("closestPointOnSurface", name=f"{joint_name}Project_CPS", ss=True)
                
                cmds.setAttr(f"{pick_matrix}.useTranslate", 0)
                cmds.setAttr(f"{pick_matrix}.useShear", 0)
                cmds.setAttr(f"{rfm_project}.input", 3) # Fila 3 = Traslación
                
                cmds.connectAttr(f"{input_connection}.matrixSum", f"{pick_matrix}.inputMatrix")
                cmds.connectAttr(f"{pick_matrix}.outputMatrix", f"{decompose_matrix}.inputMatrix")
                cmds.connectAttr(f"{decompose_matrix}.outputRotate", f"{joint}.rotate")
                cmds.connectAttr(f"{decompose_matrix}.outputScale", f"{joint}.scale")
                
                cmds.connectAttr(f"{input_connection}.matrixSum", f"{rfm_project}.matrix")
                cmds.connectAttr(f"{rfm_project}.outputX", f"{cps_project}.inPositionX")
                cmds.connectAttr(f"{rfm_project}.outputY", f"{cps_project}.inPositionY")
                cmds.connectAttr(f"{rfm_project}.outputZ", f"{cps_project}.inPositionZ")

                cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_project}.inputSurface")
                cmds.connectAttr(f"{cps_project}.position", f"{joint}.translate")
                cmds.disconnectAttr(f"{input_connection}.matrixSum", f"{joint}.offsetParentMatrix")
                identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
                cmds.setAttr(f"{joint}.offsetParentMatrix", identity, type="matrix")


            skin_cluster = cmds.skinCluster(secondary_joints, nurbs, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name=f"C_{part}Nurbs_SKIN")[0]

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):

            cvs = upper_nurbs_surface_cvs if part == "upper" else lower_nurbs_surface_cvs
            curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            linear_curve = self.upper_linear_lip_curve if part == "upper" else self.lower_linear_lip_curve
            linear_curve_cvs = len(cmds.ls(f"{linear_curve}.cv[*]", flatten=True))
            mid_point = linear_curve_cvs // 2

            for i in range(0, linear_curve_cvs):

                surface_cv = f"{nurbs}.cv[{i}][0]"
                curve_cv = f"{curve}.cv[{i}]"

                if i < mid_point:
                    side = "R"
                elif i == mid_point:
                    side = "C"
                else:
                    side = "L"

                cv_ws_pos = cmds.xform(surface_cv, query=True, worldSpace=True, translation=True)
                u_param, v_param = matrix_manager.getClosestParamsToPositionSurface(nurbs, cv_ws_pos)
                vertex_cv = cmds.xform(curve_cv, query=True, worldSpace=True, translation=True)
                param_vertex = matrix_manager.getClosestParamToWorldMatrixCurve(curve, vertex_cv)

                point_on_surface_info = cmds.createNode("pointOnSurfaceInfo", name=f"{side}_{part}Lip{str(i).zfill(2)}_POS", ss=True)
                point_on_surface_info_up = cmds.createNode("pointOnSurfaceInfo", name=f"{side}_{part}Lip{str(i).zfill(2)}Up_POS", ss=True)
                fbf_aim = cmds.createNode("fourByFourMatrix", name=f"{side}_{part}Lip{str(i).zfill(2)}_Aim_FBF", ss=True)
                fbf_up = cmds.createNode("fourByFourMatrix", name=f"{side}_{part}Lip{str(i).zfill(2)}_Up_FBF", ss=True)

                cmds.connectAttr(f"{nurbs}.worldSpace[0]", f"{point_on_surface_info}.inputSurface")
                cmds.connectAttr(f"{nurbs}.worldSpace[0]", f"{point_on_surface_info_up}.inputSurface")
                cmds.setAttr(f"{point_on_surface_info}.parameterU", 0.5)
                cmds.setAttr(f"{point_on_surface_info}.parameterV", param_vertex)
                cmds.setAttr(f"{point_on_surface_info_up}.parameterU", 0.5)
                cmds.setAttr(f"{point_on_surface_info_up}.parameterV", param_vertex)  # Slightly above the original CV to get the up vector

                cmds.connectAttr(f"{point_on_surface_info}.positionX", f"{fbf_aim}.in30")
                cmds.connectAttr(f"{point_on_surface_info}.positionY", f"{fbf_aim}.in31")
                cmds.connectAttr(f"{point_on_surface_info}.positionZ", f"{fbf_aim}.in32")
                cmds.connectAttr(f"{point_on_surface_info_up}.positionX", f"{fbf_up}.in30")
                cmds.connectAttr(f"{point_on_surface_info_up}.positionY", f"{fbf_up}.in31")
                cmds.connectAttr(f"{point_on_surface_info_up}.positionZ", f"{fbf_up}.in32")

                aim_matrix_vector = cmds.createNode("aimMatrix", name=f"{side}_{part}Lip{str(i).zfill(2)}AimMatrixVector_AMX", ss=True)
                cmds.connectAttr(f"{fbf_aim}.output", f"{aim_matrix_vector}.inputMatrix")
                cmds.connectAttr(f"{fbf_aim}.output", f"{aim_matrix_vector}.primaryTargetMatrix")
                cmds.connectAttr(f"{fbf_up}.output", f"{aim_matrix_vector}.secondaryTargetMatrix")
                cmds.setAttr(f"{aim_matrix_vector}.primaryInputAxis", 0,0,1)
                cmds.setAttr(f"{aim_matrix_vector}.primaryTargetVector", 0,0,1)
                cmds.setAttr(f"{aim_matrix_vector}.primaryMode", 2)
                cmds.setAttr(f"{aim_matrix_vector}.secondaryInputAxis", 1,0,0)
                if side == "R":
                    cmds.setAttr(f"{aim_matrix_vector}.secondaryInputAxis", -1,0,0)
                cmds.setAttr(f"{aim_matrix_vector}.secondaryMode", 1)

                fbf = cmds.createNode("fourByFourMatrix", name=f"{side}_{part}Lip{str(i).zfill(2)}Position_FBF", ss=True)
                cmds.connectAttr(f"{linear_curve}.editPoints[{i}].xValueEp", f"{fbf}.in30")
                cmds.connectAttr(f"{linear_curve}.editPoints[{i}].yValueEp", f"{fbf}.in31")
                cmds.connectAttr(f"{linear_curve}.editPoints[{i}].zValueEp", f"{fbf}.in32")

    
                out_joint = cmds.createNode("joint", name=f"{side}_{part}Lip{str(i).zfill(2)}Skinning_JNT", ss=True, parent=self.skeleton_grp)
                cmds.connectAttr(f"{aim_matrix_vector}.outputMatrix", f"{out_joint}.offsetParentMatrix")


        # ------ Conditions to control visibility of lip controllers ------
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
        # cmds.connectAttr(f"{condition_all}.outColorR", f"{out_controllers}.visibility", f=True)

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

    
    def get_offset_matrix(self, child, parent):
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