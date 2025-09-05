import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool

from autorig.utilities import matrix_manager
from autorig.utilities import ribbon

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
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExport().get_data("neck_module", "head_ctl")

    def make(self, side):

        """ 
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_eyebrow"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

        self.load_guides()
        self.create_controllers()
        self.ribbon_setup()
        self.slide_setup()

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
        self.eyebrows = eyebrows[1:]
        
        for jnt in self.eyebrows:
            cmds.parent(jnt, self.module_trn)

        if self.side == "L":
            self.radius_loc = guides_manager.get_guides("C_headRadius_LOCShape")
            cmds.select(clear=True)
            self.mid_eyebrow = guides_manager.get_guides("C_eyebrowMid_JNT")
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
            distance = cmds.getAttr(f"{self.radius_loc}.translateX")
            self.sphere = cmds.sphere(name="C_eyebrowSlide_NRB", sections=4, startSweep=160, radius=distance)[0]
            cmds.parent(self.sphere, self.module_trn)
            cmds.setAttr(f"{self.radius_loc}.translateX", 0)
            cmds.matchTransform(self.sphere, self.radius_loc)
            cmds.delete(self.radius_loc)
            

        self.main_eyebrow_nodes, self.main_eyebrow_ctl = curve_tool.create_controller(f"{self.side}_eyebrowMain", offset=["GRP", "OFF"])
        
        cmds.matchTransform(self.main_eyebrow_nodes[0], self.main_eyebrow)
        cmds.parent(self.main_eyebrow_nodes[0], self.controllers_grp)
        self.lock_attributes(self.main_eyebrow_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        main_local_grp, main_local_trn = self.local(self.main_eyebrow_ctl)

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

    def ribbon_setup(self): 

        """
        Set up ribbon system for the eyebrow module.
        """

        sel = [trn for trn in self.local_trns]

        self.skinning_trn, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_eyebrowSkinning", aim_axis='x', up_axis='y', num_joints=len(self.eyebrows))

        for t in temp:
            cmds.delete(t)
        cmds.parent(self.skinning_trn, self.skeleton_grp)

    def slide_setup(self):

        """
        Set up the slide functionality for the eyebrow module.

        """

        cmds.addAttr(self.main_eyebrow_ctl, longName="SLIDE", attributeType="enum", enumName="___")
        cmds.setAttr(f"{self.main_eyebrow_ctl}.SLIDE", keyable=False, channelBox=True)
        cmds.addAttr(self.main_eyebrow_ctl, longName="slide", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        skinning_joints = cmds.listRelatives(self.skinning_trn, c=True, type="joint")

        for i, ctl in enumerate(self.eyebrow_controllers):

            closest_point = cmds.createNode("closestPointOnSurface", name=ctl.replace("_CTL", "Slide_CPOS"))
            point_on_surface_info = cmds.createNode("pointOnSurfaceInfo", name=ctl.replace("_CTL", "Slide_POS"))
            compose_matrix = cmds.createNode("composeMatrix", name=ctl.replace("_CTL", "Slide_CMTX"))
            aim_matrix = cmds.createNode("aimMatrix", name=ctl.replace("_CTL", "Slide_AMTX"))

            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{point_on_surface_info}.inputSurface")
            cmds.connectAttr(f"{self.local_trns[i]}.translate", f"{closest_point}.inPosition") # I think this should change
            cmds.connectAttr(f"{closest_point}.parameterU", f"{point_on_surface_info}.parameterU")
            cmds.connectAttr(f"{closest_point}.parameterV", f"{point_on_surface_info}.parameterV")
            cmds.connectAttr(f"{point_on_surface_info}.position", f"{compose_matrix}.inputTranslate")
            cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{aim_matrix}.inputMatrix")
            cmds.connectAttr(f"{point_on_surface_info}.normalizedTangentV", f"{aim_matrix}.primaryTargetVector")
            cmds.connectAttr(f"{point_on_surface_info}.normalizedTangentU", f"{aim_matrix}.secondaryTargetVector")

            blend_matrix = cmds.createNode("blendMatrix", name=ctl.replace("_CTL", "Slide_BMTX"))
            cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{blend_matrix}.inputMatrix")

            input_conns = cmds.listConnections(f"{skinning_joints[i]}.offsetParentMatrix", source=True, destination=True, plugs=True)
            cmds.connectAttr(f"{input_conns[0]}", f"{blend_matrix}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.main_eyebrow_ctl}.slide", f"{blend_matrix}.target[0].weight")
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{skinning_joints[i]}.offsetParentMatrix", force=True)
            
