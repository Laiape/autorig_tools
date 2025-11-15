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

        self.load_guides()
        self.create_controllers()
        self.collision_setup()
        self.create_lips_setup()

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
        

        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.jaw_guide}.worldMatrix[0]", f"{self.upper_jaw_nodes[0]}.offsetParentMatrix")
        self.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])


        self.chin_nodes, self.chin_ctl = curve_tool.create_controller("C_chin", offset=["GRP"], parent=self.jaw_ctl)
        cmds.matchTransform(self.chin_nodes[0], self.chin_nodes[0].replace("C_chin_GRP", "C_chin_JNT"))
        self.lock_attributes(self.chin_ctl, ["v"])

        for side in ["L", "R"]:
            self.side_jaw_nodes, self.side_jaw_ctl = curve_tool.create_controller(f"{side}_jaw", offset=["GRP"], parent=self.jaw_ctl)
            cmds.matchTransform(self.side_jaw_nodes[0], self.side_jaw_nodes[0].replace(f"{side}_jaw_GRP", f"{side}_jaw_JNT"))
            self.lock_attributes(self.side_jaw_ctl, ["sx", "sy", "sz", "v"])

    def collision_setup(self):

        """
        Set up collision detection for the jaw module.
        """

        # Add attribute to the jaw controller
        cmds.addAttr(self.jaw_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
        cmds.setAttr(f"{self.jaw_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
        cmds.addAttr(self.jaw_ctl, longName="Collision", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)

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
        cmds.connectAttr(f"{self.jaw_ctl}.Collision", f"{attribute_blender}.attributesBlender")
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
        radius_loc = guides_manager.get_guides("C_jawSlide_LOCShape")
        self.upper_linear_lip_curve = guides_manager.get_guides("C_upperLipLinear_CRVShape", parent=self.module_trn)
        self.lower_linear_lip_curve = guides_manager.get_guides("C_lowerLipLinear_CRVShape", parent=self.module_trn)


        # Create NURBS surface
        self.sphere = guides_manager.get_guides("C_jaw_NURBShape", parent=self.module_trn) # NURBS surface guide
        cmds.hide(self.sphere)
        cmds.rotate(0, 90, 0, self.sphere, relative=True, objectSpace=True)
        cmds.setAttr(f"{radius_loc}.translateX", 0)
        self.sphere_guide = cmds.createNode("transform", name="C_jawSlideGuide_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.sphere_guide, radius_loc)
        cmds.delete(radius_loc)

        # Jaw local joint
        cmds.delete(self.jaw_jnt)
        self.jaw_jnt = cmds.createNode("joint", name="C_jaw_JNT", ss=True, p=self.module_trn)
        mult_matrix_jaw_local = cmds.createNode("multMatrix", name="C_jawLocal_MMT")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.matchTransform(self.jaw_jnt, self.jaw_ctl, pos=True)  # Only position

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
        

        # Create upper controller
        upper_lip_nodes, upper_lip_ctl = curve_tool.create_controller("C_upperLip", offset=["GRP"], parent=self.controllers_grp)
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

        # Create lower controller
        lower_lip_nodes, lower_lip_ctl = curve_tool.create_controller("C_lowerLip", offset=["GRP"], parent=self.controllers_grp)
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

        upper_local_jnts = []
        lower_local_jnts = []

        # Create corner controllers
        for side in ["L", "R"]:
            
            # Create corner controller and place them

            corner_nodes, corner_ctl = curve_tool.create_controller(f"{side}_lipCorner", offset=["GRP", "OFF"], parent=self.controllers_grp)
            self.lock_attributes(corner_ctl, ["sx", "sz", "v"])
            mtp_corner_lip = cmds.createNode("motionPath", name=f"{side}_lipCorner_MTP", ss=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.worldSpace[0]", f"{mtp_corner_lip}.geometryPath")

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
            cmds.setAttr(f"{corner_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
            cmds.addAttr(corner_ctl, longName="Jaw_Blend", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)

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
            if side == "L":
                upper_local_jnts.append(upper_local_jnt)
                lower_local_jnts.append(lower_local_jnt)


        # Rebuild curves for better deformation
        self.upper_rebuild_lip_curve = cmds.rebuildCurve(self.upper_linear_lip_curve, ch=0, rpo=0, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=4, d=3, tol=0.01, name="C_upperLip_CRV")[0]
        self.lower_rebuild_lip_curve = cmds.rebuildCurve(self.lower_linear_lip_curve, ch=0, rpo=0, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=4, d=3, tol=0.01, name="C_lowerLip_CRV")[0]
        cmds.parent(self.upper_rebuild_lip_curve, self.lower_rebuild_lip_curve, self.module_trn)

        # Skin cluster to local joints
        self.upper_skin_cluster = cmds.skinCluster(upper_local_jnts, self.upper_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_upperLip_SKIN")[0]
        self.lower_skin_cluster = cmds.skinCluster(lower_local_jnts, self.lower_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_lowerLip_SKIN")[0]

        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[0]", transformValue=[upper_local_jnts[0], 1.0])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[1]", transformValue=[upper_local_jnts[0], 0.5], transformValue=[upper_local_jnts[1], 0.5])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[2]", transformValue=[upper_local_jnts[0], 0.2], transformValue=[upper_local_jnts[1], 0.8])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[3]", transformValue=[upper_local_jnts[1], 1.0])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[4]", transformValue=[upper_local_jnts[1], 0.8], transformValue=[upper_local_jnts[2], 0.2])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[5]", transformValue=[upper_local_jnts[1], 0.5], transformValue=[upper_local_jnts[2], 0.5])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[6]", transformValue=[upper_local_jnts[2], 1.0])

        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[0]", transformValue=[lower_local_jnts[0], 1.0])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[1]", transformValue=[lower_local_jnts[0], 0.5], transformValue=[lower_local_jnts[1], 0.5])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[2]", transformValue=[lower_local_jnts[0], 0.2], transformValue=[lower_local_jnts[1], 0.8])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[3]", transformValue=[lower_local_jnts[1], 1.0])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[4]", transformValue=[lower_local_jnts[1], 0.8], transformValue=[lower_local_jnts[2], 0.2])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[5]", transformValue=[lower_local_jnts[1], 0.5], transformValue=[lower_local_jnts[2], 0.5])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[6]", transformValue=[lower_local_jnts[2], 1.0])

        # Cvs controllers for lips
        rebuilded_upper_lip_cvs = cmds.ls(f"{self.upper_rebuild_lip_curve}.cv[*]", fl=True)
        rebuilded_lower_lip_cvs = cmds.ls(f"{self.lower_rebuild_lip_curve}.cv[*]", fl=True)

        for i, cv in enumerate(rebuilded_upper_lip_cvs):
            side = "R" if i < len(rebuilded_upper_lip_cvs) / 2 else "L"
            cv_ctl_nodes, cv_ctl = curve_tool.create_controller(f"{side}_upperLip0{i}", offset=["GRP", "OFF"], parent=self.controllers_grp)
            self.lock_attributes(cv_ctl, ["sy", "sz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
            
            mtp_cv = cmds.createNode("motionPath", name=f"{side}_upperLip0{i}_MTP", ss=True)
            cmds.connectAttr(f"{self.upper_rebuild_lip_curve}.worldSpace[0]", f"{mtp_cv}.geometryPath")
            paramU = self.getClosestParamToPosition(self.upper_rebuild_lip_curve, cmds.xform(cv, q=True, ws=True, t=True))
            cmds.setAttr(f"{mtp_cv}.uValue", paramU)
            cmds.setAttr(f"{mtp_cv}.fractionMode", 1)
            fbf_cv = cmds.createNode("fourByFourMatrix", name=f"{side}_upperLip0{i}_FBF", ss=True)
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.xCoordinate", f"{fbf_cv}.in30")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.yCoordinate", f"{fbf_cv}.in31")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.zCoordinate", f"{fbf_cv}.in32")
            if side == "R":
                cmds.setAttr(f"{fbf_cv}.in00", -1)  # Invert X axis for right side
            cmds.connectAttr(f"{fbf_cv}.output", f"{cv_ctl_nodes[0]}.offsetParentMatrix")
            local_jnt_cv = cmds.createNode("joint", name=f"{side}_upperLip0{i}_JNT", ss=True, p=self.module_trn)
            cmds.connectAttr(f"{cv_ctl}.matrix", f"{local_jnt_cv}.offsetParentMatrix")
        
        for i, cv in enumerate(rebuilded_lower_lip_cvs):
            side = "R" if i < len(rebuilded_lower_lip_cvs) / 2 else "L"
            cv_ctl_nodes, cv_ctl = curve_tool.create_controller(f"{side}_lowerLip0{i}", offset=["GRP", "OFF"], parent=self.controllers_grp)
            self.lock_attributes(cv_ctl, ["sy", "sz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
            
            mtp_cv = cmds.createNode("motionPath", name=f"{side}_lowerLip0{i}_MTP", ss=True)
            cmds.connectAttr(f"{self.lower_rebuild_lip_curve}.worldSpace[0]", f"{mtp_cv}.geometryPath")
            paramU = self.getClosestParamToPosition(self.lower_rebuild_lip_curve, cmds.xform(cv, q=True, ws=True, t=True))
            cmds.setAttr(f"{mtp_cv}.uValue", paramU)
            cmds.setAttr(f"{mtp_cv}.fractionMode", 1)
            fbf_cv = cmds.createNode("fourByFourMatrix", name=f"{side}_lowerLip0{i}_FBF", ss=True)
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.xCoordinate", f"{fbf_cv}.in30")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.yCoordinate", f"{fbf_cv}.in31")
            cmds.connectAttr(f"{mtp_cv}.allCoordinates.zCoordinate", f"{fbf_cv}.in32")
            if side == "R":
                cmds.setAttr(f"{fbf_cv}.in00", -1)  # Invert X axis for right side
            cmds.connectAttr(f"{fbf_cv}.output", f"{cv_ctl_nodes[0]}.offsetParentMatrix")
            local_jnt_cv = cmds.createNode("joint", name=f"{side}_lowerLip0{i}_JNT", ss=True, p=self.module_trn)
            cmds.connectAttr(f"{cv_ctl}.matrix", f"{local_jnt_cv}.offsetParentMatrix")






        

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