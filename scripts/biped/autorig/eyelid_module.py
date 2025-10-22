import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from biped.utils import data_manager
from biped.utils import guides_manager
from biped.utils import curve_tool

from biped.autorig.utilities import matrix_manager
from biped.autorig.utilities import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)
reload(ribbon)

class EyelidModule(object):

    def __init__(self):

        """
        Initialize the eyelidModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    def make(self, side):

        """ 
        Create the eyelid module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyelid module.
        Args:
            side (str): The side of the eyelid ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_eyelid"
        if cmds.objExists(f"{self.module_name}Module_GRP"):
            self.module_trn = f"{self.module_name}Module_GRP"
            self.skeleton_grp = f"{self.module_name}Skinning_GRP"
            self.controllers_grp = f"{self.module_name}Controllers_GRP"
            self.local_jnts_grp = f"{self.module_name}LocalJoints_GRP"
            self.curves_grp = f"{self.module_name}Curves_GRP"
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)
            self.local_jnts_grp = cmds.createNode("transform", name=f"{self.module_name}LocalJoints_GRP", ss=True, p=self.module_trn)
            self.curves_grp = cmds.createNode("transform", name=f"{self.module_name}Curves_GRP", ss=True, p=self.module_trn)
        self.extra_controllers_grp = cmds.createNode("transform", name=f"{self.side}_eyelidExtraControllers_GRP", ss=True, p=self.controllers_grp)

        self.create_curves()
        self.load_guides()
        self.curve_cvs_into_guides()
        self.create_main_eye_setup()
        self.create_controllers()
        self.eye_direct()
        self.create_blink_setup()
        self.fleshy_setup()
        self.skinning_joints()

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
        grp = ctl.replace("_CTL", "_GRP")

        if "01" in ctl:
            local_jnt = cmds.createNode("joint", name=ctl.replace("01_CTL", "01Local_JNT"), ss=True, p=self.local_jnts_grp)
            cmds.delete(local_jnt.replace("01Local_JNT", "Local_JNT"))
        else:
            local_jnt = cmds.createNode("joint", name=ctl.replace("_CTL", "Local_JNT"), ss=True, p=self.local_jnts_grp)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_jnt}.offsetParentMatrix")
        # cmds.matchTransform(local_jnt, grp)
        

        return  local_jnt
    
    def create_curves(self):

        """
        Create curves for the blink setup.
        """
        # Get the guide curves
        self.linear_upper_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidUpperLinear_CRVShape", parent=self.curves_grp)
        self.linear_lower_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidLowerLinear_CRVShape", parent=self.curves_grp)
        self.blink_ref_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidBlinkRef_CRVShape")
        self.up_blink_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidUpBlink_CRVShape")
        self.down_blink_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidDownBlink_CRVShape")

        # Rebuild the curves to have proper CV count and degree
        self.eyelid_up_curve = cmds.rebuildCurve(self.linear_upper_curve, n=f"{self.side}_eyelidUp_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, tol=0.01, d=3, s=4)[0]
        self.eyelid_down_curve = cmds.rebuildCurve(self.linear_lower_curve, n=f"{self.side}_eyelidDown_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, tol=0.01, d=3, s=4)[0]
        self.eyelid_up_curve_rebuild = cmds.rebuildCurve(self.eyelid_up_curve, n=f"{self.side}_eyelidUpRebuilded_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=1, kep=1, kt=0, tol=0.01)
        self.eyelid_down_curve_rebuild = cmds.rebuildCurve(self.eyelid_down_curve, n=f"{self.side}_eyelidDownRebuilded_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=1, kep=1, kt=0, tol=0.01)

        cmds.parent(self.eyelid_up_curve, self.eyelid_down_curve, self.blink_ref_curve, self.up_blink_curve, self.down_blink_curve, self.eyelid_up_curve_rebuild,  self.eyelid_down_curve_rebuild, self.curves_grp)

    def load_guides(self):

        """
        Load the guide locators for the eyelid module.
        """
        cmds.select(clear=True)
        self.eye_joint = guides_manager.get_guides(f"{self.side}_eye_JNT", parent=self.module_trn)
        self.eye_guide = cmds.createNode("transform", name=f"{self.side}_eye_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.eye_guide, self.eye_joint[0])
        cmds.delete(self.eye_joint[0])

    def curve_cvs_into_guides(self):

        """
        Convert curve CVs into guides for the eyelid module.
        """

        names = [
            "eyelidIn",
            "eyelidInUp",
            "eyelidUp",
            "eyelidOutUp",
            "eyelidOut",
            "eyelidInDown",
            "eyelidDown",
            "eyelidOutDown"
        ]

        self.guides_matrices = []

        for i, name in enumerate(names):
            if i == 0 or i == len(names) - 1:
                # Must connect in and out with blend matrices to upper and lower curve cvs
                four_by_four_matrix_00 = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}00_FFX", ss=True)
                four_by_four_matrix_01 = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}01_FFX", ss=True)
                cmds.connectAttr(f"{self.eyelid_up_curve_rebuild}.editPoints[{i}].xValueEp", f"{four_by_four_matrix_00}.in30")
                cmds.connectAttr(f"{self.eyelid_up_curve_rebuild}.editPoints[{i}].yValueEp", f"{four_by_four_matrix_00}.in31")
                cmds.connectAttr(f"{self.eyelid_up_curve_rebuild}.editPoints[{i}].zValueEp", f"{four_by_four_matrix_00}.in32")
                cmds.connectAttr(f"{self.eyelid_down_curve_rebuild}.editPoints[{i}].xValueEp", f"{four_by_four_matrix_01}.in30")
                cmds.connectAttr(f"{self.eyelid_down_curve_rebuild}.editPoints[{i}].yValueEp", f"{four_by_four_matrix_01}.in31")
                cmds.connectAttr(f"{self.eyelid_down_curve_rebuild}.editPoints[{i}].zValueEp", f"{four_by_four_matrix_01}.in32")
                blend_matrix = cmds.createNode("blendMatrix", name=f"{self.side}_{name}_BMX", ss=True)
                cmds.connectAttr(f"{four_by_four_matrix_00}.output", f"{blend_matrix}.inputMatrix")
                cmds.connectAttr(f"{four_by_four_matrix_01}.output", f"{blend_matrix}.target[0].targetMatrix")
                cmds.setAttr(f"{blend_matrix}.envelope", 0.5) # Blend equally between upper and lower
            
            
        print(self.guides_matrices)
    def create_main_eye_setup(self):

        """
        Create the main eye setup for the eyelid module.
        """
        self.eye_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_eyeSkinning_JNT", p=self.skeleton_grp)

        if self.side == "L":
            self.main_aim_nodes, self.main_aim_ctl = curve_tool.create_controller(name=f"C_eyeMain", offset=["GRP"])
            cmds.parent(self.main_aim_nodes[0], self.head_ctl)
            self.lock_attributes(self.main_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
            before_translate = cmds.xform(self.eye_guide, q=True, t=True, ws=True)
            cmds.setAttr(f"{self.eye_guide}.tx", 0)
            cmds.matchTransform(self.main_aim_nodes[0], self.eye_guide)
            cmds.select(self.main_aim_nodes[0])
            cmds.move(0, 0, 10, relative=True, objectSpace=True, worldSpaceDistance=True)
            cmds.xform(self.eye_guide, t=before_translate, ws=True)

        side_aim_nodes, self.side_aim_ctl = curve_tool.create_controller(name=f"{self.side}_eye", offset=["GRP"])
        cmds.parent(side_aim_nodes[0], self.controllers_grp)
        cmds.matchTransform(side_aim_nodes[0], self.eye_guide)
        cmds.select(side_aim_nodes[0])
        cmds.move(0, 0, 10, relative=True, objectSpace=True, worldSpaceDistance=True)
        self.lock_attributes(self.side_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
        cmds.parent(side_aim_nodes[0], "C_eyeMain_CTL")

        # Aim setup
        self.eye_jnt_matrix = cmds.xform(self.eye_guide, q=True, m=True, ws=True)
        self.aim = cmds.createNode("aimMatrix", name=f"{self.side}_eye_AIM", ss=True)
        cmds.setAttr(f"{self.aim}.primaryInputAxis", 0, 1, 0)
        cmds.setAttr(f"{self.aim}.secondaryInputAxis", 0, 0, -1)
        cmds.setAttr(f"{self.aim}.secondaryTargetVector", 0, 0, -1)
        cmds.setAttr(f"{self.aim}.secondaryMode", 1) # Aim
        cmds.connectAttr(f"{self.eye_guide}.worldMatrix[0]", f"{self.aim}.inputMatrix")
        cmds.connectAttr(f"{self.side_aim_ctl}.worldMatrix[0]", f"{self.aim}.primaryTargetMatrix")
        cmds.connectAttr(f"{self.head_ctl}.worldMatrix[0]", f"{self.aim}.secondaryTargetMatrix")
        cmds.connectAttr(f"{self.aim}.outputMatrix", f"{self.eye_skinning_jnt}.offsetParentMatrix")

    def create_controllers(self):

        """
        Create controllers for the eyelid module.
        """

        self.upper_local_jnt = []
        self.lower_local_jnt = []

        self.controllers = []
        self.nodes = []

        for i, matrix in enumerate(self.guides_matrices):

            node, ctl = curve_tool.create_controller(name=matrix.replace("_FFX", ""), offset=["GRP"])
            local_jnt = self.local(ctl)
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            
            # if "eyelidIn_" in matrix or "eyelidOut_" in matrix or "eyelidDown_" in matrix or "eyelidUp_" in matrix:
            #     node_01, ctl_01 = curve_tool.create_controller(name=matrix.replace("_FFX", "01"), offset=["GRP"])
            #     local_jnt = self.local(ctl_01)

            #     cmds.parent(node_01, ctl)
            
            if "Up" in matrix:
                self.upper_local_jnt.append(local_jnt)
            elif "Down" in matrix:
                self.lower_local_jnt.append(local_jnt)
            elif "In" not in matrix or "Out" not in matrix:
                self.upper_local_jnt.append(local_jnt)
                self.lower_local_jnt.append(local_jnt)

                    
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])

            cmds.connectAttr(f"{matrix}.output", f"{node[0]}.offsetParentMatrix")
            cmds.parent(node, self.controllers_grp)
            self.controllers.append(ctl)
            self.nodes.append(node[0])
        
        self.upper_guides = [matrix for matrix in self.guides_matrices if "Up" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.lower_guides = [matrix for matrix in self.guides_matrices if "Down" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.upper_nodes = [matrix for matrix in self.nodes if "Up" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.lower_nodes = [matrix for matrix in self.nodes if "Down" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.upper_controllers = [matrix for matrix in self.controllers if "Up" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.lower_controllers = [matrix for matrix in self.controllers if "Down" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]

    
        #Constraints between controllers
        self.constraints_callback(guide=self.upper_guides[1], driven=self.upper_nodes[1], drivers=[self.upper_controllers[2], self.upper_controllers[0]], local_jnt=self.upper_local_jnt[1])
        self.constraints_callback(guide=self.upper_guides[-2], driven=self.upper_nodes[-2], drivers=[self.upper_controllers[2], self.upper_controllers[-1]] , local_jnt=self.upper_local_jnt[-2])
        self.constraints_callback(guide=self.lower_guides[1], driven=self.lower_nodes[1], drivers=[self.lower_controllers[2], self.lower_controllers[0]], local_jnt=self.lower_local_jnt[1])
        self.constraints_callback(guide=self.lower_guides[-2], driven=self.lower_nodes[-2], drivers=[self.lower_controllers[2], self.lower_controllers[-1]], local_jnt=self.lower_local_jnt[-2])

        for jnt in self.upper_local_jnt + self.lower_local_jnt:
            cmds.matchTransform(jnt, jnt.replace("Local_JNT", "_GRP"))

        self.local_constraints_callback(driven_jnt=self.upper_local_jnt[1], drivers=[self.upper_controllers[2], self.upper_controllers[0]])
        self.local_constraints_callback(driven_jnt=self.upper_local_jnt[-2], drivers=[self.upper_controllers[2], self.upper_controllers[-1]])
        self.local_constraints_callback(driven_jnt=self.lower_local_jnt[1], drivers=[self.lower_controllers[2], self.lower_controllers[0]])
        self.local_constraints_callback(driven_jnt=self.lower_local_jnt[-2], drivers=[self.lower_controllers[2], self.lower_controllers[-1]])



    def eye_direct(self):

        """
        Add custom attributes to the eyelid controllers.
        """

        self.eye_direct_nodes, self.eye_direct_ctl = curve_tool.create_controller(name=f"{self.side}_eyeDirect", offset=["GRP", "OFF"])
        cmds.parent(self.eye_direct_nodes[0], self.head_ctl)
        cmds.matchTransform(self.eye_direct_nodes[0], self.eye_guide)
        self.lock_attributes(self.eye_direct_ctl, ["sx", "sy", "sz", "v"])

        cmds.addAttr(self.eye_direct_ctl, ln="EYE_ATTRIBUTES", at="enum", en="____", k=True)
        cmds.setAttr(f"{self.eye_direct_ctl}.EYE_ATTRIBUTES", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Upper_Blink", at="float", min=-1, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Lower_Blink", at="float", min=-1, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Blink_Height", at="float", min=0, max=1, dv=0.2, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Fleshy", at="float", min=0, max=1, dv=0.1, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Fleshy_Corners", at="float", min=0, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Extra_Controllers", at="float", min=0, max=1, dv=0, k=True)

        # Connect the aim matrix to the eye direct controller and orient constrain the eye joint to it
        cmds.connectAttr(f"{self.aim}.outputMatrix", f"{self.eye_direct_nodes[1]}.offsetParentMatrix")
        cmds.setAttr(f"{self.eye_direct_nodes[1]}.inheritsTransform", 0)

        # Connect visibility of extra controllers
        cmds.connectAttr(f"{self.eye_direct_ctl}.Extra_Controllers", f"{self.extra_controllers_grp}.visibility")
        cmds.connectAttr(f"{self.eye_direct_ctl}.worldMatrix[0]", f"{self.eye_skinning_jnt}.offsetParentMatrix", force=True)

    def create_blink_setup(self):

        """
        Create the blink setup for the eyelid module.
        """

        # Upper Blink
        upper_blink = cmds.blendShape(self.blink_ref_curve, self.eyelid_up_curve , self.up_blink_curve, self.eyelid_up_curve_rebuild, name=f"{self.side}_upperEyelidBlink_BLS")[0] # Blend between blink curve and upper eyelid curve
        clamp_node = cmds.createNode("clamp", name=f"{self.side}_upperBlink_CLMP", ss=True)
        cmds.setAttr(f"{clamp_node}.minR", 0)
        cmds.setAttr(f"{clamp_node}.minG", -1)
        cmds.setAttr(f"{clamp_node}.maxR", 1)
        cmds.setAttr(f"{clamp_node}.maxG", 0)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Upper_Blink", f"{clamp_node}.inputR") # Connect upper blink attribute to clamp
        cmds.connectAttr(f"{self.eye_direct_ctl}.Upper_Blink", f"{clamp_node}.inputG") # Connect upper blink attribute to clamp
        cmds.connectAttr(f"{clamp_node}.outputR", f"{upper_blink}.{self.blink_ref_curve}") # Connect clamp output to blend shape weight [0]
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_upperBlink_REV", ss=True)
        cmds.connectAttr(f"{clamp_node}.outputR", f"{reverse_node}.inputX") # Connect clamp output to reverse
        cmds.connectAttr(f"{reverse_node}.outputX", f"{upper_blink}.{self.eyelid_up_curve}") # Connect reverse output to blend shape weight [1]
        negate_node = cmds.createNode("negate", name=f"{self.side}_upperBlink_NEG", ss=True)
        cmds.connectAttr(f"{clamp_node}.outputG", f"{negate_node}.input") # Connect clamp output to negate
        cmds.connectAttr(f"{negate_node}.output", f"{upper_blink}.{self.up_blink_curve}") # Connect negate output to blend shape weight [2]

        # Lower Blink
        lower_blink = cmds.blendShape(self.blink_ref_curve, self.eyelid_down_curve , self.down_blink_curve, self.eyelid_down_curve_rebuild, name=f"{self.side}_lowerEyelidBlink_BLS")[0] # Blend between blink curve and lower eyelid curve
        clamp_node = cmds.createNode("clamp", name=f"{self.side}_lowerBlink_CLMP", ss=True)
        cmds.setAttr(f"{clamp_node}.minR", 0)
        cmds.setAttr(f"{clamp_node}.minG", -1)
        cmds.setAttr(f"{clamp_node}.maxR", 1)
        cmds.setAttr(f"{clamp_node}.maxG", 0)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Lower_Blink", f"{clamp_node}.inputR") # Connect lower blink attribute to clamp
        cmds.connectAttr(f"{self.eye_direct_ctl}.Lower_Blink", f"{clamp_node}.inputG") # Connect lower blink attribute to clamp
        cmds.connectAttr(f"{clamp_node}.outputR", f"{lower_blink}.{self.blink_ref_curve}") # Connect clamp output to blend shape weight [0]
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_lowerBlink_REV", ss=True)
        cmds.connectAttr(f"{clamp_node}.outputR", f"{reverse_node}.inputX") # Connect clamp output to reverse
        cmds.connectAttr(f"{reverse_node}.outputX", f"{lower_blink}.{self.eyelid_down_curve}") # Connect reverse output to blend shape weight [1]
        negate_node = cmds.createNode("negate", name=f"{self.side}_lowerBlink_NEG", ss=True)
        cmds.connectAttr(f"{clamp_node}.outputG", f"{negate_node}.input") # Connect clamp output to negate
        cmds.connectAttr(f"{negate_node}.output", f"{lower_blink}.{self.down_blink_curve}") # Connect negate output to blend shape weight [2]

        # Blink Height
        blink_blend = cmds.blendShape(self.eyelid_up_curve, self.eyelid_down_curve, self.blink_ref_curve, name=f"{self.side}_eyelidBlink_BLS")[0] # Blend between blink curve and upper eyelid curve
        cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{blink_blend}.{self.eyelid_up_curve}") # Connect upper blink attribute to blend shape weight
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_blinkHeight_REV", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{reverse_node}.inputX") # Connect blink height attribute to reverse
        cmds.connectAttr(f"{reverse_node}.outputX", f"{blink_blend}.{self.eyelid_down_curve}") # Connect reverse output to blend shape weight

        upper_eyelid_curve_skin = cmds.skinCluster(*self.upper_local_jnt, self.eyelid_up_curve_rebuild[0], toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, n=f"{self.side}_upperEyelid_SKIN")[0]
        lower_eyelid_curve_skin = cmds.skinCluster(*self.lower_local_jnt, self.eyelid_down_curve_rebuild[0], toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, n=f"{self.side}_lowerEyelid_SKIN")[0]

        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild[0]}.cv[0]", tv=[(self.upper_local_jnt[0], 1.0)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild[0]}.cv[1]", tv=[(self.upper_local_jnt[1], 1.0)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild[0]}.cv[2]", tv=[(self.upper_local_jnt[2], 1.0)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild[0]}.cv[3]", tv=[(self.upper_local_jnt[3], 1)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild[0]}.cv[4]", tv=[(self.upper_local_jnt[4], 1.0)])

        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild[0]}.cv[0]", tv=[(self.lower_local_jnt[0], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild[0]}.cv[1]", tv=[(self.lower_local_jnt[1], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild[0]}.cv[2]", tv=[(self.lower_local_jnt[2], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild[0]}.cv[3]", tv=[(self.lower_local_jnt[3], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild[0]}.cv[4]", tv=[(self.lower_local_jnt[4], 1.0)])

    def fleshy_setup(self):

        """
        Create the fleshy setup for the eyelid module.
        """
        decompose_matrix = cmds.createNode("decomposeMatrix", name=f"{self.side}_fleshy_DECM", ss=True)
        mult_double_linear = cmds.createNode("multDoubleLinear", name=f"{self.side}_fleshy_MDL", ss=True)
        blend_colors_fleshy = cmds.createNode("blendColors", name=f"{self.side}_fleshy_BLC", ss=True)
        blend_colors_corners = cmds.createNode("blendColors", name=f"{self.side}_fleshyCorners_BLC", ss=True)

        cmds.connectAttr(f"{self.eye_direct_ctl}.matrix", f"{decompose_matrix}.inputMatrix")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Fleshy", f"{mult_double_linear}.input1")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Fleshy_Corners", f"{mult_double_linear}.input2")
        cmds.connectAttr(f"{decompose_matrix}.outputRotateX", f"{blend_colors_fleshy}.color1R")
        cmds.connectAttr(f"{decompose_matrix}.outputRotateY", f"{blend_colors_fleshy}.color1G")
        cmds.connectAttr(f"{decompose_matrix}.outputRotateZ", f"{blend_colors_fleshy}.color1B")
        cmds.connectAttr(f"{decompose_matrix}.outputRotateX", f"{blend_colors_corners}.color1R")
        cmds.connectAttr(f"{decompose_matrix}.outputRotateY", f"{blend_colors_corners}.color1G")
        cmds.connectAttr(f"{decompose_matrix}.outputRotateZ", f"{blend_colors_corners}.color1B")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Fleshy", f"{blend_colors_fleshy}.blender")
        cmds.connectAttr(f"{mult_double_linear}.output", f"{blend_colors_corners}.blender")


        fleshy_nodes = [node for node in self.upper_nodes + self.lower_nodes if "eyelidIn_" in node or "eyelidOut_" in node or "eyelidDown_" in node or "eyelidUp_" in node]

        for i, node in enumerate(fleshy_nodes):

            if cmds.objExists(node.replace("_GRP", "Fleshy_OFF")):
                continue
            else:
                fleshy_offset = cmds.createNode("transform", name=node.replace("_GRP", "Fleshy_OFF"), ss=True, p=self.controllers_grp)
                fleshy_trn = cmds.createNode("transform", name=node.replace("_GRP", "Fleshy_TRN"), ss=True, p=fleshy_offset)
                mult_matrix = cmds.createNode("multMatrix", name=node.replace("_GRP", "_MMT"), ss=True)
                cmds.connectAttr(f"{self.eye_guide}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
                cmds.connectAttr(f"{self.head_ctl}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
                cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{fleshy_offset}.offsetParentMatrix")
                cmds.delete(mult_matrix)
                if cmds.connectionInfo(f"{node.replace('_GRP', '_FFX')}.output", isDestination=True):
                    cmds.disconnectAttr(f"{node.replace('_GRP', '_FFX')}.output", f"{node}.offsetParentMatrix")
                    cmds.connectAttr(f"{node.replace('_GRP', '_FFX')}.output", f"{node}.offsetParentMatrix", force=True)
                cmds.parent(node, fleshy_trn)

                # Fleshy setup
                if "Up_" in node or "Down_" in node:
                    cmds.connectAttr(f"{blend_colors_fleshy}.output", f"{fleshy_trn}.rotate")
                    if "Up_" in node:
                        cmds.connectAttr(f"{blend_colors_fleshy}.output", f"{self.upper_local_jnt[i]}.rotate")
                    else:
                        cmds.connectAttr(f"{blend_colors_fleshy}.output", f"{self.lower_local_jnt[i]}.rotate")
                else:
                    cmds.connectAttr(f"{blend_colors_corners}.output", f"{fleshy_trn}.rotate")
                    if "Up" in node:
                        cmds.connectAttr(f"{blend_colors_corners}.output", f"{self.upper_local_jnt[i]}.rotate")
                    else:
                        cmds.connectAttr(f"{blend_colors_corners}.output", f"{self.lower_local_jnt[i]}.rotate")
                
        for jnt in self.upper_local_jnt + self.lower_local_jnt:
            cmds.matchTransform(jnt, jnt.replace("Local_JNT", "_GRP"))

    def skinning_joints(self):
        
        """
        Output the skinning joints for the eyelid module, creating one for each vertex on the upper and lower eyelid curves.
        """

        self.upper_skin_joints = []
        self.lower_skin_joints = []

        upper_cvs = cmds.ls(f"{self.linear_upper_curve}.cv[*]", fl=True)[:-2]
        lower_cvs = cmds.ls(f"{self.linear_lower_curve}.cv[*]", fl=True)[:-2]

        for i, cv in enumerate(upper_cvs + lower_cvs):

            cv_pos = cmds.xform(cv, q=True, t=True, ws=True)

            if cv in upper_cvs:
                name = "upper"
                parameter = self.getClosestParamToPosition(self.eyelid_up_curve_rebuild[0], cv_pos) # Get the closest parameter on the curve to the CV position
            else:
                name = "down"
                parameter = self.getClosestParamToPosition(self.eyelid_down_curve_rebuild[0], cv_pos) # Get the closest parameter on the curve to the CV position

            mtp = cmds.createNode("motionPath", name=f"{self.side}_{name}Eyelid0{i}_MTP", ss=True)
            four_by_four_matrix = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}Eyelid0{i}_F4X4", ss=True)

            cmds.setAttr(f"{mtp}.uValue", parameter) # Set the parameter value
            cmds.setAttr(f"{mtp}.fractionMode", 1) # Disable fraction mode

            if cv in upper_cvs:
                cmds.connectAttr(f"{self.eyelid_up_curve_rebuild[0]}.worldSpace[0]", f"{mtp}.geometryPath")
            else:
                cmds.connectAttr(f"{self.eyelid_down_curve_rebuild[0]}.worldSpace[0]", f"{mtp}.geometryPath")

            cmds.connectAttr(f"{mtp}.allCoordinates.xCoordinate", f"{four_by_four_matrix}.in30", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.yCoordinate", f"{four_by_four_matrix}.in31", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.zCoordinate", f"{four_by_four_matrix}.in32", f=True)

            if self.side == "R":
                float_constant = cmds.createNode("floatConstant", name=f"{self.side}_{name}Eyelid0{i}_FLC", ss=True)
                cmds.setAttr(f"{float_constant}.inFloat", -1) 
                cmds.connectAttr(f"{float_constant}.outFloat", f"{four_by_four_matrix}.in00") # -1 Scale X for mirroring

            parent_matrix = cmds.createNode("parentMatrix", name=f"{self.side}_{name}Eyelid0{i}_PMT", ss=True)
            four_by_four_matrix_origin = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}Eyelid0{i}Origin_F4X4", ss=True)
            if cv in upper_cvs:
                cmds.connectAttr(f"{self.linear_upper_curve}Shape.editPoints[{i}].xValueEp", f"{four_by_four_matrix_origin}.in30", f=True)
                cmds.connectAttr(f"{self.linear_upper_curve}Shape.editPoints[{i}].yValueEp", f"{four_by_four_matrix_origin}.in31", f=True)
                cmds.connectAttr(f"{self.linear_upper_curve}Shape.editPoints[{i}].zValueEp", f"{four_by_four_matrix_origin}.in32", f=True)
            else:
                cmds.connectAttr(f"{self.linear_lower_curve}Shape.editPoints[{i - len(upper_cvs)}].xValueEp", f"{four_by_four_matrix_origin}.in30", f=True)
                cmds.connectAttr(f"{self.linear_lower_curve}Shape.editPoints[{i - len(upper_cvs)}].yValueEp", f"{four_by_four_matrix_origin}.in31", f=True)
                cmds.connectAttr(f"{self.linear_lower_curve}Shape.editPoints[{i - len(upper_cvs)}].zValueEp", f"{four_by_four_matrix_origin}.in32", f=True)

            if self.side == "R":
                cmds.connectAttr(f"{float_constant}.outFloat", f"{four_by_four_matrix_origin}.in00") # -1 Scale X for mirroring

            cmds.connectAttr(f"{four_by_four_matrix_origin}.output", f"{parent_matrix}.inputMatrix") # Connect the four by four matrix to the parent matrix input
            cmds.connectAttr(f"{four_by_four_matrix}.output", f"{parent_matrix}.target[0].targetMatrix") # Connect the origin four by four matrix to the parent matrix target

            aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_{name}Eyelid0{i}_AIM", ss=True)
            cmds.connectAttr(f"{self.eye_guide}.worldMatrix[0]", f"{aim_matrix}.inputMatrix")
            cmds.setAttr(f"{aim_matrix}.primaryInputAxis", 0, 0, 1)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{aim_matrix}.primaryTargetMatrix")
            temp_trn = cmds.createNode("transform", name=f"{self.side}_{name}Eyelid0{i}_TEMP", ss=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{temp_trn}.offsetParentMatrix")
            if "upper" in name:
                skinning_jnt = cmds.createNode("joint", name=f"{self.side}_{name}Eyelid0{i}Skinning_JNT", ss=True, p=self.skeleton_grp)
            if "down" in name:
                skinning_jnt = cmds.createNode("joint", name=f"{self.side}_{name}Eyelid0{i-len(upper_cvs)}Skinning_JNT", ss=True, p=self.skeleton_grp)
            # cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")
            if "upper" in name:
                node, ctl = curve_tool.create_controller(name=f"{self.side}_{name}Eyelid0{i}", offset=["GRP"])
            if "down" in name:
                node, ctl = curve_tool.create_controller(name=f"{self.side}_{name}Eyelid0{i - len(upper_cvs)}", offset=["GRP"])
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{node[0]}.offsetParentMatrix")
            decompose_matrix = cmds.createNode("decomposeMatrix", name=f"{self.side}_{name}Eyelid0{i}_DECM", ss=True)
            cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{decompose_matrix}.inputMatrix")
            cmds.connectAttr(f"{decompose_matrix}.outputRotate", f"{node[0]}.rotate")
            mult_matrix_skin = cmds.createNode("multMatrix", name=f"{self.side}_{name}Eyelid0{i}Skinning_MMT", ss=True)
            cmds.connectAttr(f"{ctl}.matrix", f"{mult_matrix_skin}.matrixIn[0]")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix_skin}.matrixIn[1]")
            cmds.connectAttr(f"{mult_matrix_skin}.matrixSum", f"{skinning_jnt}.offsetParentMatrix")

            # cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")
            # cmds.disconnectAttr(f"{ctl}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")
            # cmds.connectAttr(f"{ctl}.translate", f"{skinning_jnt}.translate")
            # cmds.connectAttr(f"{ctl}.rotate", f"{skinning_jnt}.rotate")
            # cmds.setAttr(f"{node[0]}.inheritsTransform", 0)
            four_by_four_matrix_temp = cmds.createNode("transform", name=f"{self.side}_{name}Eyelid0{i}_F4X4_TEMP", ss=True)
            cmds.connectAttr(f"{four_by_four_matrix_origin}.output", f"{four_by_four_matrix_temp}.offsetParentMatrix") # Connect the four by four matrix to the transform offset parent matrix
            cmds.parent(node[0], self.extra_controllers_grp)
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", self.get_offset_matrix(four_by_four_matrix_temp, temp_trn), type="matrix") # Calculate offset matrix between driven and driver
            cmds.delete(temp_trn)
            cmds.delete(four_by_four_matrix_temp)

        for i, node in enumerate(self.nodes):
            cmds.matchTransform(node, self.locators[i], pos=True, rot=True)
            if "UpIn_" in node or "UpOut_" in node or "DownIn_" in node or "DownOut_" in node:
                cmds.xform(node, m=om.MMatrix.kIdentity)


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


    def constraints_callback(self, guide, driven, drivers=[], local_jnt=None):

        """
        Create a parent constraint between a driven object and multiple driver objects with equal weights.
        Args:
            driven (str): The name of the driven object.
            drivers (list): A list of driver objects.
        """
        driven_ctl = driven.replace("GRP", "CTL")
        suffix = driven.split("_")[-1]
        parent_matrix = cmds.createNode("parentMatrix", name=driven.replace(suffix, "PMT"), ss=True)
        cmds.connectAttr(f"{guide}.output", f"{parent_matrix}.inputMatrix")
        cmds.connectAttr(f"{drivers[0]}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        cmds.connectAttr(f"{drivers[1]}.worldMatrix[0]", f"{parent_matrix}.target[1].targetMatrix")
        cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{driven}.offsetParentMatrix", force=True)
        cmds.setAttr(f"{parent_matrix}.target[0].weight", 0.7) # Up or Down controllers have more influence
        cmds.setAttr(f"{parent_matrix}.target[1].weight", 0.3) # In or Out controllers have less influence

        cmds.setAttr(f"{driven}.inheritsTransform", 0)
        guide_trn_temp = cmds.createNode("transform", name="temp_TRN", ss=True)
        cmds.connectAttr(f"{guide}.output", f"{guide_trn_temp}.offsetParentMatrix")
        cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", self.get_offset_matrix(guide_trn_temp, drivers[0]), type="matrix") # Calculate offset matrix between driven and driver
        cmds.setAttr(f"{parent_matrix}.target[1].offsetMatrix", self.get_offset_matrix(guide_trn_temp, drivers[1]), type="matrix") # Calculate offset matrix between driven and driver
        
        cmds.xform(driven, m=om.MMatrix.kIdentity)
        

        # mult_matrix = cmds.createNode("multMatrix", name=driven.replace(suffix, "MMT"), ss=True)
        # cmds.connectAttr(f"{driven_ctl}.matrix", f"{mult_matrix}.matrixIn[0]")
        # cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[1]")
        # cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{local_jnt}.offsetParentMatrix", force=True)
        # cmds.xform(local_jnt, m=om.MMatrix.kIdentity)
        cmds.delete(guide_trn_temp)

        return parent_matrix
    
    def local_constraints_callback(self, driven_jnt, drivers=[]):

        """
        Create a parent constraint between a driven object and multiple driver objects with equal weights.
        Args:
            driven_jnt (str): The name of the driven object.
            drivers (list): A list of driver objects. Driver[0] == 0.7 weight, Driver[1] == 0.3 weight
        """
        driven_ctl = driven_jnt.replace("Local_JNT", "_CTL")

        row_from_matrix_driver_0 = cmds.createNode("rowFromMatrix", name=drivers[0].replace("CTL", "RFM"), ss=True)
        row_from_matrix_driver_1 = cmds.createNode("rowFromMatrix", name=drivers[1].replace("CTL", "RFM"), ss=True)
        multiply_divide_driver_0 = cmds.createNode("multiplyDivide", name=drivers[0].replace("CTL", "MDV"), ss=True)
        multiply_divide_driver_1 = cmds.createNode("multiplyDivide", name=drivers[1].replace("CTL", "MDV"), ss=True)
        four_by_four_matrix_driver_0 = cmds.createNode("fourByFourMatrix", name=drivers[0].replace("CTL", "F4X4"), ss=True)
        four_by_four_matrix_driver_1 = cmds.createNode("fourByFourMatrix", name=drivers[1].replace("CTL", "F4X4"), ss=True)
        mult_matrix = cmds.createNode("multMatrix", name=driven_jnt.replace("JNT", "MMT"), ss=True)

        cmds.setAttr(f"{row_from_matrix_driver_0}.input", 3)  # Get translation row
        cmds.setAttr(f"{row_from_matrix_driver_1}.input", 3)  # Get translation row
        cmds.setAttr(f"{multiply_divide_driver_0}.input2X", 0.7)
        cmds.setAttr(f"{multiply_divide_driver_0}.input2Y", 0.7)
        cmds.setAttr(f"{multiply_divide_driver_0}.input2Z", 0.7)
        cmds.setAttr(f"{multiply_divide_driver_1}.input2X", 0.3)
        cmds.setAttr(f"{multiply_divide_driver_1}.input2Y", 0.3)
        cmds.setAttr(f"{multiply_divide_driver_1}.input2Z", 0.3)
        cmds.connectAttr(f"{drivers[0]}.matrix", f"{row_from_matrix_driver_0}.matrix")
        cmds.connectAttr(f"{drivers[1]}.matrix", f"{row_from_matrix_driver_1}.matrix")
        cmds.connectAttr(f"{row_from_matrix_driver_0}.outputX", f"{multiply_divide_driver_0}.input1X")
        cmds.connectAttr(f"{row_from_matrix_driver_0}.outputY", f"{multiply_divide_driver_0}.input1Y")
        cmds.connectAttr(f"{row_from_matrix_driver_0}.outputZ", f"{multiply_divide_driver_0}.input1Z")
        cmds.connectAttr(f"{row_from_matrix_driver_1}.outputX", f"{multiply_divide_driver_1}.input1X")
        cmds.connectAttr(f"{row_from_matrix_driver_1}.outputY", f"{multiply_divide_driver_1}.input1Y")
        cmds.connectAttr(f"{row_from_matrix_driver_1}.outputZ", f"{multiply_divide_driver_1}.input1Z")
        cmds.connectAttr(f"{multiply_divide_driver_0}.outputX", f"{four_by_four_matrix_driver_0}.in30")
        cmds.connectAttr(f"{multiply_divide_driver_0}.outputY", f"{four_by_four_matrix_driver_0}.in31")
        cmds.connectAttr(f"{multiply_divide_driver_0}.outputZ", f"{four_by_four_matrix_driver_0}.in32")
        cmds.connectAttr(f"{multiply_divide_driver_1}.outputX", f"{four_by_four_matrix_driver_1}.in30")
        cmds.connectAttr(f"{multiply_divide_driver_1}.outputY", f"{four_by_four_matrix_driver_1}.in31")
        cmds.connectAttr(f"{multiply_divide_driver_1}.outputZ", f"{four_by_four_matrix_driver_1}.in32")
        cmds.connectAttr(f"{driven_ctl}.matrix", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{four_by_four_matrix_driver_0}.output", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{four_by_four_matrix_driver_1}.output", f"{mult_matrix}.matrixIn[2]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{driven_jnt}.offsetParentMatrix", force=True)





            

