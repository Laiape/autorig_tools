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

class EyebrowModule(object):

    def __init__(self):

        """
        Initialize the EyebrowModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")

    def make(self, side):

        """ 
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_eyebrow"
        if cmds.objExists(f"{self.module_name}Module_GRP"):
            self.module_trn = f"{self.module_name}Module_GRP"
            self.skeleton_grp = f"{self.module_name}Skinning_GRP"
            self.controllers_grp = f"{self.module_name}Controllers_GRP"
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)
        
            cmds.addAttr(self.face_ctl, longName="Brows", attributeType="long", defaultValue=2, max=3, min=0, keyable=True)


        self.load_guides()
        self.create_controllers()
        self.ribbon_setup()
        self.slide_setup()

        # Clean up
        cmds.delete(self.main_eyebrow)
        if self.side == "L":
            cmds.delete(self.mid_eyebrow)


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
        grp = ctl.replace("_CTL", "_GRP")
        mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMT"))
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{local_trn}.offsetParentMatrix")
        cmds.matchTransform(local_grp, ctl)
        # cmds.parent(local_trn, self.module_trn)

        return local_grp, local_trn

    def load_guides(self):

        cmds.select(clear=True)
        eyebrows = guides_manager.get_guides(f"{self.side}_eyebrowMain_JNT")
        cmds.parent(eyebrows[0], self.module_trn)
        self.main_eyebrow = eyebrows[0]
        self.eyebrows = sorted(eyebrows[1:])
        cmds.select(clear=True)

        for jnt in self.eyebrows:
            cmds.parent(jnt, self.module_trn)

        if self.side == "L":
            self.mid_eyebrow = guides_manager.get_guides("C_eyebrowMid_JNT")[0]
            cmds.parent(self.mid_eyebrow, self.module_trn)
            

    def create_controllers(self):

        """
        Create controllers for the eyebrow module.
        """
        self.eyebrow_controllers = []
        self.eyebrow_nodes = []
        self.local_trns = []
        self.local_grps = []

        if self.side == "L":

            self.sphere = guides_manager.get_guides("C_eyebrowSlide_NURBShape", parent=self.module_trn)
        
        self.sphere = cmds.ls("C_eyebrowSlide_NURB", long=True)[0]
        cmds.hide(self.sphere)

        condition_primary = cmds.createNode("condition", name="C_eyebrowPrimary_COND", ss=True)
        cmds.setAttr(f"{condition_primary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_primary}.secondTerm", 1)
        cmds.setAttr(f"{condition_primary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_primary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Brows", f"{condition_primary}.firstTerm") 
            
        self.main_eyebrow_nodes, self.main_eyebrow_ctl = curve_tool.create_controller(f"{self.side}_eyebrowMain", offset=["GRP", "OFF"])
        cmds.matchTransform(self.main_eyebrow_nodes[0], self.main_eyebrow)
        cmds.connectAttr(f"{condition_primary}.outColorR", f"{self.main_eyebrow_nodes[0]}.visibility") # Connect visibility
        
        cmds.parent(self.main_eyebrow_nodes[0], self.controllers_grp)
        self.lock_attributes(self.main_eyebrow_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        main_local_grp, main_local_trn = self.local(self.main_eyebrow_ctl)

        if self.side == "L":
            mid_eyebrow_nodes, mid_eyebrow_ctl = curve_tool.create_controller("C_eyebrowMid", offset=["GRP", "OFF"])

            cmds.connectAttr(f"{condition_primary}.outColorR", f"{mid_eyebrow_nodes[0]}.visibility") # Connect visibility

            cmds.parent(mid_eyebrow_nodes[0], self.controllers_grp)
            self.lock_attributes(mid_eyebrow_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])

            mid_local_grp, mid_local_trn = self.local(mid_eyebrow_ctl)
            mid_eyebrow_guide = cmds.createNode("transform", name="C_eyebrowMid_GUIDE", ss=True, p=self.module_trn)
            cmds.matchTransform(mid_eyebrow_guide, self.mid_eyebrow)
            jnt = cmds.createNode("joint", name="C_eyebrowMidSkinning_JNT", ss=True, p=self.skeleton_grp)
            cmds.connectAttr(f"{mid_local_trn}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")

            # Set up mid eyebrow parentMatrix
            fbf_mid = cmds.createNode("fourByFourMatrix", name="C_eyebrowMid_FBF", ss=True)
            cmds.setAttr(f"{fbf_mid}.in30", cmds.getAttr(f"{mid_eyebrow_guide}.translateX"))
            cmds.setAttr(f"{fbf_mid}.in31", cmds.getAttr(f"{mid_eyebrow_guide}.translateY"))
            cmds.setAttr(f"{fbf_mid}.in32", cmds.getAttr(f"{mid_eyebrow_guide}.translateZ"))
            
            
            parent_matrix = cmds.createNode("parentMatrix", name="C_eyebrowMid_PM", ss=True)
            cmds.connectAttr(f"{fbf_mid}.output", f"{parent_matrix}.inputMatrix")
            cmds.connectAttr(f"{main_local_trn}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")

            mult_matrix = cmds.createNode("multMatrix", name="C_eyebrowMid_MMX", ss=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[0]")
            cmds.setAttr(f"{mult_matrix}.matrixIn[1]", cmds.getAttr(f"{self.head_ctl}.worldInverseMatrix[0]"), type="matrix")
            cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{mid_eyebrow_nodes[0]}.offsetParentMatrix")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mid_local_grp}.offsetParentMatrix")
            cmds.setAttr(f"{parent_matrix}.envelope", 0.5)
        
            cmds.xform(mid_local_grp, m=om.MMatrix.kIdentity)
            cmds.xform(mid_eyebrow_nodes[0], m=om.MMatrix.kIdentity)
            
        else:
            parent_matrix = "C_eyebrowMid_PM"
            mid_eyebrow_nodes = "C_eyebrowMid_GRP" # Dummy for get_offset_matrix
            mid_eyebrow_guide = "C_eyebrowMid_GUIDE" # Dummy for get_offset_matrix
            cmds.connectAttr(f"{main_local_trn}.worldMatrix[0]", f"{parent_matrix}.target[1].targetMatrix")

        if self.side == "L":
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", *self.get_offset_matrix(mid_eyebrow_guide, main_local_trn), type="matrix")
        else:
            cmds.setAttr(f"{parent_matrix}.target[1].offsetMatrix", *self.get_offset_matrix(mid_eyebrow_guide, main_local_trn), type="matrix")
            cmds.delete(mid_eyebrow_guide)

        names = {"In": 0, "InTan": 1, "Mid": len(self.eyebrows) // 2, "OutTan": -2, "Out": -1}

        for name, value in names.items():

            eyebrow_nodes, eyebrow_ctl = curve_tool.create_controller(f"{self.side}_eyebrow{name}", offset=["GRP"])
            cmds.matchTransform(eyebrow_nodes[0], self.eyebrows[value])
            cmds.parent(eyebrow_nodes[0], self.main_eyebrow_ctl)
            self.lock_attributes(eyebrow_ctl, ["visibility"])

            local_grp, local_trn = self.local(eyebrow_ctl)
            cmds.parent(local_grp, main_local_trn)
            self.eyebrow_controllers.append(eyebrow_ctl)
            self.eyebrow_nodes.append(eyebrow_nodes)
            self.local_trns.append(local_trn)
            self.local_grps.append(local_grp)

        cmds.parent(self.eyebrow_nodes[-2], self.eyebrow_controllers[-1]) # OutTan to Out
        cmds.parent(self.eyebrow_nodes[1], self.eyebrow_controllers[0]) # InTan to In
        cmds.parent(self.local_grps[-2], self.local_trns[-1]) # OutTan to Out
        cmds.parent(self.local_grps[1], self.local_trns[0]) # InTan to In

        condition_secondary = cmds.createNode("condition", name="C_eyebrowSecondary_COND", ss=True)
        cmds.setAttr(f"{condition_secondary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_secondary}.secondTerm", 2)
        cmds.setAttr(f"{condition_secondary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_secondary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Brows", f"{condition_secondary}.firstTerm")
        cmds.connectAttr(f"{condition_secondary}.outColorR", f"{self.eyebrow_nodes[1][0]}.visibility") # InTan visibility
        cmds.connectAttr(f"{condition_secondary}.outColorR", f"{self.eyebrow_nodes[-2][0]}.visibility") # OutTan visibility


    def ribbon_setup(self): 

        """
        Set up ribbon system for the eyebrow module.
        """

        sel = [trn for trn in self.local_trns]

        self.output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_eyebrowSkinning", aim_axis='x', up_axis='y', num_joints=len(self.eyebrows), skeleton_grp=self.skeleton_grp)

        for t in temp:
            cmds.delete(t)


    def slide_setup(self):

        """
        Set up the slide functionality for the eyebrow module.

        """

        cmds.addAttr(self.main_eyebrow_ctl, longName="SLIDE", niceName="SLIDE ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.main_eyebrow_ctl}.SLIDE", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.main_eyebrow_ctl, longName="slide", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)


        for i, jnt in enumerate(self.output_joints):

            closest_point = cmds.createNode("closestPointOnSurface", name=jnt.replace("_JNT", "Slide_CPOS"), ss=True)
            row_from_matrix_projection = cmds.createNode("rowFromMatrix", name=jnt.replace("_JNT", "Slide_RFM"), ss=True)
            cmds.setAttr(f"{row_from_matrix_projection}.input", 3) # Getting the translation row
            compose_matrix = cmds.createNode("composeMatrix", name=jnt.replace("_JNT", "Slide_CM"), ss=True)
            decompose_matrix = cmds.createNode("decomposeMatrix", name=jnt.replace("_JNT", "Slide_DCM"), ss=True)
            blend_matrix = cmds.createNode("blendMatrix", name=jnt.replace("_JNT", "Slide_BM"), ss=True)
            jnt_input = cmds.listConnections(jnt, source=True, destination=True, plugs=True)[0] # Getting the input matrix of the joint

            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{closest_point}.inputSurface") # Sphere world matrix to CPOS
            cmds.connectAttr(jnt_input, f"{row_from_matrix_projection}.matrix") # Joint input matrix to RFM
            cmds.connectAttr(f"{row_from_matrix_projection}.outputX", f"{closest_point}.inPositionX")
            cmds.connectAttr(f"{row_from_matrix_projection}.outputY", f"{closest_point}.inPositionY") 
            cmds.connectAttr(f"{row_from_matrix_projection}.outputZ", f"{closest_point}.inPositionZ")
            cmds.connectAttr(jnt_input, f"{decompose_matrix}.inputMatrix") # Joint input matrix to CM
            cmds.connectAttr(f"{closest_point}.position", f"{compose_matrix}.inputTranslate") # CPOS position to CM
            cmds.connectAttr(f"{decompose_matrix}.outputRotate", f"{compose_matrix}.inputRotate") # DM to CM
            cmds.connectAttr(f"{decompose_matrix}.outputScale", f"{compose_matrix}.inputScale") # DM to CM
            cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{blend_matrix}.target[0].targetMatrix") # CM to BM
            cmds.connectAttr(jnt_input, f"{blend_matrix}.inputMatrix") # Joint input matrix to BM
            cmds.connectAttr(f"{self.main_eyebrow_ctl}.slide", f"{blend_matrix}.target[0].weight") # Slide attribute to BM weight
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{jnt}.offsetParentMatrix", force=True) # BM to joint offsetParentMatrix

        for jnt in self.eyebrows:
            cmds.delete(jnt)

            
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


            

