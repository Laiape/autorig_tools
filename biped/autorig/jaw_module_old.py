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

class JawModuleOld(object):

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
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

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

    def local(self, ctl, joint=False):

        """
        Create a local transform node for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            str: The name of the local transform node.
        """

        local_grp = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_GRP"), ss=True, p=self.module_trn)
        local_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=local_grp)
        if joint == True:
            local_jnt = cmds.createNode("joint", name=ctl.replace("_CTL", "Local_JNT"), ss=True, p=local_trn)
        cmds.matchTransform(local_grp, ctl)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_trn}.offsetParentMatrix")
        
        return (local_grp, local_trn, local_jnt) if joint else (local_grp, local_trn, None)
    
    def load_guides(self):

        """
        Load the guide positions for the jaw module.
        Returns:
            dict: A dictionary containing the guide positions.
        """

        self.jaw_guides = guides_manager.get_guides("C_jaw_JNT") # Jaw father, l_jaw_JNT, r_jaw_JNT and c_chin_JNT

        for guide in self.jaw_guides:
            cmds.parent(guide, self.module_trn)

    def create_controllers(self):
        
        """
        Create the controllers for the jaw module.  
        """
    

        self.jaw_nodes, self.jaw_ctl = curve_tool.create_controller("C_jaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.matchTransform(self.jaw_nodes[0], self.jaw_guides[0], pos=True) # Only position
        self.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])
        self.jaw_guide = cmds.createNode("transform", name="C_jaw_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.jaw_guide, self.jaw_guides[0], pos=True) # Only position

        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.matchTransform(self.upper_jaw_nodes[0], self.jaw_guides[0], pos=True) # Only position
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

        num_cvs = cmds.getAttr(f"{self.upper_linear_lip_curve}.spans") + cmds.getAttr(f"{self.upper_linear_lip_curve}.degree")

        # Create master mouth controller
        self.mouth_master_nodes, self.mouth_master_ctl = curve_tool.create_controller("C_mouthMaster", offset=["GRP"], parent=self.controllers_grp) # Doesnt follow jaws
        self.lock_attributes(self.mouth_master_ctl, ["v"])
        mouth_master_local_grp, mouth_master_local_trn, mouth_master_local_jnt = self.local(self.mouth_master_ctl)
        cmds.matchTransform(self.mouth_master_nodes[0], self.jaw_ctl, pos=True) # Only position

        # Create NURBS surface
        distance = cmds.getAttr(f"{radius_loc}.translateX")
        self.sphere = guides_manager.get_guides("C_jaw_NURBShape", parent=self.module_trn) # NURBS surface guide
        cmds.hide(self.sphere)
        cmds.rotate(0, 90, 0, self.sphere, relative=True, objectSpace=True)
        cmds.setAttr(f"{radius_loc}.translateX", 0)
        # cmds.matchTransform(self.sphere, radius_loc)
        self.sphere_guide = cmds.createNode("transform", name="C_jawSlideGuide_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.sphere_guide, radius_loc)
        cmds.delete(radius_loc)

        jaw_local_grp, jaw_local_trn, self.jaw_local_joint = self.local(self.jaw_ctl, joint=True)
        upper_jaw_local_grp, upper_jaw_local_trn, self.upper_jaw_local_joint = self.local(self.upper_jaw_ctl, joint=True)
        upper_jaw_local_mult_matrix = cmds.createNode("multMatrix", n=f"{self.side}_localUpperJaw_MMX", ss=True)
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{upper_jaw_local_mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{upper_jaw_local_mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{upper_jaw_local_mult_matrix}.matrixSum", f"{upper_jaw_local_trn}.offsetParentMatrix", f=True)

        # Create constraints to upper and lower jaws
        jaw_nurbs_skin_cluster = cmds.skinCluster(
                self.sphere,
                self.jaw_local_joint,
                self.upper_jaw_local_joint,
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
                    (self.jaw_local_joint, jaw_w),
                    (self.upper_jaw_local_joint, upper_w)
                ])
        

        # Create upper and lower lip corner controllers
        self.upper_lip_nodes, self.upper_lip_ctl = curve_tool.create_controller("C_upperLip", offset=["GRP"], parent=self.mouth_master_ctl) # Main upper lip controller
        self.lock_attributes(self.upper_lip_ctl, ["v"])

        self.upper_local_joints = []
        self.lower_local_joints = []

        # Local setup for upper lip controller
        self.upper_local_grp, self.upper_local_trn, self.upper_local_jnt = self.local(self.upper_lip_ctl, joint=True)
        mult_matrix_upper_local = cmds.createNode("multMatrix", name="C_upperLipLocal_MMX", ss=True)
        cmds.connectAttr(f"{self.upper_lip_ctl}.matrix", f"{mult_matrix_upper_local}.matrixIn[0]")
        cmds.connectAttr(f"{upper_jaw_local_mult_matrix}.matrixSum", f"{mult_matrix_upper_local}.matrixIn[1]")
        cmds.connectAttr(f"{self.mouth_master_ctl}.matrix", f"{mult_matrix_upper_local}.matrixIn[2]") # Consider mouth master movement
        cmds.connectAttr(f"{mult_matrix_upper_local}.matrixSum", f"{self.upper_local_trn}.offsetParentMatrix", f=True) # Local transform for the upper lip controller
        

        # Place upper lip controller
        four_by_four_upper_main = cmds.createNode("fourByFourMatrix", name="C_upperLip_FBF", ss=True)
        cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{num_cvs//2 - 1}].xValueEp", f"{four_by_four_upper_main}.in30")
        cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{num_cvs//2 - 1}].yValueEp", f"{four_by_four_upper_main}.in31")
        cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{num_cvs//2 - 1}].zValueEp", f"{four_by_four_upper_main}.in32")
        mult_matrix_negate_master_upper_main = cmds.createNode("multMatrix", name="C_upperLipNegateMaster_MMX", ss=True)
        cmds.connectAttr(f"{four_by_four_upper_main}.output", f"{mult_matrix_negate_master_upper_main}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master_upper_main}.matrixIn[1]") # Negate the position of the master mouth controller
        cmds.connectAttr(f"{upper_jaw_local_mult_matrix}.matrixSum", f"{mult_matrix_negate_master_upper_main}.matrixIn[2]") # Consider upper jaw movement
        cmds.connectAttr(f"{mult_matrix_negate_master_upper_main}.matrixSum", f"{self.upper_lip_nodes[0]}.offsetParentMatrix") # Connect the output to the upper lip controller
        cmds.xform(self.upper_lip_nodes[0], m=om.MMatrix.kIdentity)

        # Create lower lip controller
        self.lower_lip_nodes, self.lower_lip_ctl = curve_tool.create_controller("C_lowerLip", offset=["GRP"], parent=self.mouth_master_ctl) # Main lower lip controller
        self.lock_attributes(self.lower_lip_ctl, ["v"])
        
        # Local setup for lower lip controller
        self.lower_local_grp, self.lower_local_trn, self.lower_local_jnt = self.local(self.lower_lip_ctl, joint=True)
        mult_matrix_lower_local = cmds.createNode("multMatrix", name="C_lowerLipLocal_MMX", ss=True)
        cmds.connectAttr(f"{self.lower_lip_ctl}.matrix", f"{mult_matrix_lower_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{mult_matrix_lower_local}.matrixIn[1]")
        cmds.connectAttr(f"{self.mouth_master_ctl}.matrix", f"{mult_matrix_lower_local}.matrixIn[2]") # Consider mouth master movement
        cmds.connectAttr(f"{mult_matrix_lower_local}.matrixSum", f"{self.lower_local_trn}.offsetParentMatrix", f=True) # Local transform for the lower lip controller

        # Place lower lip controller
        four_by_four_lower_main = cmds.createNode("fourByFourMatrix", name="C_lowerLip_FBF", ss=True)
        cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{math.floor(num_cvs/2)}].xValueEp", f"{four_by_four_lower_main}.in30")
        cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{math.floor(num_cvs/2)}].yValueEp", f"{four_by_four_lower_main}.in31")
        cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{math.floor(num_cvs/2)}].zValueEp", f"{four_by_four_lower_main}.in32")
        mult_matrix_negate_master_lower_main = cmds.createNode("multMatrix", name="C_lowerLipNegateMaster_MMX", ss=True)
        cmds.connectAttr(f"{four_by_four_lower_main}.output", f"{mult_matrix_negate_master_lower_main}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master_lower_main}.matrixIn[1]") # Negate the position of the master mouth controller
        cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{mult_matrix_negate_master_lower_main}.matrixIn[2]") # Consider lower jaw movement
        cmds.connectAttr(f"{mult_matrix_negate_master_lower_main}.matrixSum", f"{self.lower_lip_nodes[0]}.offsetParentMatrix") # Connect the output to the lower lip controller
        cmds.xform(self.lower_lip_nodes[0], m=om.MMatrix.kIdentity)

        corner_guide = cmds.createNode("transform", name=f"C_lipCorner_GUIDE", ss=True, p=self.module_trn)

        # Create lip corner controllers
        for side in ["L", "R"]:
            # Create corner lip controller
            self.main_corner_nodes, self.main_corner_ctl = curve_tool.create_controller(f"{side}_lipMainCorner", offset=["GRP"], parent=self.mouth_master_ctl) # Corner controller. Will drive secondary corner controller

    
            self.lock_attributes(self.main_corner_ctl, ["rx", "ry", "rz", "sx", "sz", "v"])
            cmds.addAttr(self.main_corner_ctl, ln="EXTRA_ATTRIBUTES", at="enum", en="____", k=True)
            cmds.setAttr(f"{self.main_corner_ctl}.EXTRA_ATTRIBUTES", lock=True, keyable=False, channelBox=True)
            cmds.addAttr(self.main_corner_ctl, ln="Corner_Blend", at="float", min=0, max=1, dv=0.5, k=True)


            four_by_four_upper = cmds.createNode("fourByFourMatrix", name=f"{side}_upperLipCorner_FBF", ss=True)
            four_by_four_lower = cmds.createNode("fourByFourMatrix", name=f"{side}_lowerLipCorner_FBF", ss=True)
            corner_blend_matrix = cmds.createNode("blendMatrix", name=f"{side}_lipCorner_BLM", ss=True)
            cmds.connectAttr(f"{four_by_four_upper}.output", f"{corner_blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{four_by_four_lower}.output", f"{corner_blend_matrix}.target[0].targetMatrix")
            jaws_blend_matrix = cmds.createNode("blendMatrix", name=f"{side}_lipCornerJaws_BLM", ss=True) # Blend between upper and lower jaw influence
            cmds.connectAttr(f"{self.upper_jaw_ctl}.matrix", f"{jaws_blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{jaws_blend_matrix}.target[0].targetMatrix")

            main_local_corner_jnt = cmds.createNode("joint", name=f"{side}_lipCornerLocal_JNT", ss=True, p=self.module_trn)
            self.upper_local_joints.append(main_local_corner_jnt)
            self.lower_local_joints.append(main_local_corner_jnt)
            if side == "L":
                self.upper_local_joints.append(self.upper_local_jnt)
                self.lower_local_joints.append(self.lower_local_jnt)
            

            if side == "R":
                cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{0}].xValueEp", f"{four_by_four_upper}.in30")
                cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{0}].yValueEp", f"{four_by_four_upper}.in31")
                cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{0}].zValueEp", f"{four_by_four_upper}.in32")

                cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{0}].xValueEp", f"{four_by_four_lower}.in30")
                cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{0}].yValueEp", f"{four_by_four_lower}.in31")
                cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{0}].zValueEp", f"{four_by_four_lower}.in32")

            elif side == "L":
                cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{num_cvs-1}].xValueEp", f"{four_by_four_upper}.in30")
                cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{num_cvs-1}].yValueEp", f"{four_by_four_upper}.in31")
                cmds.connectAttr(f"{self.upper_linear_lip_curve}.editPoints[{num_cvs-1}].zValueEp", f"{four_by_four_upper}.in32")


                cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{num_cvs-1}].xValueEp", f"{four_by_four_lower}.in30")
                cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{num_cvs-1}].yValueEp", f"{four_by_four_lower}.in31")
                cmds.connectAttr(f"{self.lower_linear_lip_curve}.editPoints[{num_cvs-1}].zValueEp", f"{four_by_four_lower}.in32")


            
            cmds.connectAttr(f"{self.main_corner_ctl}.Corner_Blend", f"{jaws_blend_matrix}.envelope") # Blend attribute from main corner controller
            mult_matrix_negate_master = cmds.createNode("multMatrix", name=f"{side}_lipCornerNegateMaster_MMX", ss=True)
            cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master}.matrixIn[1]") # Negate the position of the master mouth controller
            cmds.connectAttr(f"{corner_blend_matrix}.outputMatrix", f"{mult_matrix_negate_master}.matrixIn[0]")
            cmds.connectAttr(f"{jaws_blend_matrix}.outputMatrix", f"{mult_matrix_negate_master}.matrixIn[2]") # Consider jaw movements
            aim_matrix = cmds.createNode("aimMatrix", name=f"{side}_lipCorner_AIM", ss=True)
            if side == "L":
                cmds.setAttr(f"{aim_matrix}.primaryInputAxis", 0, 0, -1, type="double3") # Aim down negative Z
            else:
                cmds.setAttr(f"{aim_matrix}.primaryInputAxis", 0, 0, 1, type="double3") # Aim down positive Z
                cmds.connectAttr(f"{self.upper_lip_nodes[0]}.matrix", f"{aim_matrix}.secondaryTargetMatrix") # Aim towards mouth master controller
                cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", -1, 0, 0, type="double3")
                cmds.setAttr(f"{aim_matrix}.secondaryTargetVector", 1, 0, 0, type="double3")
                cmds.setAttr(f"{aim_matrix}.secondaryMode", 1) 

            cmds.connectAttr(f"{mult_matrix_negate_master}.matrixSum", f"{aim_matrix}.inputMatrix")
            cmds.connectAttr(f"{self.upper_lip_nodes[0]}.matrix", f"{aim_matrix}.primaryTargetMatrix") # Aim towards mouth master controller
            cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{self.main_corner_nodes[0]}.offsetParentMatrix") # Connect the output to the corner local transform
            cmds.xform(self.main_corner_nodes[0], m=om.MMatrix.kIdentity)
            
            # Create follicles for the corners
            row_matrix_corner = cmds.createNode("rowFromMatrix", name=f"{side}_lipCorner_RFM", ss=True)
            cmds.setAttr(f"{row_matrix_corner}.input", 3) # Translation row
            
            mult_matrix_corner_position = cmds.createNode("multMatrix", name=f"{side}_lipCornerPosition_MMX", ss=True)
            if side == "L":
                cmds.matchTransform(corner_guide, self.main_corner_ctl)
            cmds.connectAttr(f"{corner_guide}.worldMatrix[0]", f"{mult_matrix_corner_position}.matrixIn[0]")
            cmds.connectAttr(f"{self.main_corner_ctl}.matrix", f"{mult_matrix_corner_position}.matrixIn[1]")
            cmds.connectAttr(f"{self.mouth_master_ctl}.matrix", f"{mult_matrix_corner_position}.matrixIn[2]") # Consider mouth master movement
            cmds.connectAttr(f"{mult_matrix_corner_position}.matrixSum", f"{row_matrix_corner}.matrix")

            # Closest point on curve for corner
            closest_point_corner = cmds.createNode("closestPointOnSurface", name=f"{side}_lipCorner_CPS", ss=True)
            if side == "R":
                negate_x = cmds.createNode("negate", name=f"{side}_lipCorner_NGT", ss=True)
                cmds.connectAttr(f"{row_matrix_corner}.outputX", f"{negate_x}.input")
                cmds.connectAttr(f"{negate_x}.output", f"{closest_point_corner}.inPositionX")
            else:
                cmds.connectAttr(f"{row_matrix_corner}.outputX", f"{closest_point_corner}.inPositionX")
            cmds.connectAttr(f"{row_matrix_corner}.outputY", f"{closest_point_corner}.inPositionY")
            cmds.connectAttr(f"{row_matrix_corner}.outputZ", f"{closest_point_corner}.inPositionZ")
            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{closest_point_corner}.inputSurface") # Connect the NURBS surface to the closest point node

            
            
            cmds.connectAttr(f"{closest_point_corner}.position", f"{main_local_corner_jnt}.translate") # Connect the closest point position to the corner controller translation
            cmds.matchTransform(main_local_corner_jnt, self.main_corner_ctl, rot=True) # Match rotation
            

        cmds.matchTransform(self.lower_local_grp, self.jaw_guide)
        cmds.matchTransform(self.lower_local_trn, self.lower_lip_ctl)
        cmds.matchTransform(self.upper_local_grp, self.jaw_guide)
        cmds.matchTransform(self.upper_local_trn, self.upper_lip_ctl)
        cmds.matchTransform(mouth_master_local_grp, self.mouth_master_ctl)

        # From the linear curves, create a curve degree 3 with 4 spans
        self.upper_rebuild_lip_curve = cmds.rebuildCurve(self.upper_linear_lip_curve, ch=0, rpo=0, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=6, d=3, tol=0.01, name="C_upperLip_CRV")[0]
        self.lower_rebuild_lip_curve = cmds.rebuildCurve(self.lower_linear_lip_curve, ch=0, rpo=0, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=6, d=3, tol=0.01, name="C_lowerLip_CRV")[0]
        cmds.parent(self.upper_rebuild_lip_curve, self.lower_rebuild_lip_curve, self.module_trn)

        # Skin cluster to local joints
        self.upper_skin_cluster = cmds.skinCluster(self.upper_local_joints, self.upper_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_upperLip_SKIN")[0]
        self.lower_skin_cluster = cmds.skinCluster(self.lower_local_joints, self.lower_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_lowerLip_SKIN")[0]

        
        
        # Refine skin weights
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[0]", tv=[(self.upper_local_joints[-1], 1.0)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[1]", tv=[(self.upper_local_joints[-1], 0.8), (self.upper_local_joints[1], 0.2)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[2]", tv=[(self.upper_local_joints[-1], 0.4), (self.upper_local_joints[1], 0.6)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[3]", tv=[(self.upper_local_joints[-1], 0.2), (self.upper_local_joints[1], 0.8)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[4]", tv=[(self.upper_local_joints[1], 1.0)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[5]", tv=[(self.upper_local_joints[1], 0.8), (self.upper_local_joints[0], 0.2)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[6]", tv=[(self.upper_local_joints[1], 0.6), (self.upper_local_joints[0], 0.4)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[7]", tv=[(self.upper_local_joints[1], 0.2), (self.upper_local_joints[0], 0.8)])
        cmds.skinPercent(self.upper_skin_cluster, f"{self.upper_rebuild_lip_curve}.cv[8]", tv=[(self.upper_local_joints[0], 1.0)])


        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[0]", tv=[(self.lower_local_joints[-1], 1.0)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[1]", tv=[(self.lower_local_joints[-1], 0.8), (self.lower_local_joints[1], 0.2)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[2]", tv=[(self.lower_local_joints[-1], 0.4), (self.lower_local_joints[1], 0.6)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[3]", tv=[(self.lower_local_joints[-1], 0.2), (self.lower_local_joints[1], 0.8)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[4]", tv=[(self.lower_local_joints[1], 1.0)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[5]", tv=[(self.lower_local_joints[1], 0.8), (self.lower_local_joints[0], 0.2)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[6]", tv=[(self.lower_local_joints[1], 0.6), (self.lower_local_joints[0], 0.4)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[7]", tv=[(self.lower_local_joints[1], 0.2), (self.lower_local_joints[0], 0.8)])
        cmds.skinPercent(self.lower_skin_cluster, f"{self.lower_rebuild_lip_curve}.cv[8]", tv=[(self.lower_local_joints[0], 1.0)])


        # Make curve into bezier for better deformation
        # cmds.select(self.upper_rebuild_lip_curve)
        # cmds.nurbsCurveToBezier()
        # self.upper_rebuild_lip_curve = cmds.rename(cmds.ls(sl=True)[0], "C_upperLipBezier_CRV")
        # cmds.select(self.lower_rebuild_lip_curve)
        # cmds.nurbsCurveToBezier()
        # self.lower_rebuild_lip_curve = cmds.rename(cmds.ls(sl=True)[0], "C_lowerLipBezier_CRV")

        # Create motion paths for the extra controllers
        rebuilded_num_cvs = cmds.getAttr(f"{self.upper_rebuild_lip_curve}.spans") + cmds.getAttr(f"{self.upper_rebuild_lip_curve}.degree")
        upper_cvs = [f"{self.upper_rebuild_lip_curve}.cv[{i}]" for i in range(rebuilded_num_cvs)]
        upper_cvs = cmds.ls(upper_cvs, fl=True)
        lower_cvs = [f"{self.lower_rebuild_lip_curve}.cv[{i}]" for i in range(rebuilded_num_cvs)]
        lower_cvs = cmds.ls(lower_cvs, fl=True)

        mid_num = len(upper_cvs) // 2

        upper_local_out_joints = []
        lower_local_out_joints = []
        extra_controllers = []
        for i, cv in enumerate(upper_cvs + lower_cvs):

            cv_pos = cmds.xform(cv, q=True, t=True, ws=True)

            if cv in upper_cvs:
                parameter = self.getClosestParamToPosition(self.upper_rebuild_lip_curve, cv_pos) # Get the closest parameter on the curve to the CV position
            else:
                parameter = self.getClosestParamToPosition(self.lower_rebuild_lip_curve, cv_pos) # Get the closest parameter on the curve to the CV position

            mtp = cmds.createNode("motionPath", name=f"C_upperLipExtra_{i}_MTP", ss=True)
            cmds.setAttr(f"{mtp}.uValue", parameter)
            cmds.setAttr(f"{mtp}.fractionMode", 1)

            if i < len(upper_cvs) // 2 or (i >= len(upper_cvs) and i < len(upper_cvs) + len(lower_cvs) // 2):
                cmds.setAttr(f"{mtp}.frontAxis", 0) # X axis
                cmds.setAttr(f"{mtp}.upAxis", 1)    # Y axis
                cmds.setAttr(f"{mtp}.worldUpType", 4) # Object up
                cmds.setAttr(f"{mtp}.inverseFront", 1)
            if cv in upper_cvs:
                cmds.connectAttr(f"{self.upper_rebuild_lip_curve}.worldSpace[0]", f"{mtp}.geometryPath")
            else:
                cmds.connectAttr(f"{self.lower_rebuild_lip_curve}.worldSpace[0]", f"{mtp}.geometryPath")
            four_by_four_matrix = cmds.createNode("fourByFourMatrix", name=f"C_upperLipExtra0{i}_FBF", ss=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.xCoordinate", f"{four_by_four_matrix}.in30")
            cmds.connectAttr(f"{mtp}.allCoordinates.yCoordinate", f"{four_by_four_matrix}.in31")
            cmds.connectAttr(f"{mtp}.allCoordinates.zCoordinate", f"{four_by_four_matrix}.in32")

            for j in range(3):
                row_from_matrix = cmds.createNode("rowFromMatrix", name=f"C_upperLipExtra0{i}_RFM", ss=True)
                cmds.setAttr(f"{row_from_matrix}.input", j)
                if cv in upper_cvs:
                    cmds.connectAttr(f"{self.upper_jaw_ctl}.matrix", f"{row_from_matrix}.matrix")
                else:
                    cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{row_from_matrix}.matrix")


            if cv in lower_cvs:
                extra_nodes, extra_controller = curve_tool.create_controller(f"C_lowerLip0{i-len(lower_cvs)}", offset=["GRP"], parent=self.mouth_master_ctl)
                self.lock_attributes(extra_controller, ["sx", "sy", "sz", "rx", "ry", "rz", "v"])
                local_grp, local_trn, local_jnt = self.local(extra_controller, joint=True)
                cmds.matchTransform(local_grp, extra_nodes[0])
                lower_local_out_joints.append(local_jnt)
            else:
                extra_nodes, extra_controller = curve_tool.create_controller(f"C_upperLip0{i}", offset=["GRP"], parent=self.mouth_master_ctl)
                self.lock_attributes(extra_controller, ["sx", "sy", "sz", "rx", "ry", "rz", "v"])
                local_grp, local_trn, local_jnt = self.local(extra_controller, joint=True)
                cmds.matchTransform(local_grp, extra_nodes[0])
                upper_local_out_joints.append(local_jnt)


            mult_matrix = cmds.createNode("multMatrix", name=f"C_lipExtra0{i}_MMX", ss=True)
            cmds.connectAttr(f"{four_by_four_matrix}.output", f"{mult_matrix}.matrixIn[0]")
            cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]") # Negate the position of the master mouth controller
            cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{extra_nodes[0]}.offsetParentMatrix")
            cmds.xform(extra_nodes[0], m=om.MMatrix.kIdentity)



            if i < mid_num or i > len(upper_cvs) and i < len(upper_cvs) + mid_num:
                cmds.rotate(0, 180, 0, extra_nodes[0], relative=True, objectSpace=True)

            mult_matrix_local = cmds.createNode("multMatrix", name=f"C_lipExtra0{i}Local_MMX", ss=True)
            cmds.connectAttr(f"{extra_controller}.matrix", f"{mult_matrix_local}.matrixIn[0]")
            cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{mult_matrix_local}.matrixIn[1]")
            cmds.connectAttr(f"{mult_matrix_local}.matrixSum", f"{local_trn}.offsetParentMatrix", f=True)

            cmds.matchTransform(local_grp, self.jaw_guide)
            cmds.matchTransform(local_trn, extra_controller)


        upper_out_curve = cmds.duplicate(self.upper_linear_lip_curve, name="C_upperLipOut_CRV")[0]
        lower_out_curve = cmds.duplicate(self.lower_linear_lip_curve, name="C_lowerLipOut_CRV")[0]

        self.upper_out_skin_cluster = cmds.skinCluster(upper_local_out_joints, upper_out_curve, toSelectedBones=True, bindMethod=0, skinMethod=0,name="C_upperLipOut_SKIN")[0]
        self.lower_out_skin_cluster = cmds.skinCluster(lower_local_out_joints, lower_out_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, name="C_lowerLipOut_SKIN")[0]

        
        extra_controllers_node = cmds.createNode("transform", name="C_lipExtraControllers_GRP", ss=True, p=self.mouth_master_ctl)

        cmds.addAttr(self.mouth_master_ctl, ln="EXTRA_ATTRIBUTES", at="enum", en="____", k=True)
        cmds.setAttr(f"{self.mouth_master_ctl}.EXTRA_ATTRIBUTES", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.mouth_master_ctl, ln="Extra_Controllers_Visibility", at="bool", dv=1, k=True)
        cmds.setAttr(f"{self.mouth_master_ctl}.Extra_Controllers_Visibility", keyable=False, channelBox=True)
        cmds.connectAttr(f"{self.mouth_master_ctl}.Extra_Controllers_Visibility", f"{extra_controllers_node}.visibility")

        upper_linnear_cvs = [f"{upper_out_curve}.cv[{i}]" for i in range(num_cvs)]
        upper_linnear_cvs = cmds.ls(upper_linnear_cvs, fl=True)
        lower_linnear_cvs = [f"{lower_out_curve}.cv[{i}]" for i in range(num_cvs)]
        lower_linnear_cvs = cmds.ls(lower_linnear_cvs, fl=True)

        out_mid_num = len(upper_linnear_cvs) // 2
        
        for i, cv in enumerate(upper_linnear_cvs + lower_linnear_cvs):
            
            if cv in upper_linnear_cvs:
                name = "upper"
                j = i
            else:
                name = "lower"
                j = i - len(upper_linnear_cvs)
            mtp = cmds.createNode("motionPath", name=f"C_{name}LipOut0{j}_MTP", ss=True)
            
            if cv in upper_linnear_cvs:
                parameter = self.getClosestParamToPosition(upper_out_curve, cmds.xform(cv, q=True, t=True, ws=True)) # Get the closest parameter on the curve to the CV position
                cmds.connectAttr(f"{upper_out_curve}.worldSpace[0]", f"{mtp}.geometryPath")
            else:
                parameter = self.getClosestParamToPosition(lower_out_curve, cmds.xform(cv, q=True, t=True, ws=True)) # Get the closest parameter on the curve to the CV position
                cmds.connectAttr(f"{lower_out_curve}.worldSpace[0]", f"{mtp}.geometryPath")
            
                
            cmds.setAttr(f"{mtp}.uValue", parameter)
            cmds.setAttr(f"{mtp}.fractionMode", 0)

            # four_by_four_out = cmds.createNode("fourByFourMatrix", name=f"C_{name}LipOut0{j}_FBF", ss=True)
            # cmds.connectAttr(f"{mtp}.allCoordinates.xCoordinate", f"{four_by_four_out}.in30")
            # cmds.connectAttr(f"{mtp}.allCoordinates.yCoordinate", f"{four_by_four_out}.in31")
            # cmds.connectAttr(f"{mtp}.allCoordinates.zCoordinate", f"{four_by_four_out}.in32")

            # out_nodes, out_controller = curve_tool.create_controller(f"C_{name}LipOut0{j}", offset=["GRP"], parent=extra_controllers_node)
            # self.lock_attributes(out_controller, ["sx", "sy", "sz", "rx", "ry", "rz", "v"])

            # mult_matrix_negate_master_out = cmds.createNode("multMatrix", name=f"C_{name}LipOut0{j}NegateMaster_MMX", ss=True)
            # cmds.connectAttr(f"{four_by_four_out}.output", f"{mult_matrix_negate_master_out}.matrixIn[0]")
            # cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master_out}.matrixIn[1]") # Negate the position of the master mouth controller
            # cmds.connectAttr(f"{mult_matrix_negate_master_out}.matrixSum", f"{out_nodes[0]}.offsetParentMatrix")
            # cmds.xform(out_nodes[0], m=om.MMatrix.kIdentity)
    
            out_joint = cmds.createNode("joint", name=f"C_{name}LipOut0{j}_JNT", ss=True, p=self.skel_grp)
            # mult_matrix_out_joint = cmds.createNode("multMatrix", name=f"C_{name}LipOut0{j}_MMX", ss=True)
            # cmds.connectAttr(f"{four_by_four_out}.output", f"{mult_matrix_out_joint}.matrixIn[0]")
            # cmds.connectAttr(f"{out_controller}.matrix", f"{mult_matrix_out_joint}.matrixIn[1]")
            # cmds.connectAttr(f"{mult_matrix_out_joint}.matrixSum", f"{out_joint}.offsetParentMatrix")
            # cmds.xform(out_joint, m=om.MMatrix.kIdentity)
            # if i < out_mid_num or i >= len(upper_linnear_cvs) and i < len(upper_linnear_cvs) + out_mid_num:
            #     cmds.rotate(0, 180, 0, out_nodes[0], relative=True, objectSpace=True)
            #     cmds.rotate(0, 180, 0, out_joint, relative=True, objectSpace=True)

            cmds.connectAttr(f"{mtp}.allCoordinates", f"{out_joint}.translate")



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