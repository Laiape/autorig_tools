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
        
        # Red de orientación temporal: se construye igual que antes, se hornean
        # los valores (las guías son estáticas) y se borra, así el rig no
        # arrastra transforms _GUIDE ni nodos aimMatrix vivos.
        trn_guides = []

        for guide in self.guides:

            trn = cmds.createNode("transform", name=guide.replace("JNT", "GUIDETemp"), ss=True)
            cmds.matchTransform(trn, guide, pos=True) # Match the position of the guide
            trn_guides.append(trn)

        self.guides_matrices = []
        temp_nodes = []

        for i, trn in enumerate(trn_guides):

            if i == len(trn_guides) - 1:
                continue # la última guía no genera control FK

            matrix_node = cmds.createNode("aimMatrix", name=trn.replace("GUIDETemp", "TempAIM"), ss=True)
            cmds.connectAttr(f"{trn}.worldMatrix[0]", f"{matrix_node}.inputMatrix")
            cmds.connectAttr(f"{trn_guides[i+1]}.worldMatrix[0]", f"{matrix_node}.primary.primaryTargetMatrix")
            cmds.connectAttr(f"{trn_guides[i+1]}.worldMatrix[0]", f"{matrix_node}.secondary.secondaryTargetMatrix")
            cmds.setAttr(f"{matrix_node}.primaryInputAxis", *self.primaryInputAxis)
            cmds.setAttr(f"{matrix_node}.secondaryInputAxis", *self.secondaryInputAxis)
            cmds.setAttr(f"{matrix_node}.secondaryMode", 2)
            self.guides_matrices.append(cmds.getAttr(f"{matrix_node}.outputMatrix"))
            temp_nodes.append(matrix_node)

        cmds.delete(temp_nodes + trn_guides)
        cmds.delete(self.guides[0])
    
    def fk_setup(self):

        """
        Set up the FK controls for the limb module.
        """

        self.fk_nodes = []
        self.fk_controls = []
        
        for i, matrix in enumerate(self.guides_matrices):

            node_name = self.guides[i].replace("_JNT", "Fk")

            fk_nodes, fk_ctl = curve_tool.create_controller(name=node_name, offset=["GRP", "ANM"], parent=self.controllers_grp)

            if self.fk_controls:
                cmds.parent(fk_nodes[0], self.fk_controls[-1])
                mmx = cmds.createNode("multMatrix", name=f"{node_name}_MMX", ss=True)
                cmds.setAttr(f"{mmx}.matrixIn[0]", matrix, type="matrix")
                cmds.connectAttr(f"{self.fk_nodes[i-1]}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
                cmds.connectAttr(f"{mmx}.matrixSum", f"{fk_nodes[0]}.offsetParentMatrix")

            else:
                cmds.setAttr(f"{fk_nodes[0]}.offsetParentMatrix", matrix, type="matrix")

            cmds.xform(fk_nodes[0], m=om.MMatrix.kIdentity)

            self.fk_nodes.append(fk_nodes[0])
            self.fk_controls.append(fk_ctl)

    def ik_setup(self, solvers=[]):

        """
        Set up the IK controls for the limb module.
        """
        pass