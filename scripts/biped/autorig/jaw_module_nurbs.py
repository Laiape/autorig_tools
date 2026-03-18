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

        cmds.select(self.sphere)
        temp_joint = cmds.joint(name="tempLip_JNT")

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
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{corner_nodes[0]}.offsetParentMatrix")

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

        upper_nurbs_surface = cmds.loft([upper_curve_dup, lower_curve_dup], ch=0, u=1, c=0, name="C_upperLip_NURB")[0]
        lower_nurbs_surface = cmds.loft([upper_curve_dup, lower_curve_dup], ch=0, u=1, c=0, name="C_lowerLip_NURB")[0]
        cmds.delete(upper_curve_dup, lower_curve_dup)

        # Rebuild nurbs surfaces for better deformation and make it bezier (rt=7)
        self.upper_lip_nurbs = cmds.rebuildSurface(upper_nurbs_surface, ch=0, rpo=1, rt=7, end=1, kr=0, kcp=0, su=1, sv=3, du=3, dv=3, tol=0.01, name="C_upperLip_NURB")[0]
        self.lower_lip_nurbs = cmds.rebuildSurface(lower_nurbs_surface, ch=0, rpo=1, rt=7, end=1, kr=0, kcp=0, su=1, sv=3, du=3, dv=3, tol=0.01, name="C_lowerLip_NURB")[0]
        cmds.parent(self.upper_lip_nurbs, self.lower_lip_nurbs, self.module_trn)

        # Create secondary nodes GRP to control visibility
        secondary_controllers_nodes = cmds.createNode("transform", name="C_secondaryLipsControllers_GRP", ss=True, parent=lips_controllers_grp)

        # ----- Start nurbs setup -----
        upper_nurbs_surface_cvs = cmds.ls(f"{self.upper_lip_nurbs}.cv[*]", flatten=True)
        lower_nurbs_surface_cvs = cmds.ls(f"{self.lower_lip_nurbs}.cv[*]", flatten=True)

        # Get spans and degree to calculate CV indices
        spans_v = cmds.getAttr(f"{self.upper_lip_nurbs}.spansV")
        degree_v = cmds.getAttr(f"{self.upper_lip_nurbs}.degreeV")
        max_index = (spans_v + degree_v - 1) # Calculate the maximum CV index in V direction
        

        dict_parents = {} # Dictionary to store parent-child relationships for tangent controllers

        for i in range(0, max_index + 1, 3):
            neighbors = [n for n in [i-1, i+1] if 0 <= n <= max_index]
            dict_parents[i] = neighbors

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):
    
            cvs = upper_nurbs_surface_cvs if part == "upper" else lower_nurbs_surface_cvs
            curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            linear_curve = self.upper_linear_lip_curve if part == "upper" else self.lower_linear_lip_curve

            mid_point = max_index // 2

            secondary_grps = []
            secondary_ctls = []
            secondary_local_joints_mmx = []
            secondary_joints = []

            for i in range(0, len(cvs) - 1, 3):

                index = i // 3

                if index > max_index:
                    break

                if index < mid_point:
                    side = "R"
                elif index == mid_point:
                    side = "C"
                else:
                    side = "L"

                ctl_name = f"{side}_{part}Lip{str(index).zfill(2)}" if index % 3 == 0 else f"{side}_{part}Lip{str(index).zfill(2)}Tan"

                # Create controller for each CV
                secondary_nodes, secondary_ctl = curve_tool.create_controller(
                    ctl_name, 
                    offset=["GRP", "OFF"], 
                    parent=lips_controllers_grp
                )
                self.lock_attributes(secondary_ctl, ["v"])

                secondary_local_joint = cmds.createNode("joint", name=f"{ctl_name}_JNT", ss=True, parent=self.module_trn)
                
                surface_cv = f"{nurbs}.cv[0][{index}]"
                cv_ws_pos = cmds.xform(surface_cv, query=True, worldSpace=True, translation=True)

                # 2. Calcular el parámetro U inicial usando tu función de API
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
                    cmds.setAttr(f"{fbf}.in00", -1) 
                cmds.connectAttr(f"{fbf}.output", f"{secondary_nodes[0]}.offsetParentMatrix")

                # Create multMatrix to connect controller to local joint
                mult_matrix_secondary_local = cmds.createNode("multMatrix", name=f"{ctl_name}Local_MMX", ss=True)
                cmds.connectAttr(f"{secondary_ctl}.matrix", f"{mult_matrix_secondary_local}.matrixIn[0]")
                cmds.connectAttr(f"{fbf}.output", f"{mult_matrix_secondary_local}.matrixIn[1]")
                cmds.connectAttr(f"{mult_matrix_secondary_local}.matrixSum", f"{secondary_local_joint}.offsetParentMatrix")

                if index % 3 == 0:
                
                    cmds.addAttr(secondary_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
                    cmds.setAttr(f"{secondary_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
                    cmds.addAttr(secondary_ctl, ln="Tan_Controllers_Visibility", at="bool", k=True)
                    cmds.setAttr(f"{secondary_ctl}.Tan_Controllers_Visibility", k=False, cb=True)

                secondary_grps.append(secondary_nodes[0])
                secondary_ctls.append(secondary_ctl)
                secondary_local_joints_mmx.append(mult_matrix_secondary_local)
                secondary_joints.append(secondary_local_joint)

            for parent_idx, children in dict_parents.items():
                for child_idx in children:
                    cmds.connectAttr(f"{secondary_ctls[parent_idx]}.Tan_Controllers_Visibility", f"{secondary_grps[child_idx]}.visibility")

                    # Add the parent to the tangent controllers
                    tan_name = secondary_ctls[child_idx].split("_CTL")[0]
                    parent_connection = cmds.listConnections(f"{secondary_grps[child_idx]}.offsetParentMatrix", source=True, destination=False)[0] # Get current GRP connection
                    mmx_controller = cmds.createNode("multMatrix", name=f"{tan_name}Parent_MMX", ss=True)
                    cmds.connectAttr(f"{secondary_ctls[parent_idx]}.matrix", f"{mmx_controller}.matrixIn[0]")
                    cmds.connectAttr(f"{parent_connection}.output", f"{mmx_controller}.matrixIn[1]")
                    cmds.connectAttr(f"{mmx_controller}.matrixSum", f"{secondary_grps[child_idx]}.offsetParentMatrix", f=True)

                    # Add the parent to the local joint as well
                    mmx_local = cmds.createNode("multMatrix", name=f"{tan_name}ParentLocal_MMX", ss=True)
                    joint_connection = cmds.listConnections(f"{secondary_joints[child_idx]}.offsetParentMatrix", source=True, destination=False)[0] # Get current local joint connection
                    cmds.connectAttr(f"{secondary_ctls[parent_idx]}.matrix", f"{mmx_local}.matrixIn[0]")
                    cmds.connectAttr(f"{joint_connection}.matrixSum", f"{mmx_local}.matrixIn[1]")
                    cmds.connectAttr(f"{mmx_local}.matrixSum", f"{secondary_joints[child_idx]}.offsetParentMatrix", f=True)

            skin_cluster = cmds.skinCluster(secondary_joints, nurbs, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name=f"C_{part}Nurbs_SKIN")[0]

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):

            cvs = upper_nurbs_surface_cvs if part == "upper" else lower_nurbs_surface_cvs
            curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            linear_curve = self.upper_linear_lip_curve if part == "upper" else self.lower_linear_lip_curve

            for i in range(0, len(cvs) - 1, 3):

                index = i // 3

                if index < mid_point:
                    side = "R"
                elif index == mid_point:
                    side = "C"
                else:
                    side = "L"

                fbf_linear = cmds.createNode("fourByFourMatrix", name=f"{side}_{part}LipLinear_FBF", ss=True)
                cps_nurbs = cmds.createNode("closestPointOnSurface", name=f"{side}_{part}Lip_CPS", ss=True)
                fbf_nurbs = cmds.createNode("fourByFourMatrix", name=f"{side}_{part}LipNurbs_FBF", ss=True)
                parent_matrix_blender = cmds.createNode("parentMatrix", name=f"{side}_{part}LipBlend_PMX", ss=True)
                cmds.connectAttr(f"{nurbs}.worldSpace[0]", f"{cps_nurbs}.inputSurface")
                cmds.connectAttr(f"{nurbs}.cv[{index}]", f"{cps_nurbs}.inPosition")
                cmds.connectAttr(f"{cps_nurbs}.positionX", f"{fbf_nurbs}.in30")
                cmds.connectAttr(f"{cps_nurbs}.positionY", f"{fbf_nurbs}.in31")
                cmds.connectAttr(f"{cps_nurbs}.positionZ", f"{fbf_nurbs}.in32")
                cmds.connectAttr(f"{linear_curve}.editPoints[{index}].xValueEp", f"{fbf_linear}.in30")
                cmds.connectAttr(f"{linear_curve}.editPoints[{index}].yValueEp", f"{fbf_linear}.in31")
                cmds.connectAttr(f"{linear_curve}.editPoints[{index}].zValueEp", f"{fbf_linear}.in32")
                cmds.connectAttr(f"{fbf_linear}.output", f"{parent_matrix_blender}.inputMatrix")
                cmds.connectAttr(f"{fbf_nurbs}.output", f"{parent_matrix_blender}.target[0].targetMatrix")
                
                out_joint = cmds.createNode("joint", name=f"{side}_{part}Lip{str(index).zfill(2)}Skinning_JNT", ss=True, parent=self.skeleton_grp)
                cmds.connectAttr(f"{fbf_linear}.output", f"{out_joint}.offsetParentMatrix")


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