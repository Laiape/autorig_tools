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

class TailModule(object):

    def __init__(self):

        """
        Initialize the tailModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the tail module structure and controllers. Call this method with the side ('L' or 'R') to create the respective tail module.
        Args:
            side (str): The side of the tail ('C').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_tailModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_tailSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_tailControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.import_guides()
        self.fk_setup()
        self.ik_setup()
        self.pair_blends_setup()

    
    def import_guides(self):

        """
        Import the tail guides and set up the tail joint chain based on the guides.
        """

        self.tail_chain = guides_manager.get_guides(f"{self.side}_tail00_JNT")

    def fk_setup(self):

        """
        Create the tail controllers and set up their hierarchy and constraints.
        """

        self.tail_controllers = []

        for jnt in self.tail_chain:
            
            nodes, ctl = curve_tool.create_controller(
                name=jnt.replace("_JNT", "_CTL"),
                offset=["GRP", "ANM"],
                parent=self.controllers_grp,
                match=jnt)
            
            if self.tail_controllers:
                cmds.parent(nodes[0], self.tail_controllers[-1])
            
            self.tail_controllers.append(ctl)

    def ik_setup(self):

        """
        Set up the IK handle for the tail and connect it to the tail controllers.
        """
        ik_controllers = []
        
        for i, jnt in enumerate(self.tail_chain):

            if i == 0 or  i == len(self.tail_chain) // 2 or i == len(self.tail_chain) - 1:

                nodes, ctl = curve_tool.create_controller(
                    name=jnt.replace("_JNT", ""),
                    offset=["GRP", "ANM"],
                    parent=self.controllers_grp,
                    match=jnt)
                
                if i == len(self.tail_chain) // 2:
                    cmds.parent(nodes[0], ik_controllers[0])
                elif i == len(self.tail_chain) - 1:
                    cmds.parent(nodes[0], ik_controllers[-2])
                
            if i == 1 or i == len(self.tail_chain) - 2:

                tan_nodes, tan_ctl = curve_tool.create_controller(
                    name=jnt.replace("_JNT", "Tan"),
                    offset=["GRP", "ANM"],
                    parent=ik_controllers[-1],
                    match=jnt)
                    
            ik_controllers.append(ctl)
        
        ik_curve = cmds.curve(
            name=f"{self.side}_tailIk_CRV",
            degree=3,
            point=[cmds.xform(jnt, q=True, ws=True, t=True) for jnt in self.tail_chain])
        
        cmds.parent(ik_curve, self.module_trn)

        ik_handle = cmds.ikHandle(
            name=f"{self.side}_tailIk_HDL",
            startJoint=self.tail_chain[0],
            endEffector=self.tail_chain[-1],
            solver="ikSplineSolver",
            createCurve=False,
            curve=ik_curve)[0]

        cmds.parent(ik_handle, self.module_trn)

    def pair_blends_setup(self):

        """
        Set up pair blend constraints between tail controllers and joints for smooth deformation.
        """
        self.blend_matrices_out = []
        for ctl, jnt in zip(self.tail_controllers, self.tail_chain):
            
            blend_matrix_node = cmds.createNode("blendMatrix", name=jnt.replace("JNT", "BLM"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend_matrix_node}.inputMatrix[0]")
            cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{blend_matrix_node}.input[0].targetMatrix")
            self.blend_matrices_out.append(blend_matrix_node)


    def de_boors_call(self):

        """
        Set up the de Boor's algorithm for smooth tail deformation.
        """
        ribbon_drivers = self.blend_matrices_out 
        skinning_jnts, temp = ribbon.de_boor_ribbon(cvs=ribbon_drivers, name=f"{self.side}_tail", num_joints=5, skeleton_grp=self.skeleton_grp)

        for t in temp:
            cmds.delete(t)

    def extra_setup(self):

        """
        Perform any additional setup required for the tail module.
        """
        pass