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

class SpineModule(object):

    def __init__(self):

        """
        Initialize the spineModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

        self.primary_input_axis = (0, 0, 1)
        self.secondary_input_axis = (0, 1, 0)

    def make(self, side, spine_joints, spine_controllers):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').
            spine_joints (int): The number of spine joints.
            spine_controllers (int): The number of spine controllers.

        """

        self.spine_joints = spine_joints
        self.spine_controllers = spine_controllers
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_guides_logic()
        self.controller_creation()
        self.local_hip_chest_setup()
        self.ribbon_setup()

        # data_manager.DataExportBiped().append_data("spine_module",
        #                     {
        #                         "local_hip_ctl": self.local_hip_ctl,
        #                         "body_ctl": self.body_ctl,
        #                         "local_chest_ctl": self.local_chest_ctl,
        #                     })
        

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
        Load the spine guides for the specified side and parent them to the module transform.
        """

        self.spine_chain = guides_manager.get_guides(f"{self.side}_spine00_JNT")
        cmds.parent(self.spine_chain[0], self.module_trn)
        print(f"Spine guides loaded for side {self.side}: {self.spine_chain}")

    def create_guides_logic(self):

        """
        Create the logic for spine guides.
        """
        guide_root = cmds.createNode("transform", name=f"{self.side}_spineRoot_Guide", ss=True, p=self.module_trn)
        cmds.matchTransform(guide_root, self.spine_chain[0], pos=True)

        guide_end = cmds.createNode("transform", name=f"{self.side}_spineEnd_Guide", ss=True, p=guide_root)
        cmds.matchTransform(guide_end, self.spine_chain[-1], pos=True)

        cmds.delete(self.spine_chain[0])

        # Build the guides logic
        aim_matrix_guide_00 = cmds.createNode("aimMatrix", name=f"{self.side}_spine00_AIM", ss=True)
        cmds.setAttr(f"{aim_matrix_guide_00}.primaryInputAxis", *self.primary_input_axis, type="double3")
        cmds.setAttr(f"{aim_matrix_guide_00}.secondaryInputAxis", *self.secondary_input_axis, type="double3")
        cmds.connectAttr(f"{guide_root}.worldMatrix[0]", f"{aim_matrix_guide_00}.inputMatrix")
        cmds.connectAttr(f"{guide_end}.worldMatrix[0]", f"{aim_matrix_guide_00}.primaryTargetMatrix")

        blend_matrix_guide_04 = cmds.createNode("blendMatrix", name=f"{self.side}_spine04_BLM", ss=True)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].shearWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].translateWeight", 0)
        cmds.connectAttr(f"{guide_end}.worldMatrix[0]", f"{blend_matrix_guide_04}.inputMatrix")
        cmds.connectAttr(f"{aim_matrix_guide_00}.outputMatrix", f"{blend_matrix_guide_04}.target[0].targetMatrix")

        self.spine_guides_matrices = [f"{aim_matrix_guide_00}.outputMatrix"]

        for i in range(self.spine_controllers - 2): # We assume there are 5 guides for the spine (3 + 2 ends)

            blend_matrix_guide = cmds.createNode("blendMatrix", name=f"{self.side}_spine0{i+1}_BLM", ss=True)
            cmds.setAttr(f"{blend_matrix_guide}.target[0].weight", (i + 1) / (self.spine_controllers - 1))
            cmds.setAttr(f"{blend_matrix_guide}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{blend_matrix_guide}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{blend_matrix_guide}.target[0].shearWeight", 0)
            cmds.connectAttr(f"{aim_matrix_guide_00}.outputMatrix", f"{blend_matrix_guide}.inputMatrix")
            cmds.connectAttr(f"{blend_matrix_guide_04}.outputMatrix", f"{blend_matrix_guide}.target[0].targetMatrix")
            self.spine_guides_matrices.append(f"{blend_matrix_guide}.outputMatrix")

        self.spine_guides_matrices.append(f"{blend_matrix_guide_04}.outputMatrix")
       

    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_localHip", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])

        cmds.connectAttr(f"{self.spine_guides_matrices[0]}", f"{self.body_nodes[0]}.offsetParentMatrix")
        cmds.connectAttr(f"{self.spine_guides_matrices[0]}", f"{self.local_hip_nodes[0]}.offsetParentMatrix")

         # Create the spine controllers

        self.spine_nodes = []
        self.spine_ctls = []
        
        for i, matrix in enumerate(self.spine_guides_matrices):

            spine_node, spine_ctl = curve_tool.create_controller(name=f"{self.side}_spine0{i}", offset=["GRP", "SPC", "ANM"], parent=self.body_ctl, locked_attrs=["v"])
            cmds.connectAttr(matrix, f"{spine_node[0]}.offsetParentMatrix")
            self.spine_nodes.append(spine_node)
            self.spine_ctls.append(spine_ctl)

    def local_hip_chest_setup(self):

        # ------ Local hip setup ------
        cmds.select(clear=True)
        local_hip_skinning_jnt = cmds.joint(name=f"{self.side}_localHipSkinning_JNT")
        decompose_translation_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_localHipTranslation_DCM")
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{decompose_translation_node}.inputMatrix")
        decompose_rotation_node = cmds.createNode("decomposeMatrix", name=f"{self.side}_localHipRotation_DCM")
        cmds.connectAttr(f"{self.local_hip_ctl}.worldMatrix[0]", f"{decompose_rotation_node}.inputMatrix")
        compose_matrix = cmds.createNode("composeMatrix", name=f"{self.side}_localHip_CMP")
        cmds.connectAttr(f"{decompose_translation_node}.outputTranslate", f"{compose_matrix}.inputTranslate")
        cmds.connectAttr(f"{decompose_translation_node}.outputScale", f"{compose_matrix}.inputScale")
        cmds.connectAttr(f"{decompose_rotation_node}.outputRotate", f"{compose_matrix}.inputRotate")
        cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{local_hip_skinning_jnt}.offsetParentMatrix")
        
        cmds.setAttr(f"{self.local_hip_nodes[0]}.inheritsTransform", 0)
        cmds.parent(local_hip_skinning_jnt, self.skeleton_grp)

        # ----- Local chest setup ------
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{self.local_chest_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.select(clear=True)
        local_chest_skinning_jnt = cmds.joint(name=f"{self.side}_localChestSkinning_JNT")
        cmds.setAttr(f"{local_chest_skinning_jnt}.inheritsTransform", 0)
        cmds.connectAttr(f"{self.local_chest_ctl}.worldMatrix[0]", f"{local_chest_skinning_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        
        cmds.parent(local_chest_skinning_jnt, self.skeleton_grp)

    def ribbon_setup(self):

        """
        Set up the ribbon for the spine module.
        """
        # Create the attribute for FK in the body controller
        cmds.addAttr(self.body_ctl, longName="FK", niceName="ATTACHED FK ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="bool", defaultValue=0, keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK_Vis", lock=False, keyable=False, channelBox=True)


        # Create the FK controllers
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i in range(self.spine_joints):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=f"{self.side}_spine0{i}AttatchedFk", offset=["GRP"])
            if i == 0:
                cmds.setAttr(f"{fk_node[0]}.inheritsTransform", 0)
                cmds.parent(fk_node[0], self.controllers_grp)
                cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_node[0]}.visibility")

            self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])
            self.fk_nodes.append(fk_node)
            self.fk_controllers.append(fk_ctl)

        sel = (self.spine_ctls[0], self.spine_ctls[1], self.spine_ctls[2], self.spine_ctls[3], self.spine_ctls[4])
        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_spineSkinning", aim_axis="z", up_axis="y", num_joints=self.spine_joints, skeleton_grp=self.skeleton_grp) # Do the ribbon setup, with the created controllers
        for t in temp:
            cmds.delete(t)
    
        jnt_connections = []
        for i, jnt in enumerate(output_joints): # Use the output joints from the ribbon setup to connect to the FK controllers

            jnt_connection = cmds.listConnections(jnt, source=True, destination=True, plugs=True)[0]

            if jnt_connection:
                
                mult_matrix_node = cmds.createNode("multMatrix", name=jnt.replace("_JNT", "_MMX"))
                cmds.connectAttr(jnt_connection, f"{mult_matrix_node}.matrixIn[0]")
                if i != 0:
                    inverse_matrix_node = cmds.createNode("inverseMatrix", name=jnt.replace("_JNT", "_INV"))
                    cmds.connectAttr(jnt_connections[-1], f"{inverse_matrix_node}.inputMatrix")
                    cmds.connectAttr(f"{inverse_matrix_node}.outputMatrix", f"{mult_matrix_node}.matrixIn[1]")
                    cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{self.fk_nodes[i][0]}.offsetParentMatrix")
                elif i == 0:
                    cmds.connectAttr(jnt_connection, f"{self.fk_nodes[i][0]}.offsetParentMatrix")
                
                cmds.connectAttr(f"{self.fk_controllers[i]}.worldMatrix[0]", f"{jnt}.offsetParentMatrix", force=True)
                jnt_connections.append(jnt_connection)


    