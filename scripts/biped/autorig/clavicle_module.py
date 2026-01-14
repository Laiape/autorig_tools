import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from biped.utils import data_manager
from biped.utils import guides_manager
from biped.utils import curve_tool

from biped.autorig.utilities import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)

class ClavicleModule(object):

    def __init__(self):

        """
        Initialize the clavicleModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the clavicle module structure and controllers. Call this method with the side ('L' or 'R') to create the respective clavicle module.
        Args:
            side (str): The side of the clavicle ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_clavicleModule_GRP", ss=True, p=self.modules)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleX")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleY")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleZ")
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_clavicleSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_clavicleControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.clavicle_setup()

        data_manager.DataExportBiped().append_data("clavicle_module",
                            {
                                f"{self.side}_clavicle": self.ctl_ik
                            })


    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

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
    
    def load_guides(self):

        """
        Load clavicle joint guides and parent it to the module transform.
        """

        self.clavicle_joint = guides_manager.get_guides(f"{self.side}_clavicle_JNT")
       
        cmds.parent(self.clavicle_joint, self.module_trn)

    def clavicle_setup(self):

        cmds.select(clear=True)
        
        created_grps, self.ctl_ik = curve_tool.create_controller(f"{self.side}_clavicle", ["GRP", "OFF"])
        cmds.parent(created_grps[0], self.controllers_grp)
        cmds.matchTransform(created_grps[0], self.clavicle_joint)
        cmds.connectAttr(f"{self.ctl_ik}.worldMatrix[0]", f"{self.clavicle_joint[0]}.offsetParentMatrix")

        self.lock_attributes(self.ctl_ik, [ "sx", "sy", "sz", "v"])
        cmds.setAttr(f"{self.clavicle_joint[0]}.translateX", 0)
        cmds.setAttr(f"{self.clavicle_joint[0]}.translateY", 0)
        cmds.setAttr(f"{self.clavicle_joint[0]}.translateZ", 0)

        cmds.select(clear=True)
        clavicle_skinning = cmds.joint(name=f"{self.side}_clavicleSkinning_JNT")
        cmds.makeIdentity(clavicle_skinning, apply=True, t=1, r=1, s=1, n=0)
        cmds.parent(clavicle_skinning, self.skeleton_grp)
        cmds.connectAttr(f"{self.ctl_ik}.worldMatrix[0]", f"{clavicle_skinning}.offsetParentMatrix")
        cmds.setAttr(f"{self.clavicle_joint[0]}.inheritsTransform", 0)

        # Clean up
        cmds.delete(self.clavicle_joint)