import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from quadruped.utils import data_manager
from quadruped.utils import guides_manager
from quadruped.utils import curve_tool

from biped.autorig.utilities import matrix_manager
from biped.autorig.utilities import ribbon

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

        self.modules = data_manager.DataExportQuadruped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportQuadruped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportQuadruped().get_data("basic_structure", "masterwalk_ctl")

        

    def make(self, side, primary_axis=(1,0,0), secondary_axis=(0,1,0)):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').

        """

        self.primary_axis = primary_axis
        self.secondary_axis = secondary_axis
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_guides()
        self.controller_creation()
        self.ribbon_setup()
       



        data_manager.DataExportQuadruped().append_data("spine_module",
                            {
                                "local_hip_ctl": self.local_hip_ctl,
                                "body_ctl": self.body_ctl,
                                "local_chest_ctl": self.local_chest_ctl
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
        Load the spine guides for the specified side and parent them to the module transform.
        """

        self.spine_chain = guides_manager.get_guides(f"{self.side}_spine00_JNT")
        cmds.parent(self.spine_chain[0], self.module_trn)

    def create_guides(self):

        """
        Create guides for the spine module.
        """
        guide_00 = cmds.createNode("transform", name=f"{self.side}_spine00_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(guide_00, self.spine_chain[0], pos=True, rot=True, scl=False)
        guide_02 = cmds.createNode("transform", name=f"{self.side}_spine02_GUIDE", ss=True, p=self.module_trn)
        cmds.matchTransform(guide_02, self.spine_chain[1], pos=True, rot=True, scl=False)
        cmds.delete(self.spine_chain[0])

        aim_matrix_00 = cmds.createNode("aimMatrix", name=f"{self.side}_spine00_AMX", ss=True)
        cmds.connectAttr(f"{guide_00}.worldMatrix[0]", f"{aim_matrix_00}.inputMatrix") # Connect the world matrix of the first spine joint to the aim matrix
        cmds.setAttr(f"{aim_matrix_00}.primaryInputAxis", *self.primary_axis) # Aim in primary axis direction
        cmds.setAttr(f"{aim_matrix_00}.secondaryInputAxis", *self.secondary_axis) # Up in secondary axis direction
        cmds.connectAttr(f"{guide_02}.worldMatrix[0]", f"{aim_matrix_00}.primaryTargetMatrix") # Aim to the last spine joint

        
        blend_matrix_02 = cmds.createNode("blendMatrix", name=f"{self.side}_spine02_BMX", ss=True)
        cmds.connectAttr(f"{guide_02}.worldMatrix[0]", f"{blend_matrix_02}.inputMatrix")
        cmds.connectAttr(f"{aim_matrix_00}.outputMatrix", f"{blend_matrix_02}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_02}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_02}.target[0].translateWeight", 0) # Bind to input matrix
        cmds.setAttr(f"{blend_matrix_02}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_02}.target[0].shearWeight", 0)

        blend_matrix_mid = cmds.createNode("blendMatrix", name=f"{self.side}_spine01_BMX", ss=True)
        cmds.connectAttr(f"{aim_matrix_00}.outputMatrix", f"{blend_matrix_mid}.inputMatrix")
        cmds.connectAttr(f"{blend_matrix_02}.outputMatrix", f"{blend_matrix_mid}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_mid}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_mid}.target[0].translateWeight", 0.5) # Halfway between both
        cmds.setAttr(f"{blend_matrix_mid}.target[0].rotateWeight", 0) 
        cmds.setAttr(f"{blend_matrix_mid}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_mid}.target[0].shearWeight", 0)

        blend_matrix_00_tan = cmds.createNode("blendMatrix", name=f"{self.side}_spine00Tan_BMX", ss=True)
        cmds.connectAttr(f"{aim_matrix_00}.outputMatrix", f"{blend_matrix_00_tan}.inputMatrix")
        cmds.connectAttr(f"{blend_matrix_02}.outputMatrix", f"{blend_matrix_00_tan}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_00_tan}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_00_tan}.target[0].translateWeight", 0.2)
        cmds.setAttr(f"{blend_matrix_00_tan}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_00_tan}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_00_tan}.target[0].shearWeight", 0)
        blend_matrix_02_tan = cmds.createNode("blendMatrix", name=f"{self.side}_spine02Tan_BMX", ss=True)
        cmds.connectAttr(f"{blend_matrix_02}.outputMatrix", f"{blend_matrix_02_tan}.inputMatrix")
        cmds.connectAttr(f"{aim_matrix_00}.outputMatrix", f"{blend_matrix_02_tan}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_02_tan}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_02_tan}.target[0].translateWeight", 0.2)

        self.guides = [guide_00, guide_02]
        self.guides_matrices = [f"{aim_matrix_00}.outputMatrix", f"{blend_matrix_00_tan}.outputMatrix", f"{blend_matrix_mid}.outputMatrix", f"{blend_matrix_02_tan}.outputMatrix", f"{blend_matrix_02}.outputMatrix"]

    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC"], parent=self.controllers_grp)
        cmds.connectAttr(self.guides_matrices[0], f"{self.body_nodes[0]}.offsetParentMatrix")

        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_localHip", offset=["GRP", "SPC"], parent=self.controllers_grp)
        cmds.connectAttr(self.guides_matrices[0], f"{self.local_hip_nodes[0]}.offsetParentMatrix") # Free the local hip ctl from body, parent after in space switch setup

        self.hip_nodes, self.hip_ctl = curve_tool.create_controller(name=f"{self.side}_hip", offset=["GRP", "SPC"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.body_ctl}.worldMatrix[0]", f"{self.hip_nodes[0]}.offsetParentMatrix") # Connect the body ctl to hip ctl


        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC"], parent=self.controllers_grp)
        self.blend_matrix_chest = cmds.createNode("blendMatrix", name=f"{self.side}_localChest_BMX", ss=True) # Must connect last spine ctl and the boors last

        self.lock_attributes(self.body_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_hip_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_chest_ctl, ["sx", "sy", "sz", "v"])

        self.spine_nodes = []
        self.spine_ctls = []
        
        self.spine_nodes_00, self.spine_ctl_00 = curve_tool.create_controller(name=f"{self.side}_spine00", offset=["GRP", "SPC"], parent=self.controllers_grp)
        self.spine_nodes_00_tan, self.spine_ctl_00_tan = curve_tool.create_controller(name=f"{self.side}_spine00Tan", offset=["GRP", "SPC"], parent=self.controllers_grp)
        cmds.connectAttr(f"{self.hip_ctl}.worldMatrix[0]", f"{self.spine_nodes_00[0]}.offsetParentMatrix")
        cmds.connectAttr(self.guides_matrices[1], f"{self.spine_nodes_00_tan[0]}.offsetParentMatrix")

        self.spine_nodes_01, self.spine_ctl_01 = curve_tool.create_controller(name=f"{self.side}_spine01", offset=["GRP", "SPC"], parent=self.controllers_grp)
        cmds.connectAttr(self.guides_matrices[2], f"{self.spine_nodes_01[0]}.offsetParentMatrix")

        self.spine_nodes_02, self.spine_ctl_02 = curve_tool.create_controller(name=f"{self.side}_spine02", offset=["GRP", "SPC"], parent=self.controllers_grp)
        self.spine_nodes_02_tan, self.spine_ctl_02_tan = curve_tool.create_controller(name=f"{self.side}_spine02Tan", offset=["GRP", "SPC"], parent=self.controllers_grp)
        cmds.connectAttr(self.guides_matrices[-1], f"{self.spine_nodes_02[0]}.offsetParentMatrix")
        cmds.connectAttr(self.guides_matrices[3], f"{self.spine_nodes_02_tan[0]}.offsetParentMatrix")

        cmds.setAttr(f"{self.spine_nodes_00[0]}.inheritsTransform", 0)
        cmds.setAttr(f"{self.spine_nodes_01[0]}.inheritsTransform", 0)
        cmds.setAttr(f"{self.spine_nodes_02[0]}.inheritsTransform", 0)
        cmds.setAttr(f"{self.local_hip_nodes[0]}.inheritsTransform", 0)
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.setAttr(f"{self.hip_nodes[0]}.inheritsTransform", 0)

        for ctl in [self.spine_ctl_00, self.spine_ctl_00_tan, self.spine_ctl_01, self.spine_ctl_02, self.spine_ctl_02_tan]:
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            if "Tan" in ctl:
                self.lock_attributes(ctl, ["rx", "ry", "rz"])


        # matrix_manager.space_switches(target=self.spine_nodes_01[1], sources=[self.spine_ctl_00, self.spine_ctl_02, self.masterwalk_ctl], default_value=1) # Spine 01 ctl space switch
        # matrix_manager.space_switches(target=self.spine_nodes_02[1], sources=[self.spine_ctl_00, self.masterwalk_ctl], default_value=1) # Spine 02 ctl space switch

        # ------ Local hip setup ------
        local_hip_skinning = cmds.createNode("joint", name=f"{self.side}_localHip_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{self.local_hip_ctl}.worldMatrix[0]", f"{local_hip_skinning}.offsetParentMatrix") # Connect local hip ctl to local hip node


    def ribbon_setup(self):

        """
        Set up the ribbon for the spine module.
        """
        # Create the attribute for FK in the body controller
        cmds.addAttr(self.body_ctl, longName="FK", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)


        # Create the FK controllers
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i in range(8):

            fk_node, fk_ctl = curve_tool.create_controller(name=f"{self.side}_spine0{i+1}AttachFk", offset=["GRP"])
            if i == 0:
                cmds.setAttr(f"{fk_node[0]}.inheritsTransform", 0)
                cmds.parent(fk_node[0], self.controllers_grp)
                cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_node[0]}.visibility")

            self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])
            self.fk_nodes.append(fk_node)
            self.fk_controllers.append(fk_ctl)

        sel = (self.spine_ctl_00, self.spine_ctl_00_tan, self.spine_ctl_01, self.spine_ctl_02_tan, self.spine_ctl_02)
        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_spineSkinning", aim_axis="x", up_axis="y", num_joints=8, skeleton_grp=self.skeleton_grp) # Do the ribbon setup, with the created controllers
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

                if i == len(output_joints) -1: # Last joint connects to local chest blend matrix
                    cmds.rename(jnt, f"{self.side}_localChest_JNT")
            
        
        cmds.connectAttr(jnt_connections[-1], f"{self.blend_matrix_chest}.inputMatrix")
        cmds.connectAttr(f"{self.spine_ctl_02}.worldMatrix[0]", f"{self.blend_matrix_chest}.target[0].targetMatrix")
        cmds.setAttr(f"{self.blend_matrix_chest}.target[0].weight", 1)
        cmds.setAttr(f"{self.blend_matrix_chest}.target[0].translateWeight", 0)
        cmds.connectAttr(f"{self.blend_matrix_chest}.outputMatrix", f"{self.local_chest_nodes[0]}.offsetParentMatrix")



