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

class EyelidModule(object):

    def __init__(self):

        """
        Initialize the eyelidModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExport().get_data("neck_module", "head_ctl")

    def make(self, side):

        """ 
        Create the eyelid module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyelid module.
        Args:
            side (str): The side of the eyelid ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_eyelid"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.head_ctl)

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

    def local(self, ctl):

        """
        Create a local transform node for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            str: The name of the local transform node.
        """

        local_grp = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_GRP"), ss=True, p=self.module_trn)
        local_trn = cmds.createNode("transform", name=ctl.replace("_CTL", "Local_TRN"), ss=True, p=local_grp)
        grp = ctl.replace("_CTL", "_GRP")
        mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMT"))
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{local_trn}.offsetParentMatrix")
        cmds.matchTransform(local_grp, ctl)

        return local_grp, local_trn

    def load_guides(self):
        """
        Load the guide locators for the eyelid module.
        """

        self.locators = []
        for guide in ["In", "UpIn", "Up", "UpOut",  "DownOut", "Down", "DownIn", "Out"]:
            loc = guides_manager.get_guides(f"{self.side}_eyelid{guide}_LOCShape")
            self.locators.append(loc)
            cmds.parent(loc, self.module_trn)


    def create_controllers(self):

        """
        Create controllers for the eyelid module.
        """

        for i, loc in enumerate(self.locators):

            node, ctl = curve_tool.create_controller(name=loc.replace("_LOC", ""), offset=["GRP"])
            local_grp, local_trn = self.local(ctl)
            if "eyelidIn_" in loc or "eyelidOut_" in loc or "eyelidDown_" in loc or "eyelidUp_" in loc:
                node_01, ctl_01 = curve_tool.create_controller(name=loc.replace("_LOC", "01"), offset=["GRP"])
                local_grp_01, local_trn_01 = self.local(ctl_01)
                cmds.parent(local_grp_01, local_trn)
                cmds.parent(node_01, ctl)
            cmds.parent(node, self.controllers_grp)
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            
            cmds.matchTransform(node[0], loc)

    def get_offset_matrix(self, child, parent):

        """
        Calculate the offset matrix between a child and parent transform in Maya.
        Args:
            child (str): The name of the child transform.
            parent (str): The name of the parent transform. 
        Returns:
            om.MMatrix: The offset matrix that transforms the child into the parent's space.
        """
        child_dag = om.MSelectionList().add(child).getDagPath(0)
        parent_dag = om.MSelectionList().add(parent).getDagPath(0)

        child_world_matrix = child_dag.inclusiveMatrix()
        parent_world_matrix = parent_dag.inclusiveMatrix()
        
        offset_matrix = child_world_matrix * parent_world_matrix.inverse()

        
        return offset_matrix
    


            

