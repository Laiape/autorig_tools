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

    def make(self, side, skinning_joints_number):

        """ 
        Create the limb module structure and controllers. Call this method with the side ('L' or 'R') to create the respective limb module.
        Args:
            side (str): The side of the limb ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_limbModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_limbSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_limbControllers_GRP", ss=True, p=self.masterwalk_ctl)