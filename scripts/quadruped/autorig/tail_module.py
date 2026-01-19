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

    
    def import_guides(self):

        """
        Import the tail guides and set up the tail joint chain based on the guides.
        """

        self.tail_chain = guides_manager.get_guides(f"{self.side}_tail00_JNT")

    def create_controllers(self):

        """
        Create the tail controllers and set up their hierarchy and constraints.
        """

        self.tail_controllers = []

        for i, jnt in enumerate(self.tail_chain):
            
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

        ik_handle = cmds.ikHandle(
            name=f"{self.side}_tail_IK",
            startJoint=self.tail_chain[0],
            endEffector=self.tail_chain[-1],
            solver="ikSplineSolver",
            createCurve=False)[0]

        cmds.parent(ik_handle, self.tail_controllers[0])
        cmds.setAttr(f"{ik_handle}.visibility", 0)