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

class NeckModule(object):

    def __init__(self):

        """
        Initialize the neckModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the neck module structure and controllers. Call this method with the side ('L' or 'R') to create the respective neck module.
        Args:
            side (str): The side of the neck ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_neckModule_GRP", ss=True, p=self.modules)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.controller_creation()
        self.ribbon_setup()
        self.local_head()


        data_manager.DataExport().append_data("neck_module",
                            {
                                "head_ctl": self.neck_ctls[-1],
                                "neck_ctl": self.neck_ctls[0]
                            })
        

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:source_matrices
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def load_guides(self):

        """
        Load the neck guides for the specified side and parent them to the module transform.
        """

        self.neck_chain = guides_manager.get_guides(f"{self.side}_neck00_JNT")
        cmds.parent(self.neck_chain[0], self.module_trn)

       

    def controller_creation(self):

        """
        Create controllers for the neck module.
        """

        self.neck_nodes = []
        self.neck_ctls = []
        
        for i, jnt in enumerate(self.neck_chain):

            if i == 0:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_neck", offset=["GRP"])
                cmds.connectAttr(f"{corner_ctl}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")
                
            if i == len(self.neck_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_head", offset=["GRP"])

            if i == 0 or i == len(self.neck_chain) - 1:

                cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)
                cmds.parent(corner_nodes[0], self.controllers_grp)
                
                self.neck_nodes.append(corner_nodes[0])
                self.neck_ctls.append(corner_ctl)


        cmds.xform(self.neck_chain[0], m=om.MMatrix.kIdentity)
        for i , ctl in enumerate(self.neck_ctls):
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])


    def ribbon_setup(self):

        """
        Set up the ribbon for the neck module.
        """
        sel = (self.neck_ctls[0], self.neck_ctls[-1])
        self.skeleton_grp, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_neckSkinning", aim_axis="y", up_axis="z") # Do the ribbon setup, with the created controllers

        for t in temp:
            cmds.delete(t)
        
        cmds.parent(self.skeleton_grp, self.skel_grp) # Parent the output skinning joints trn to skeleton_grp

        self.joints = cmds.listRelatives(self.skeleton_grp, c=True, type="joint")

        for jnt in self.joints:
            cmds.setAttr(f"{jnt}.inheritsTransform", 1)


    def local_head(self):

        """
        Create the local head setup to have the head follow the neck's movement.
        """

        self.head_jnt = cmds.joint(name=f"{self.side}_head_JNT")
        cmds.parent(self.head_jnt, self.module_trn)

        decompose_translation = cmds.createNode("decomposeMatrix", name=f"{self.side}_headTranslation_DCM")
        cmds.connectAttr(f"{self.joints[-1]}.worldMatrix[0]", f"{decompose_translation}.inputMatrix")
        decompose_rotation = cmds.createNode("decomposeMatrix", name=f"{self.side}_headRotation_DCM")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{decompose_rotation}.inputMatrix")
        compose_head = cmds.createNode("composeMatrix", name=f"{self.side}_head_CMP")
        cmds.connectAttr(f"{decompose_translation}.outputTranslate", f"{compose_head}.inputTranslate")
        cmds.connectAttr(f"{decompose_translation}.outputScale", f"{compose_head}.inputScale")
        cmds.connectAttr(f"{decompose_rotation}.outputRotate", f"{compose_head}.inputRotate")
        cmds.connectAttr(f"{compose_head}.outputMatrix", f"{self.head_jnt}.offsetParentMatrix")

        head_skinning_jnt = cmds.joint(name=f"{self.side}_headSkinning_JNT")
        cmds.setAttr(f"{head_skinning_jnt}.inheritsTransform", 0)
        cmds.parent(head_skinning_jnt, self.skeleton_grp)
        cmds.connectAttr(f"{self.head_jnt}.worldMatrix[0]", f"{head_skinning_jnt}.offsetParentMatrix")

        cmds.matchTransform(f"{self.neck_nodes[-1]}", self.neck_chain[-1], pos=True, rot=True, scl=False)
        cmds.xform(self.head_jnt, m=om.MMatrix.kIdentity)
        cmds.delete(self.neck_chain[0])
        
        matrix_manager.space_switches(self.neck_ctls[-1], [self.neck_ctls[0], self.masterwalk_ctl], default_value=0) # Neck base and masterwalk
         