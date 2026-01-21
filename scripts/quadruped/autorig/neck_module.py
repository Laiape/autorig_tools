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

class NeckModule(object):

    def __init__(self):

        """
        Initialize the neckModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.preferences_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")

        self.primary_axis = (1,0,0)
        self.secondary_axis = (0,1,0)

    def make(self, side, skinning_joints_number, controllers_number):

        """ 
        Create the neck module structure and controllers. Call this method with the side ('L' or 'R') to create the respective neck module.
        Args:
            side (str): The side of the neck ('L' or 'R').

        """
        self.side = side
        self.controllers_number = controllers_number

        self.module_trn = cmds.createNode("transform", name=f"{self.side}_neckModule_GRP", ss=True, p=self.modules)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckControllers_GRP", ss=True, p=self.masterwalk_ctl)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_neckSkinning_GRP", ss=True, p=self.skel_grp)

        self.load_guides()
        self.controller_creation()
        self.ribbon_setup(skinning_joints_number)
        self.local_head()

        data_manager.DataExportBiped().append_data("neck_module",
                            {
                                "head_ctl": self.neck_ctls[-1],
                                "neck_ctl": self.neck_ctls[0],
                                "head_guide": self.head_guide,
                                "face_ctl": self.face_ctl,
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

        self.neck_chain = guides_manager.get_guides(f"{self.side}_neck00_JNT", parent=self.module_trn)
        cmds.select(clear=True)

        neck_root_guide = cmds.createNode("transform", name=f"{self.side}_neckRoot_Guide", ss=True, p=self.module_trn)
        cmds.matchTransform(neck_root_guide, self.neck_chain[0], pos=True, rot=True)

        neck_end_guide = cmds.createNode("transform", name=f"{self.side}_neckEnd_Guide", ss=True, p=neck_root_guide)
        cmds.matchTransform(neck_end_guide, self.neck_chain[-1], pos=True, rot=True)
        self.head_guide = neck_end_guide

        # Create aim matrix for neck root
        aim_matrix_root = cmds.createNode("aimMatrix", name=f"{self.side}_neck00_AIM", ss=True)
        cmds.setAttr(f"{aim_matrix_root}.primaryInputAxis", *self.primary_axis, type="double3")
        cmds.setAttr(f"{aim_matrix_root}.secondaryInputAxis", *self.secondary_axis, type="double3")
        cmds.connectAttr(f"{neck_root_guide}.worldMatrix[0]", f"{aim_matrix_root}.inputMatrix")
        cmds.connectAttr(f"{neck_end_guide}.worldMatrix[0]", f"{aim_matrix_root}.primaryTargetMatrix")

        blend_matrix_end = cmds.createNode("blendMatrix", name=f"{self.side}_neckEnd_BLM", ss=True)
        cmds.connectAttr(f"{neck_end_guide}.worldMatrix[0]", f"{blend_matrix_end}.inputMatrix")
        cmds.connectAttr(f"{aim_matrix_root}.outputMatrix", f"{blend_matrix_end}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_end}.envelope", 1)
        cmds.setAttr(f"{blend_matrix_end}.target[0].translateWeight", 0)
        cmds.setAttr(f"{blend_matrix_end}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_end}.target[0].shearWeight", 0)

        self.neck_guides_matrices = []
        self.neck_guides_matrices.append(f"{aim_matrix_root}.outputMatrix")

        for i in range(self.controllers_number - 2):
            
            blend_matrix = cmds.createNode("blendMatrix", name=f"{self.side}_neck{str(i+1).zfill(2)}_BLM", ss=True)
            cmds.connectAttr(f"{aim_matrix_root}.outputMatrix", f"{blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{blend_matrix_end}.outputMatrix", f"{blend_matrix}.target[0].targetMatrix")
            weight = (i + 1) / (self.controllers_number - 1)
            cmds.setAttr(f"{blend_matrix}.envelope", weight)
            self.neck_guides_matrices.append(f"{blend_matrix}.outputMatrix")
        
        self.neck_guides_matrices.append(f"{blend_matrix_end}.outputMatrix")
        cmds.delete(self.neck_chain[0])

    def controller_creation(self):

        """
        Create controllers for the neck module.
        """

        self.neck_nodes = []
        self.neck_ctls = []

        face_nodes, self.face_ctl = curve_tool.create_controller(name=f"{self.side}_face", offset=["GRP", "ANM"])
        self.lock_attributes(self.face_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(self.face_ctl, longName="FACE_VIS", niceName="FACE VISIBILITY ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.face_ctl}.FACE_VIS", lock=True, keyable=False, channelBox=True)
        
        for i, matrix in enumerate(self.neck_guides_matrices):

            corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_neck{str(i).zfill(2)}", offset=["GRP", "ANM"], locked_attrs=["v"], parent=self.controllers_grp) 
            cmds.connectAttr(f"{matrix}", f"{corner_nodes[0]}.offsetParentMatrix")
                
            self.neck_nodes.append(corner_nodes[0])
            self.neck_ctls.append(corner_ctl)

        # Make hierarchy
        for i, node in enumerate(self.neck_nodes):
            if i == 1:
                cmds.parent(node, self.neck_ctls[0])
            elif i == len(self.neck_nodes) // 2:
                ctl = self.neck_ctls[i]
                cmds.addAttr(ctl, longName="TANGENT_VISIBILITY", niceName="TANGENT VISIBILITY -----", attributeType="enum", enumName="-----")
                cmds.setAttr(f"{ctl}.TANGENT_VISIBILITY", lock=True, keyable=False, channelBox=True)
                cmds.addAttr(ctl, longName="Controllers_Visibility", niceName="Controllers Visibility", attributeType="float", minValue=0, maxValue=1, defaultValue=1, keyable=True)
                cmds.parent(node, self.neck_ctls[0])
            elif i == len(self.neck_nodes) - 2:
                cmds.parent(node, self.neck_ctls[-1])
            elif i == len(self.neck_nodes) - 1:
                cmds.parent(node, self.neck_ctls[len(self.neck_ctls)// 2])

        self.head_nodes, self.head_ctl = curve_tool.create_controller(name=f"{self.side}_head", offset=["GRP", "ANM"], parent=self.controllers_grp, locked_attrs=["v"])
        cmds.parent(face_nodes[0], self.head_ctl)
    
    def ribbon_setup(self, skinning_joints_number):

        """
        Set up the ribbon for the neck module.
        """
        sel = self.neck_ctls
        self.output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_neck", aim_axis="x", up_axis="y", skeleton_grp=self.skeleton_grp, num_joints=skinning_joints_number) # Do the ribbon setup, with the created controllers

        for t in temp:
            cmds.delete(t)

        for jnt in self.output_joints:
            cmds.setAttr(f"{jnt}.inheritsTransform", 1)

        cmds.rename(self.output_joints[-1], f"{self.side}_headSkinning_JNT")

    
    def local_head(self):

        """
        Create the local head setup to have the head follow the neck's movement.
        """

        cmds.addAttr(self.head_ctl, longName="NECK_FOLLOW", niceName="LOCAL HEAD -----", attributeType="enum", enumName="-----")
        cmds.setAttr(f"{self.head_ctl}.NECK_FOLLOW", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.head_ctl, longName="HEAD_FOLLOW", niceName="Head Follow", attributeType="float", minValue=0, maxValue=1, defaultValue=1, keyable=True)

        
        blend_matrix_head = cmds.createNode("blendMatrix", name=f"{self.side}_headLocal_BLM", ss=True)
        cmds.connectAttr(f"{self.head_guide}.worldMatrix[0]", f"{blend_matrix_head}.inputMatrix")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{blend_matrix_head}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.head_ctl}.HEAD_FOLLOW", f"{blend_matrix_head}.target[0].weight")
        cmds.connectAttr(f"{blend_matrix_head}.outputMatrix", f"{self.head_nodes[0]}.offsetParentMatrix")

        