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

class SpineModule(object):

    def __init__(self):

        """
        Initialize the spineModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.controller_creation()
        self.local_hip_chest_setup()
        # self.stretch_activate()
        self.ribbon_setup()
       



        data_manager.DataExport().append_data("spine_module",
                            {
                                "local_hip_ctl": self.local_hip_ctl,
                                "body_ctl": self.body_ctl,
                                "local_chest_ctl": self.local_chest_ctl,
                                "last_spine_jnt": self.spine_chain[-1]
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

       

    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC"])
        cmds.matchTransform(self.body_nodes[0], self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.parent(self.body_nodes[0], self.controllers_grp)

        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_localHip", offset=["GRP", "SPC"])
        cmds.matchTransform(self.local_hip_nodes[0], self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.parent(self.local_hip_nodes[0], self.controllers_grp)

        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC"])
        cmds.parent(self.local_chest_nodes[0], self.controllers_grp)

        self.lock_attributes(self.body_ctl, ["sx", "sy", "sz", "v"])
        self.lock_attributes(self.local_hip_ctl, ["sx", "sy", "sz", "v"])

        self.spine_nodes = []
        self.spine_ctls = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            if i == 0 or i == len(self.spine_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])
                
                cmds.matchTransform(corner_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 0:

                    cmds.parent(corner_nodes[0], self.body_ctl)

                else:

                    cmds.parent(self.spine_nodes[-1], corner_ctl)
                    cmds.parent(corner_nodes[0], self.spine_ctls[(len(self.spine_ctls) // 2)])

                self.spine_nodes.append(corner_nodes[0])
                self.spine_ctls.append(corner_ctl)

            if i == (len(self.spine_chain) - 1) // 2:

                mid_nodes, mid_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", ""), offset=["GRP"])

                cmds.parent(mid_nodes[0], self.spine_ctls[0])
                cmds.matchTransform(mid_nodes[0], self.spine_chain[(len(self.spine_chain) // 2) - 1], pos=True, rot=True, scl=False)
                self.spine_nodes.append(mid_nodes[0])
                self.spine_ctls.append(mid_ctl)

            
            if i == 1 or i == len(self.spine_chain) - 2:

                tan_nodes, tan_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "Tan"), offset=["GRP"])

                cmds.matchTransform(tan_nodes[0], jnt, pos=True, rot=True, scl=False)

                if i == 1:

                    cmds.parent(tan_nodes[0], self.spine_ctls[-1])

                self.spine_nodes.append(tan_nodes[0])
                self.spine_ctls.append(tan_ctl)

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
        cmds.addAttr(self.body_ctl, longName="FK", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        fk_controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineFKControllers_GRP", ss=True, p=self.body_ctl)
        cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_controllers_grp}.visibility")

        # Create the FK controllers
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i, jnt in enumerate(self.spine_chain):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=jnt.replace("_JNT", "FK"), offset=["GRP"])
            # cmds.matchTransform(fk_node[0], jnt, pos=True, rot=True, scl=False)
            cmds.parent(fk_node[0], fk_controllers_grp)
            self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])
            self.fk_nodes.append(fk_node)
            self.fk_controllers.append(fk_ctl)

        sel = (self.spine_ctls[0], self.spine_ctls[1], self.spine_ctls[2], self.spine_ctls[3], self.spine_ctls[4])
        self.skeleton_grp, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_spineSkinning", aim_axis="y", up_axis="z", num_joints=len(self.spine_chain)) # Do the ribbon setup, with the created controllers
        cmds.setAttr(f"{self.skeleton_grp}.inheritsTransform", 1)
        for t in temp:
            cmds.delete(t)
        
        cmds.parent(self.skeleton_grp, self.skel_grp) # Parent the output skinning joints trn to skeleton_grp

        self.joints = cmds.listRelatives(self.skeleton_grp, c=True, type="joint")
        jnt_connections = []
        for i, jnt in enumerate(self.joints):

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


    def stretch_activate(self):

        """
        Stretch activate
        """
        # Create the guides for the aim and blend matrix nodes
        guide_00 = cmds.createNode("transform", name=f"{self.side}_spine00_Guide", ss=True, p=self.module_trn)
        guide_01 = cmds.createNode("transform", name=f"{self.side}_spine01_Guide", ss=True, p=self.module_trn)
        cmds.matchTransform(guide_00, self.spine_chain[0], pos=True, rot=True, scl=False)
        cmds.matchTransform(guide_01, self.spine_chain[-1], pos=True, rot=True, scl=False)

        aim_matrix_spine_00 = cmds.createNode("aimMatrix", name=f"{self.side}_spine00_AIM", ss=True)
        cmds.setAttr(f"{aim_matrix_spine_00}.primaryInputAxis", 0, 1, 0, type="double3")
        cmds.connectAttr(f"{guide_00}.worldMatrix[0]", f"{aim_matrix_spine_00}.inputMatrix")
        cmds.connectAttr(f"{guide_01}.worldMatrix[0]", f"{aim_matrix_spine_00}.primaryTargetMatrix") # Aim at the next guide

        blend_matrix_guide_04 = cmds.createNode("blendMatrix", name=f"{self.side}_spine04_BLM", ss=True)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].shearWeight", 0)
        cmds.setAttr(f"{blend_matrix_guide_04}.target[0].translateWeight", 0)
        cmds.connectAttr(f"{guide_01}.worldMatrix[0]", f"{blend_matrix_guide_04}.inputMatrix") # First target is the guide itself
        cmds.connectAttr(f"{aim_matrix_spine_00}.outputMatrix", f"{blend_matrix_guide_04}.target[0].targetMatrix")

        blend_matrix_spine = cmds.createNode("blendMatrix", name=f"{self.side}_spine_BLM", ss=True)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].weight", 1)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_spine}.target[0].shearWeight", 0)
        cmds.connectAttr(f"{aim_matrix_spine_00}.outputMatrix", f"{blend_matrix_spine}.inputMatrix") # First target is the guide itself
        cmds.connectAttr(f"{guide_01}.worldMatrix[0]", f"{blend_matrix_spine}.target[0].targetMatrix")

        # Create the stretch attribute in the body controller
        cmds.addAttr(self.body_ctl, longName="STRETCH", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.STRETCH", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="Stretch", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        # Create the nodes to drive the stretch
        distance_node = cmds.createNode("distanceBetween", name=f"{self.side}_spineStretch_DTB")
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{distance_node}.inMatrix1")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{distance_node}.inMatrix2") # Distance between the first and last spine joint

        divide_node = cmds.createNode("divide", name=f"{self.side}_spineStretch_DIV")
        cmds.connectAttr(f"{distance_node}.distance", f"{divide_node}.input1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{divide_node}.input2")

        distance_matrix_node = cmds.createNode("distanceBetween", name=f"{self.side}_spineStretchMatrix_DTB")
        cmds.connectAttr(f"{aim_matrix_spine_00}.outputMatrix", f"{distance_matrix_node}.inMatrix1")
        cmds.connectAttr(f"{blend_matrix_guide_04}.outputMatrix", f"{distance_matrix_node}.inMatrix2") # Distance between the first aim matrix and the last blend matrix

        blend_two_attr_node = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineStretch_B2A")
        cmds.connectAttr(f"{self.body_ctl}.Stretch", f"{blend_two_attr_node}.attributesBlender")
        cmds.connectAttr(f"{divide_node}.output", f"{blend_two_attr_node}.input[0]")   
        cmds.connectAttr(f"{distance_matrix_node}.distance", f"{blend_two_attr_node}.input[1]") # Blend between no stretch and full stretch

        four_by_four_matrix_node = cmds.createNode("fourByFourMatrix", name=f"{self.side}_spineStretch_44M", ss=True)
        cmds.connectAttr(f"{blend_two_attr_node}.output", f"{four_by_four_matrix_node}.in31")

        blend_matrix_ctls = cmds.createNode("aimMatrix", name=f"{self.side}_spineStretch_AIM", ss=True)
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{blend_matrix_ctls}.inputMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{blend_matrix_ctls}.primaryTargetMatrix") # Second target is the stretch matrix
        cmds.setAttr(f"{blend_matrix_ctls}.primaryInputAxis", 0, 1, 0, type="double3")
        
        mult_matrix_stretch_node = cmds.createNode("multMatrix", name=f"{self.side}_spineStretch_MMX", ss=True)
        cmds.connectAttr(f"{blend_matrix_ctls}.outputMatrix", f"{mult_matrix_stretch_node}.matrixIn[0]")
        cmds.connectAttr(f"{four_by_four_matrix_node}.output", f"{mult_matrix_stretch_node}.matrixIn[1]") # Apply the stretch to the final blend matrix

        

        index = [1, 1- 1/len(self.spine_chain), 0.5, 1/len(self.spine_chain),  0]

        self.blend_matrices = []
        for i, ctl in enumerate(self.spine_ctls):
            
            blend_matrix_node = cmds.createNode("blendMatrix", name=ctl.replace("CTL", "BLM"), ss=True)
            cmds.setAttr(f"{blend_matrix_node}.target[0].weight", index[i])
            cmds.setAttr(f"{blend_matrix_node}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{blend_matrix_node}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{blend_matrix_node}.target[0].shearWeight", 0)
            cmds.connectAttr(f"{mult_matrix_stretch_node}.matrixSum", f"{blend_matrix_node}.inputMatrix", force=True)
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend_matrix_node}.target[0].targetMatrix", force=True) # Second target is the aim matrix
            self.blend_matrices.append(blend_matrix_node)
