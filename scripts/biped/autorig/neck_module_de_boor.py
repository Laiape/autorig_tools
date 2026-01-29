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

    def make(self, side, skinning_joints_number, controllers_number):

        """ 
        Create the neck module structure and controllers. Call this method with the side ('L' or 'R') to create the respective neck module.
        Args:
            side (str): The side of the neck ('L' or 'R').

        """
        self.side = side
        
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_neckModule_GRP", ss=True, p=self.modules)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckControllers_GRP", ss=True, p=self.masterwalk_ctl)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_neckSkinning_GRP", ss=True, p=self.skel_grp)
        # mGear integration
        self.mGear_integration()

        # self.load_guides()
        # self.controller_creation()
        # self.ribbon_setup(skinning_joints_number)
        # self.local_head()
        # Clean up and store data
        # cmds.delete(self.throat_guide)

        data_manager.DataExportBiped().append_data("neck_module",
                            {
                                "head_ctl": self.head_ctl[0],
                                # "neck_ctl": self.neck_ctls[0],
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
        self.throat_guide = guides_manager.get_guides(f"{self.side}_throat_JNT", parent=self.module_trn)

        cmds.select(clear=True)
        self.head_guide = cmds.createNode("transform", name=f"{self.side}_head_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.head_guide, self.neck_chain[-1], pos=True, rot=True, scl=False)
       

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
        
        for i, jnt in enumerate(self.neck_chain):

            if i == 0:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_neck", offset=["GRP"])
                cmds.connectAttr(f"{corner_ctl}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")
                
            if i == len(self.neck_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_head", offset=["GRP"])
                cmds.parent(face_nodes[0], corner_ctl)
                cmds.matchTransform(face_nodes[0], corner_ctl, pos=True, rot=True)

            if i == 0 or i == len(self.neck_chain) - 1:

                cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)
                cmds.parent(corner_nodes[0], self.controllers_grp)
                
                self.neck_nodes.append(corner_nodes[0])
                self.neck_ctls.append(corner_ctl)


        cmds.xform(self.neck_chain[0], m=om.MMatrix.kIdentity)
        for i , ctl in enumerate(self.neck_ctls):
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])

        throat_nodes, throat_ctl = curve_tool.create_controller(name=f"{self.side}_throat", offset=["GRP"], parent=self.neck_ctls[0])
        self.lock_attributes(throat_ctl, ["sx", "sy", "sz", "v"])
        cmds.matchTransform(throat_nodes[0], self.throat_guide[0], pos=True, rot=True, scl=False)
        skin_throat_jnt = cmds.createNode("joint", name=f"{self.side}_throatSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{throat_ctl}.matrix", f"{skin_throat_jnt}.offsetParentMatrix")
        cmds.matchTransform(skin_throat_jnt, self.throat_guide[0], pos=True, rot=True, scl=False)
    


    def ribbon_setup(self, skinning_joints_number):

        """
        Set up the ribbon for the neck module.
        """
        sel = (self.neck_ctls[0], self.neck_ctls[-1])
        self.output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_neckSkinning", aim_axis="y", up_axis="z", skeleton_grp=self.skeleton_grp, num_joints=skinning_joints_number) # Do the ribbon setup, with the created controllers

        for t in temp:
            cmds.delete(t)

        for jnt in self.output_joints:
            cmds.setAttr(f"{jnt}.inheritsTransform", 1)

    
    def local_head(self):

        """
        Create the local head setup to have the head follow the neck's movement.
        """


        head_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_headSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.setAttr(f"{head_skinning_jnt}.inheritsTransform", 0)

        decompose_translation = cmds.createNode("decomposeMatrix", name=f"{self.side}_headTranslation_DCM")
        cmds.connectAttr(f"{self.output_joints[-1]}.worldMatrix[0]", f"{decompose_translation}.inputMatrix")
        decompose_rotation = cmds.createNode("decomposeMatrix", name=f"{self.side}_headRotation_DCM")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{decompose_rotation}.inputMatrix")
        compose_head = cmds.createNode("composeMatrix", name=f"{self.side}_head_CMP")
        cmds.connectAttr(f"{decompose_translation}.outputTranslate", f"{compose_head}.inputTranslate")
        cmds.connectAttr(f"{decompose_translation}.outputScale", f"{compose_head}.inputScale")
        cmds.connectAttr(f"{decompose_rotation}.outputRotate", f"{compose_head}.inputRotate")
        cmds.connectAttr(f"{compose_head}.outputMatrix", f"{head_skinning_jnt}.offsetParentMatrix")

        cmds.matchTransform(f"{self.neck_nodes[-1]}", self.neck_chain[-1], pos=True, rot=True, scl=False)
        cmds.delete(self.neck_chain[0])
        
        matrix_manager.space_switches(self.neck_ctls[-1], [self.neck_ctls[0], self.masterwalk_ctl], default_value=0) # Neck base and masterwalk

    def mGear_integration(self):

        """
        Integrate the neck module with mGear by adding the necessary attributes to the preferences controller.
        """

        self.head_ctl = cmds.ls(f"{self.side}_head_CTL")
        face_nodes, self.face_ctl = curve_tool.create_controller(name=f"{self.side}_face", offset=["GRP", "ANM"], parent=self.head_ctl[0])
        self.lock_attributes(self.face_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(self.face_ctl, longName="FACE_VIS", niceName="FACE VISIBILITY ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.face_ctl}.FACE_VIS", lock=True, keyable=False, channelBox=True)
        self.head_guide = cmds.createNode("transform", name=f"{self.side}_head_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(self.head_guide, self.head_ctl, pos=True, rot=True)