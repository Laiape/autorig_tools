import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool

from autorig.utilities import matrix_manager
from autorig.utilities import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)
reload(ribbon)

class EyebrowModule(object):

    def __init__(self):

        """
        Initialize the EyebrowModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")
        cmds.select(clear=True)
        self.mid_eyebrow = guides_manager.get_guides("C_eyebrowMid_JNT")

    def make(self, side):

        """ 
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_eyebrow"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_controllers()

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def load_guides(self):

        cmds.select(clear=True)
        self.eyebrows = guides_manager.get_guides(f"{self.side}_eyebrowMain_JNT")

    def create_controllers(self):

        """
        Create controllers for the eyebrow module.
        """
  

        self.sphere = cmds.sphere(name=f'{self.side}_eyebroweSlide_NRB', sections=4, startSweep=160)[0]
        cmds.parent(self.sphere, self.module_trn)
        cmds.matchTransform(self.sphere, self.mid_eyebrow[0])
