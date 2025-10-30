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

    def local(self, ctl):

        """
        Create a local transform node for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            str: The name of the local transform node.
        """

        local_grp = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_GRP"), ss=True, p=self.module_trn)
        local_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=local_grp)
        cmds.matchTransform(local_grp, ctl)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_trn}.offsetParentMatrix")
        
        return local_grp, local_trn
    
    def load_guides(self):

        """
        Load the guide positions for the jaw module.
        Returns:
            dict: A dictionary containing the guide positions.
        """

        self.jaw_guides = guides_manager.get_guides("C_jaw_JNT") # Jaw father, l_jaw_JNT, r_jaw_JNT and c_chin_JNT

        # self.jaw_guides = 
        
        for guide in self.jaw_guides:
            cmds.parent(guide, self.module_trn)

    def create_controllers(self):
        
        """
        Create the controllers for the jaw module.  
        """
    

        self.jaw_nodes, self.jaw_ctl = curve_tool.create_controller("C_jaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.matchTransform(self.jaw_nodes[0], self.jaw_guides[0])
        self.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])
        self.jaw_guide = cmds.createNode("transform", name="C_jaw_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.jaw_guide, self.jaw_guides[0], pos=True) # Only position

        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.matchTransform(self.upper_jaw_nodes[0], self.jaw_guides[0])
        self.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])

        self.chin_nodes, self.chin_ctl = curve_tool.create_controller("C_chin", offset=["GRP", "OFF"], parent=self.jaw_ctl)
        cmds.matchTransform(self.chin_nodes[0], self.jaw_guides[-2])
        self.lock_attributes(self.chin_ctl, ["v"])

        for side in ["L", "R"]:
            self.side_jaw_nodes, self.side_jaw_ctl = curve_tool.create_controller(f"{side}_sideJaw", offset=["GRP", "OFF"], parent=self.jaw_ctl)
            cmds.matchTransform(self.side_jaw_nodes[0], self.jaw_guides[1 if side == "L" else -1])
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
        row_from_matrix_jaw = cmds.createNode("decomposeMatrix", name=f"{self.module_name}_collisionJaw_DCM")
        row_from_matrix_upper_jaw = cmds.createNode("decomposeMatrix", name=f"{self.module_name}_collisionUpperJaw_DCM")

        cmds.connectAttr(f"{self.jaw_ctl}.matrix", f"{row_from_matrix_jaw}.inputMatrix")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.matrix", f"{row_from_matrix_upper_jaw}.inputMatrix")

        plus_minus_jaw = cmds.createNode("plusMinusAverage", name=f"{self.module_name}_collisionJaw_PMA", ss=True)
        cmds.setAttr(f"{plus_minus_jaw}.operation", 2) # Subtraction
        cmds.connectAttr(f"{row_from_matrix_jaw}.outputRotateX", f"{plus_minus_jaw}.input1D[0]")
        cmds.connectAttr(f"{row_from_matrix_upper_jaw}.outputRotateX", f"{plus_minus_jaw}.input1D[1]")

        clamp_jaw = cmds.createNode("clamp", name=f"{self.module_name}_collisionJaw_CLP")
        cmds.setAttr(f"{clamp_jaw}.minR", -360)
        cmds.connectAttr(f"{plus_minus_jaw}.output1D", f"{clamp_jaw}.inputR") # Connect the output of the plusMinusAverage to the input of the clamp node
        cmds.connectAttr(f"{row_from_matrix_upper_jaw}.outputRotateX", f"{clamp_jaw}.maxR") # Connect the output of the rowFromMatrix to the input of the clamp node


        float_constant_0 = cmds.createNode("floatConstant", name=f"{self.module_name}_collisionJaw_FC0")
        cmds.setAttr(f"{float_constant_0}.inFloat", 0)

        attribute_blender = cmds.createNode("blendTwoAttr", name=f"{self.module_name}_collisionJaw_BTA")
        cmds.connectAttr(f"{self.jaw_ctl}.Collision", f"{attribute_blender}.attributesBlender")
        cmds.connectAttr(f"{float_constant_0}.outFloat", f"{attribute_blender}.input[0]")
        cmds.connectAttr(f"{clamp_jaw}.outputR", f"{attribute_blender}.input[1]")
        cmds.connectAttr(f"{attribute_blender}.output", f"{self.upper_jaw_nodes[1]}.rotateX")  # Connect the output of the blendTwoAttr to the rotateX of the upper jaw controller

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
        self.mouth_master_nodes, self.mouth_master_ctl = curve_tool.create_controller("C_mouthMaster", offset=["GRP", "OFF"], parent=self.controllers_grp) # Doesnt follow jaws
        self.lock_attributes(self.mouth_master_ctl, ["v"])
        mouth_master_local_grp, mouth_master_local_trn = self.local(self.mouth_master_ctl)
        cmds.matchTransform(self.mouth_master_nodes[0], self.jaw_ctl, pos=True) # Only position

        # Create NURBS surface
        distance = cmds.getAttr(f"{radius_loc}.translateX")
        self.sphere = cmds.sphere(name="C_jawSlide_NRB", sections=4, startSweep=160, radius=distance)[0]
        cmds.parent(self.sphere, self.module_trn)
        cmds.setAttr(f"{radius_loc}.translateX", 0)
        cmds.matchTransform(self.sphere, radius_loc)
        self.sphere_guide = cmds.createNode("transform", name="C_jawSlideGuide_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.sphere_guide, radius_loc)
        cmds.delete(radius_loc)

        # Create constraints to upper and lower jaws
        nrbs_constraint = cmds.createNode("parentMatrix", name="C_jawSlideUpper_PMA", ss=True)
        cmds.connectAttr(f"{self.sphere_guide}.worldMatrix[0]", f"{nrbs_constraint}.inputMatrix") # Use the locator as input guide
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{nrbs_constraint}.target[0].targetMatrix") # Use the upper jaw controller as target
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{nrbs_constraint}.target[1].targetMatrix") # Use the jaw controller as target
        cmds.connectAttr(f"{nrbs_constraint}.outputMatrix", f"{self.sphere}.offsetParentMatrix") # Connect the output to the sphere world matrix
        cmds.setAttr(f"{nrbs_constraint}.target[0].offsetMatrix", self.get_offset_matrix(self.sphere_guide, self.upper_jaw_ctl), type="matrix")
        cmds.setAttr(f"{nrbs_constraint}.target[1].offsetMatrix", self.get_offset_matrix(self.sphere_guide, self.jaw_ctl), type="matrix")

        for side in ["L", "R"]:
            # Create corner lip controller
            self.main_corner_nodes, self.main_corner_ctl = curve_tool.create_controller(f"{side}_lipMainCorner", offset=["GRP", "OFF"], parent=self.mouth_master_ctl) # Corner controller. Will drive secondary corner controller
            self.lock_attributes(self.main_corner_ctl, ["rx", "ry", "rz", "sx", "sz", "v"])
            self.corner_nodes, self.corner_ctl = curve_tool.create_controller(f"{side}_lipCorner", offset=["GRP", "OFF"], parent=self.main_corner_ctl) # Secondary corner controller drived by the main corner but without constraints to other controllers
            corner_local_grp, corner_local_trn = self.local(self.corner_ctl) # Local transform for the corner controller
            four_by_four_upper = cmds.createNode("fourByFourMatrix", name=f"{side}_upperLipCorner_FBF", ss=True)
            four_by_four_lower = cmds.createNode("fourByFourMatrix", name=f"{side}_lowerLipCorner_FBF", ss=True)

            upper_corner_nodes, upper_corner_ctl = curve_tool.create_controller(f"{side}_upperLipCorner", offset=["GRP", "OFF"], parent=self.mouth_master_ctl)
            mult_matrix_negate_master_upper = cmds.createNode("multMatrix", name=f"{side}_upperLipCornerNegateMaster_MMX", ss=True)
            cmds.connectAttr(f"{four_by_four_upper}.output", f"{mult_matrix_negate_master_upper}.matrixIn[0]")
            cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master_upper}.matrixIn[1]") # Negate the position of the master mouth controller
            cmds.connectAttr(f"{mult_matrix_negate_master_upper}.matrixSum", f"{upper_corner_nodes[0]}.offsetParentMatrix") # Connect the output to the corner controller
            

            lower_corner_nodes, lower_corner_ctl = curve_tool.create_controller(f"{side}_lowerLipCorner", offset=["GRP", "OFF"], parent=self.mouth_master_ctl)
            mult_matrix_negate_master_lower = cmds.createNode("multMatrix", name=f"{side}_lowerLipCornerNegateMaster_MMX", ss=True)
            cmds.connectAttr(f"{four_by_four_lower}.output", f"{mult_matrix_negate_master_lower}.matrixIn[0]")
            cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master_lower}.matrixIn[1]") # Negate the position of the master mouth controller
            cmds.connectAttr(f"{mult_matrix_negate_master_lower}.matrixSum", f"{lower_corner_nodes[0]}.offsetParentMatrix") # Connect the output to the corner controller

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


            corner_blend_matrix = cmds.createNode("blendMatrix", name=f"{side}_lipCorner_BLM", ss=True) # Blend between upper and lower lip corners
            cmds.connectAttr(f"{four_by_four_upper}.output", f"{corner_blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{four_by_four_lower}.output", f"{corner_blend_matrix}.target[0].targetMatrix")
            mult_matrix_negate_master = cmds.createNode("multMatrix", name=f"{side}_lipCornerNegateMaster_MMX", ss=True)
            cmds.connectAttr(f"{self.jaw_guide}.worldInverseMatrix[0]", f"{mult_matrix_negate_master}.matrixIn[1]") # Negate the position of the master mouth controller
            cmds.connectAttr(f"{corner_blend_matrix}.outputMatrix", f"{mult_matrix_negate_master}.matrixIn[0]")
            cmds.connectAttr(f"{mult_matrix_negate_master}.matrixSum", f"{self.main_corner_nodes[0]}.offsetParentMatrix") # Connect the output to the corner local transform
            cmds.xform(self.main_corner_nodes[0], m=om.MMatrix.kIdentity)

            cmds.matchTransform(upper_corner_nodes[0], self.main_corner_ctl, pos=True)
            cmds.matchTransform(lower_corner_nodes[0], self.main_corner_ctl, pos=True)

            # Create follicles for the corners
            row_matrix_corner = cmds.createNode("rowFromMatrix", name=f"{self.side}_lipCorner_RFM", ss=True)
            cmds.setAttr(f"{row_matrix_corner}.input", 3) # Translation row
            cmds.connectAttr(f"{corner_local_trn}.worldMatrix[0]", f"{row_matrix_corner}.matrix")

            # Closest point on curve for corner
            closest_point_corner = cmds.createNode("closestPointOnSurface", name=f"{self.side}_lipCorner_CPS", ss=True)
            cmds.connectAttr(f"{row_matrix_corner}.outputX", f"{closest_point_corner}.inPositionX")
            cmds.connectAttr(f"{row_matrix_corner}.outputY", f"{closest_point_corner}.inPositionY")
            cmds.connectAttr(f"{row_matrix_corner}.outputZ", f"{closest_point_corner}.inPositionZ")
            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{closest_point_corner}.inputSurface") # Connect the NURBS surface to the closest point node

            if self.side == "R": # Scale controllers in -Z
                cmds.setAttr(f"{self.main_corner_nodes[1]}.scaleZ", -1)
                cmds.setAttr(f"{self.corner_nodes[1]}.scaleZ", -1)
                cmds.setAttr(f"{upper_corner_nodes[1]}.scaleZ", -1)
                cmds.setAttr(f"{lower_corner_nodes[1]}.scaleZ", -1)




        # From the linear curves, create a curve degree 3 with 4 spans
        # self.upper_rebuild_lip_curve = cmds.rebuildCurve(self.upper_linear_lip_curve, ch=0, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=6, d=3, tol=0.01, name="C_upperLip_CRV")
        # self.lower_rebuild_lip_curve = cmds.rebuildCurve(self.lower_linear_lip_curve, ch=0, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=6, d=3, tol=0.01, name="C_lowerLip_CRV")

        # # Curves to beziers
        # cmds.select(self.upper_rebuild_lip_curve)
        # cmds.nurbsCurveToBezier()

    
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