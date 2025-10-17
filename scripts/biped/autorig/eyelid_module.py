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

    def make(self, side, vertex_num=13):

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
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

        self.load_guides()
        self.locators_into_guides()
        self.create_main_eye_setup()
        self.create_controllers()
        self.create_curves()
        self.eye_direct()
        self.create_blink_setup()
        self.skinning_joints(vertex_num=vertex_num)
        self.cleanup()

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
            local_trn = cmds.createNode("transform", name=ctl.replace("01_CTL", "01Local_TRN"), ss=True, p=ctl.replace("01_CTL", "Local_TRN"))
            local_jnt = cmds.createNode("joint", name=ctl.replace("01_CTL", "01Local_JNT"), ss=True, p=local_trn)
            cmds.delete(local_jnt.replace("01Local_JNT", "Local_JNT"))
            # if "Up" in ctl:
            #     self.upper_local_jnt.remove(local_jnt.replace("01Local_JNT", "Local_JNT"))
            # if "Down" in ctl:
            #     self.lower_local_jnt.remove(local_jnt.replace("01Local_JNT", "Local_JNT"))
        else:
            local_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=self.module_trn)
            local_jnt = cmds.createNode("joint", name=ctl.replace("_CTL", "Local_JNT"), ss=True, p=local_trn)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_trn}.offsetParentMatrix")
        cmds.matchTransform(local_trn, grp)
        

        return local_trn, local_jnt

    def load_guides(self):

        """
        Load the guide locators for the eyelid module.
        """

        self.locators = []
        for guide in ["In", "UpIn", "Up", "UpOut",  "DownIn", "Down", "DownOut", "Out"]:
            if "Blink" not in guide:
                loc = guides_manager.get_guides(f"{self.side}_eyelid{guide}_LOCShape")
                self.locators.append(loc)
                cmds.parent(loc, self.module_trn)

        self.eye_joint = guides_manager.get_guides(f"{self.side}_eye_JNT")
        cmds.parent(self.eye_joint[0], self.module_trn)

        self.upper_blink_locators = [] # Create list for upper blink locators
        self.upper_blink_locators.append(self.locators[0])
        for guide in ["UpInBlink", "UpBlink", "UpOutBlink"]:
            loc = guides_manager.get_guides(f"{self.side}_eyelid{guide}_LOCShape")
            self.upper_blink_locators.append(loc)
            cmds.parent(loc, self.module_trn)
        self.upper_blink_locators.append(self.locators[-1])

        self.lower_blink_locators = [] # Create list for lower blink locators
        self.lower_blink_locators.append(self.locators[0])
        for guide in ["DownInBlink", "DownBlink", "DownOutBlink"]:
            loc = guides_manager.get_guides(f"{self.side}_eyelid{guide}_LOCShape")
            self.lower_blink_locators.append(loc)
            cmds.parent(loc, self.module_trn)
        self.lower_blink_locators.append(self.locators[-1])

        self.blink_ref_locators = [] # Create list for blink reference locators
        self.blink_ref_locators.append(self.locators[0])
        for guide in ["eyelidBlink01", "eyelidBlink02", "eyelidBlink03"]:
            loc = guides_manager.get_guides(f"{self.side}_{guide}_LOCShape")
            self.blink_ref_locators.append(loc)
            cmds.parent(loc, self.module_trn)
        self.blink_ref_locators.append(self.locators[-1])

    def locators_into_guides(self):

        """
        Convert locators into guides for the eyelid module.
        """

        self.eye_guide = cmds.createNode("transform", name=f"{self.side}_eye_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.eye_guide, self.eye_joint[0])

        self.guides_matrices = []

        for loc in self.locators:
            four_by_four_matrix = cmds.createNode("fourByFourMatrix", name=loc.replace("LOC", "FFX")) # Create a fourByFourMatrix node for each locator
            cmds.connectAttr(f"{loc}.translateX", f"{four_by_four_matrix}.in30")
            cmds.connectAttr(f"{loc}.translateY", f"{four_by_four_matrix}.in31")
            cmds.connectAttr(f"{loc}.translateZ", f"{four_by_four_matrix}.in32")
            if self.side == "R":
                cmds.setAttr(f"{four_by_four_matrix}.in00", -1)
            self.guides_matrices.append(four_by_four_matrix)
            

    def create_main_eye_setup(self):

        """
        Create the main eye setup for the eyelid module.
        """
        eye_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_eyeSkinning_JNT", p=self.skeleton_grp)

        if self.side == "L":
            self.main_aim_nodes, self.main_aim_ctl = curve_tool.create_controller(name=f"C_eyeMain", offset=["GRP"])
            cmds.parent(self.main_aim_nodes[0], self.head_ctl)
            self.lock_attributes(self.main_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
            before_translate = cmds.xform(self.eye_joint[0], q=True, t=True, ws=True)
            cmds.setAttr(f"{self.eye_joint[0]}.tx", 0)
            cmds.matchTransform(self.main_aim_nodes[0], self.eye_joint[0])
            cmds.select(self.main_aim_nodes[0])
            cmds.move(0, 0, 10, relative=True, objectSpace=True, worldSpaceDistance=True)
            cmds.xform(self.eye_joint[0], t=before_translate, ws=True)

        side_aim_nodes, self.side_aim_ctl = curve_tool.create_controller(name=f"{self.side}_eye", offset=["GRP"])
        cmds.parent(side_aim_nodes[0], self.controllers_grp)
        cmds.matchTransform(side_aim_nodes[0], self.eye_joint[0])
        cmds.select(side_aim_nodes[0])
        cmds.move(0, 0, 10, relative=True, objectSpace=True, worldSpaceDistance=True)
        self.lock_attributes(self.side_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
        cmds.parent(side_aim_nodes[0], "C_eyeMain_CTL")

        # Aim setup
        self.eye_jnt_matrix = cmds.xform(self.eye_joint[0], q=True, m=True, ws=True)
        self.aim = cmds.createNode("aimMatrix", name=f"{self.side}_eye_AIM", ss=True)
        cmds.setAttr(f"{self.aim}.primaryInputAxis", 0, 0, 1)
        cmds.setAttr(f"{self.aim}.secondaryInputAxis", 0, 1, 0)
        cmds.setAttr(f"{self.aim}.secondaryTargetVector", 0, 1, 0)
        cmds.setAttr(f"{self.aim}.secondaryMode", 2) # Align
        cmds.connectAttr(f"{self.eye_guide}.worldMatrix[0]", f"{self.aim}.inputMatrix")
        cmds.connectAttr(f"{self.side_aim_ctl}.worldMatrix[0]", f"{self.aim}.primaryTargetMatrix")
        cmds.connectAttr(f"{self.head_ctl}.worldMatrix[0]", f"{self.aim}.secondaryTargetMatrix")
        cmds.connectAttr(f"{self.aim}.outputMatrix", f"{eye_skinning_jnt}.offsetParentMatrix")
        cmds.xform(self.eye_joint[0], m=om.MMatrix.kIdentity)

    

    def create_controllers(self):

        """
        Create controllers for the eyelid module.
        """

        self.upper_local_trn = []
        self.lower_local_trn = []
        self.upper_local_jnt = []
        self.lower_local_jnt = []

        self.controllers = []

        for i, matrix in enumerate(self.guides_matrices):

            node, ctl = curve_tool.create_controller(name=matrix.replace("_FFX", ""), offset=["GRP"])
            local_trn, local_jnt = self.local(ctl)
            cmds.matchTransform(local_trn, node[0])
            if "eyelidIn_" in matrix or "eyelidOut_" in matrix or "eyelidDown_" in matrix or "eyelidUp_" in matrix:
                node_01, ctl_01 = curve_tool.create_controller(name=matrix.replace("_FFX", "01"), offset=["GRP"])
                local_trn_01, local_jnt = self.local(ctl_01)
    
                cmds.matchTransform(local_trn_01, node_01[0])
                cmds.parent(node_01, ctl)
                
            cmds.parent(node, self.controllers_grp)
            
            if "Up" in matrix:
                self.upper_local_jnt.append(local_jnt)
                self.upper_local_trn.append(local_trn)
            elif "Down" in matrix:
                self.lower_local_jnt.append(local_jnt)
                self.lower_local_trn.append(local_trn)
            elif "In" not in matrix or "Out" not in matrix:
                self.upper_local_trn.append(local_trn)
                self.lower_local_trn.append(local_trn)
                self.upper_local_jnt.append(local_jnt)
                self.lower_local_jnt.append(local_jnt)

                    
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])

            cmds.connectAttr(f"{matrix}.output", f"{node[0]}.offsetParentMatrix")
            self.controllers.append(ctl)

        for trn in self.upper_local_trn + self.lower_local_trn:
            cmds.matchTransform(trn, trn.replace("Local_TRN", "_GRP"))

    def create_curves(self):

        """
        Create curves for the blink setup.
        """
        curves_grp = cmds.createNode("transform", name=f"{self.side}_eyelidCurves_GRP", ss=True, p=self.module_trn)
        self.eyelid_up_curve = cmds.curve(name=f"{self.side}_eyelidUp_CRV", d=3, p=[tuple(cmds.xform(trn, q=True, t=True, ws=True)) for trn in self.upper_local_trn])
        self.eyelid_down_curve = cmds.curve(name=f"{self.side}_eyelidDown_CRV", d=3, p=[tuple(cmds.xform(trn, q=True, t=True, ws=True)) for trn in self.lower_local_trn])
        self.eyelid_up_curve_rebuild = cmds.rebuildCurve( self.eyelid_up_curve, n=f"{self.side}_eyelidUpRebuilded_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=1, kep=1, kt=0, tol=0.01)
        self.eyelid_down_curve_rebuild = cmds.rebuildCurve(self.eyelid_down_curve, n=f"{self.side}_eyelidDownRebuilded_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=1, kep=1, kt=0, tol=0.01)

        self.blink_ref_curve = cmds.curve(name=f"{self.side}_eyelidBlinkRef_CRV", d=3, p=[tuple(cmds.xform(loc, q=True, t=True, ws=True)) for loc in self.blink_ref_locators])
        self.up_blink_curve = cmds.curve(name=f"{self.side}_eyelidUpBlink_CRV", d=3, p=[tuple(cmds.xform(loc, q=True, t=True, ws=True)) for loc in self.upper_blink_locators])
        self.down_blink_curve = cmds.curve(name=f"{self.side}_eyelidDownBlink_CRV", d=3, p=[tuple(cmds.xform(loc, q=True, t=True, ws=True)) for loc in self.lower_blink_locators])

        cmds.parent(self.eyelid_up_curve, curves_grp)
        cmds.parent(self.eyelid_up_curve_rebuild, curves_grp)
        cmds.parent(self.eyelid_down_curve, curves_grp)
        cmds.parent(self.eyelid_down_curve_rebuild, curves_grp)
        cmds.parent(self.blink_ref_curve, curves_grp)
        cmds.parent(self.up_blink_curve, curves_grp)
        cmds.parent(self.down_blink_curve, curves_grp)

    def eye_direct(self):

        """
        Add custom attributes to the eyelid controllers.
        """

        self.eye_direct_nodes, self.eye_direct_ctl = curve_tool.create_controller(name=f"{self.side}_eyeDirect", offset=["GRP"])
        cmds.parent(self.eye_direct_nodes[0], self.head_ctl)
        cmds.matchTransform(self.eye_direct_nodes[0], self.eye_guide)
        cmds.select(self.eye_direct_nodes[0])
        cmds.move(0, 0, 5, relative=True, objectSpace=True, worldSpaceDistance=True)
        self.lock_attributes(self.eye_direct_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])

        cmds.addAttr(self.eye_direct_ctl, ln="EYE_ATTRIBUTES", at="enum", en="____", k=True)
        cmds.setAttr(f"{self.eye_direct_ctl}.EYE_ATTRIBUTES", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Upper_Blink", at="float", min=-1, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Lower_Blink", at="float", min=-1, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Blink_Height", at="float", min=0, max=1, dv=0.2, k=True)

        # Connect the aim matrix to the eye direct controller and orient constrain the eye joint to it
        # eye_direct_matrix = cmds.xform(self.eye_direct_nodes, q=True, m=True, ws=True)
        # cmds.setAttr(f"{self.aim}.inputMatrix", eye_direct_matrix, type="matrix")
        # cmds.connectAttr(f"{self.aim}.outputMatrix", f"{self.eye_direct_nodes[0]}.offsetParentMatrix", force=True)
        # cmds.xform(self.eye_direct_nodes[0], m=om.MMatrix.kIdentity)
        # cmds.setAttr(f"{self.eye_direct_nodes[0]}.inheritsTransform", 0)
        # pick_matrix_rotation = cmds.createNode("pickMatrix", name=f"{self.side}_eye_PMK", ss=True)
        # cmds.connectAttr(f"{self.eye_direct_ctl}.worldMatrix[0]", f"{pick_matrix_rotation}.inputMatrix")
        # cmds.setAttr(f"{pick_matrix_rotation}.useTranslate", 0)
        # cmds.setAttr(f"{pick_matrix_rotation}.useScale", 0)
        # cmds.connectAttr(f"{pick_matrix_rotation}.outputMatrix", f"{self.eye_joint[0]}.offsetParentMatrix", force=True)
        # cmds.xform(self.eye_joint[0], m=self.eye_jnt_matrix)
        

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

    def skinning_joints(self, vertex_num=15):
        
        """
        Output the skinning joints for the eyelid module, creating one for each vertex on the upper and lower eyelid curves.
        """
        self.linear_upper_curve = cmds.rebuildCurve(self.eyelid_up_curve_rebuild, ch=False, rpo=False, rt=0, end=1, kr=0, kcp=0, kep=1, kt=1, s=vertex_num-1, tol=0.01, n=f"{self.side}_eyelidUpperLinear_CRV")[0]
        self.linear_lower_curve = cmds.rebuildCurve(self.eyelid_down_curve_rebuild, ch=False, rpo=False, rt=0, end=1, kr=0, kcp=0, kep=1, kt=1, s=vertex_num-1, tol=0.01, n=f"{self.side}_eyelidLowerLinear_CRV")[0]

        cmds.parent(self.linear_upper_curve, self.module_trn)
        cmds.parent(self.linear_lower_curve, self.module_trn)

        self.upper_skin_joints = []
        self.lower_skin_joints = []

        upper_cvs = cmds.ls(self.linear_upper_curve + ".cv[*]", fl=True)
        lower_cvs = cmds.ls(self.linear_lower_curve + ".cv[*]", fl=True)

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
            cmds.connectAttr(f"{self.linear_upper_curve}Shape.editPoints[{i}].xValueEp", f"{four_by_four_matrix_origin}.in30", f=True)
            cmds.connectAttr(f"{self.linear_upper_curve}Shape.editPoints[{i}].yValueEp", f"{four_by_four_matrix_origin}.in31", f=True)
            cmds.connectAttr(f"{self.linear_upper_curve}Shape.editPoints[{i}].zValueEp", f"{four_by_four_matrix_origin}.in32", f=True)

            cmds.connectAttr(f"{four_by_four_matrix_origin}.output", f"{parent_matrix}.inputMatrix") # Connect the four by four matrix to the parent matrix input
            cmds.connectAttr(f"{four_by_four_matrix}.output", f"{parent_matrix}.target[0].targetMatrix") # Connect the origin four by four matrix to the parent matrix target

            jnt_aim = cmds.createNode("joint", name=f"{self.side}_{name}Eyelid0{i}Center_JNT", ss=True, p=self.skeleton_grp) # Create aim joint for orientation reference
            jnt = cmds.createNode("joint", name=f"{self.side}_{name}Eyelid0{i}Tip_JNT", ss=True, p=jnt_aim) # Create skinning joint

            aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_{name}Eyelid0{i}_AIM", ss=True)
            cmds.connectAttr(f"{self.eye_guide}.worldMatrix[0]", f"{aim_matrix}.inputMatrix")
            cmds.setAttr(f"{aim_matrix}.primaryInputAxis", 0, 0, 1)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{aim_matrix}.primaryTargetMatrix")
            cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{jnt_aim}.offsetParentMatrix") # Connect the aim matrix to the four by four matrix
            temp_trn = cmds.createNode("transform", name=f"{self.side}_{name}Eyelid0{i}_TEMP", ss=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{temp_trn}.offsetParentMatrix")
            cmds.matchTransform(jnt, temp_trn)
            cmds.delete(temp_trn)

            self.upper_skin_joints.append(jnt)


    def cleanup(self):

        cmds.delete(self.eye_joint)
        
        for loc in self.locators:
            cmds.delete(loc)

        for loc in self.upper_blink_locators[1:-1] + self.lower_blink_locators[1:-1] + self.blink_ref_locators[1:-1]:
            cmds.delete(loc)

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


            

