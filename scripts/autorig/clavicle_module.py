import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool

from autorig.utilities import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)

class ClavicleModule(object):

    def __init__(self):

        """
        Initialize the clavicleModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

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
        self.auto_clavicle_setup()


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

        """
        Load clavicle joint guides and parent it to the module transform.
        """

        self.clavicle_joint = guides_manager.get_guides(f"{self.side}_clavicle_JNT")
        cmds.parent(self.clavicle_joint, self.module_trn)

    def auto_clavicle_setup(self):

        cmds.select(clear=True)
        shoulder = data_manager.DataExport().get_data("arm_module", f"{self.side}_shoulder_JNT")
        armIk = data_manager.DataExport().get_data("arm_module", f"{self.side}_armIk") 
        ctl_switch = data_manager.DataExport().get_data("arm_module", f"{self.side}_armSettings") 
        spine_joints = data_manager.DataExport().get_data("spine_module", "last_spine_jnt") 

        cmds.parentConstraint(spine_joints, self.module_trn, mo=True)
        # cmds.scaleConstraint(self.masterwalk_ctl, self.module_trn, mo=True)
        
        created_grps, self.ctl_ik = curve_tool.create_controller(f"{self.side}_clavicle", ["GRP", "OFF"])
        cmds.parent(created_grps[0], self.controllers_grp)
        cmds.matchTransform(created_grps[0], self.clavicle_joint)
        cmds.parentConstraint(self.ctl_ik, self.clavicle_joint, mo=False)
        self.lock_attributes(self.ctl_ik, [ "sx", "sy", "sz", "v"])


        ik_pos = cmds.xform(self.clavicle_joint, q=True, ws=True, t=True)
        armIk_pos = cmds.xform(shoulder, q=True, ws=True, t=True)
        distance = ((ik_pos[0] - armIk_pos[0]) ** 2 + (ik_pos[1] - armIk_pos[1]) ** 2 + (ik_pos[2] - armIk_pos[2]) ** 2) ** 0.5

        sphere = cmds.sphere(name=f'{self.side}_armAutoClavicleSlide_NRB', radius=distance, sections=4, startSweep=160)[0]
        cmds.delete(sphere, ch=True)
        cmds.parent(sphere, self.module_trn)
        cmds.matchTransform(sphere, self.clavicle_joint, rotation=False)
        if self.side == "L":
            cmds.rotate(-90,-90,0, sphere)
        elif self.side == "R":
            cmds.rotate(-90,90,0, sphere)
        
        locator = cmds.spaceLocator(name=f'{self.side}_armAutoClavicleSlide_LOC')
        cmds.parent(locator, self.module_trn)
        cmds.matchTransform(locator, shoulder, rotation=False)
        
        dupe = cmds.duplicate(locator, name=f'{self.side}_armAutoClavicleSlideReduced_LOC')
        cmds.pointConstraint(armIk, locator)
        cmds.geometryConstraint(sphere, locator)
        offset=cmds.createNode("transform", name=f"{self.side}_armAutoClavicleSlide_OFF")
        cmds.parent(offset, self.module_trn)
        cmds.matchTransform(offset, shoulder, rotation=False)
        cmds.parent(dupe, offset)
        constraint = cmds.parentConstraint(locator, offset, dupe, mo=True)
        cmds.setAttr(f"{constraint[0]}.{locator[0]}W0", 0.8)
        cmds.setAttr(f"{constraint[0]}.{offset}W1", 0.2)
        aim = cmds.aimConstraint(dupe, created_grps[1], aimVector=(1,0,0), upVector=(0,0,1), maintainOffset=True, worldUpType="objectrotation", worldUpVector=(0,0,1), wuo=spine_joints)

        cmds.addAttr(ctl_switch, shortName="autoClavicleIk", niceName="Auto Clavicle Ik", maxValue=1, minValue=0,defaultValue=0, keyable=True)

        cmds.connectAttr(f"{ctl_switch}.autoClavicleIk", f"{aim[0]}.{dupe[0]}W0")

        # cmds.parent(shoulder, self.clavicle_joint)
        cmds.hide(sphere)
        # cmds.delete(shoulder)