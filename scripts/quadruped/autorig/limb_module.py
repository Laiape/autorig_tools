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

class LimbModule(object):

    def __init__(self):

        """
        Initialize the spineModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

        self.primaryInputAxis = 1, 0, 0
        self.secondaryInputAxis = 0, 1, 0

    def make(self, side, skinning_joints_number):

        """ 
        Create the limb module structure and controllers. Call this method with the side ('L' or 'R') to create the respective limb module.
        Args:
            side (str): The side of the limb ('L' or 'R').

        """
        self.side = side
        self.guides_data = data_manager.DataExportBiped().get_data("limb_module", "guides_data")[0] if self.side == "L" else data_manager.DataExportBiped().get_data("limb_module", "guides_data")[1]
        self.skinning_joints_number = skinning_joints_number
        
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_limbModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_limbSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_limbControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.orient_guides()
        self.fk_setup()
        self.ik_setup()

    
    def load_guides(self):

        """
        Load the guides for the limb module based on the provided guide data.
        Args:
            guides_data (dict): A dictionary containing the guide information for the limb module.

        """
        self.guides = guides_manager.get_guides(self.guides_data)
        print(f"Guides loaded for {self.side} limb module: {self.guides}")


    def orient_guides(self):

        """
        Orient the guides for the limb module to ensure they are properly aligned for rigging.
        """
        
        self.trn_guides = []

        for guide in self.guides:
            
            trn = cmds.createNode("transform", name=guide.replace("JNT", "GUIDE"), ss=True, p=self.module_trn)
            
            if self.trn_guides:
                cmds.parent(trn, self.trn_guides[-1])
            cmds.matchTransform(trn, guide, pos=True) # Match the position of the guide
            self.trn_guides.append(trn)

        self.guides_matrices = []
        
        for i, trn in enumerate(self.trn_guides):
            
            if i == 0:
                matrix_node = cmds.createNode("aimMatrix", name=trn.replace("GUIDE", "AIM"), ss=True)
                cmds.connectAttr(f"{trn}.worldMatrix[0]", f"{matrix_node}.inputMatrix")
                cmds.connectAttr(f"{self.trn_guides[-1]}.worldMatrix[0]", f"{matrix_node}.primary.primaryTargetMatrix")
                cmds.setAttr(f"{matrix_node}.primaryInputAxis", *self.primaryInputAxis)
                cmds.setAttr(f"{matrix_node}.secondaryInputAxis", *self.secondaryInputAxis)
                self.guides_matrices.append(f"{matrix_node}.outputMatrix")

            elif i == len(self.trn_guides) - 1:
                matrix_node = cmds.createNode("blendMatrix", name=trn.replace("GUIDE", "BLM"), ss=True)
                cmds.connectAttr(self.guides_matrices[0], f"{matrix_node}.inputMatrix")
                cmds.connectAttr(f"{trn}.worldMatrix[0]", f"{matrix_node}.target[0].targetMatrix")
                cmds.setAttr(f"{matrix_node}.target[0].weight", 1)
                self.guides_matrices.append(f"{matrix_node}.outputMatrix")

            else:
                matrix_node = cmds.createNode("blendMatrix", name=trn.replace("GUIDE", "BLM"), ss=True)
                cmds.connectAttr(self.guides_matrices[0], f"{matrix_node}.inputMatrix")
                cmds.connectAttr(f"{trn}.worldMatrix[0]", f"{matrix_node}.target[0].targetMatrix")
                weight = i / (len(self.trn_guides) - 1)
                cmds.setAttr(f"{matrix_node}.target[0].weight", weight)
                self.guides_matrices.append(f"{matrix_node}.outputMatrix")

        cmds.delete(self.guides[0])
    
    def fk_setup(self):

        """
        Set up the FK controls for the limb module.
        """

        self.fk_nodes = []
        self.fk_controls = []
        
        for i, matrix in enumerate(self.guides_matrices):

            node_name = self.trn_guides[i].replace("_GUIDE", "Fk")

            fk_nodes, fk_ctl = curve_tool.create_controller(name=node_name, offset=["GRP", "ANM"])
            
            if self.fk_controls:
                cmds.parent(fk_nodes[0], self.fk_controls[-1])
                mmx = cmds.createNode("multMatrix", name=f"{node_name}_MMX", ss=True)
                cmds.connectAttr(matrix, f"{mmx}.matrixIn[0]")
                cmds.connectAttr(f"{self.trn_guides[i-1]}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
                cmds.connectAttr(f"{mmx}.matrixSum", f"{fk_nodes[0]}.offsetParentMatrix")
            
            else:
                cmds.connectAttr(matrix, f"{fk_nodes[0]}.offsetParentMatrix")

            self.fk_nodes.append(fk_nodes)
            self.fk_controls.append(fk_ctl)

    def ik_setup(self, solvers=[]):

        """
        Set up the IK controls for the limb module.
        """
        pass