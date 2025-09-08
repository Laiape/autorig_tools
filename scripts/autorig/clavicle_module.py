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

        data_manager.DataExport().append_data("clavicle_module",
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

    def auto_clavicle_setup(self):

        cmds.select(clear=True)
        shoulder = data_manager.DataExport().get_data("arm_module", f"{self.side}_shoulder_JNT")
        armIk = data_manager.DataExport().get_data("arm_module", f"{self.side}_armIk") 
        ctl_switch = data_manager.DataExport().get_data("arm_module", f"{self.side}_armSettings") 
        spine_joints = data_manager.DataExport().get_data("spine_module", "last_spine_jnt") 
        local_chest = data_manager.DataExport().get_data("spine_module", "local_chest_ctl")
        body = data_manager.DataExport().get_data("spine_module", "body_ctl")

        # cmds.scaleConstraint(self.masterwalk_ctl, self.module_trn, mo=True)
        
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

        # ik_pos = cmds.xform(self.clavicle_joint, q=True, ws=True, t=True)
        # armIk_pos = cmds.xform(shoulder, q=True, ws=True, t=True)
        # distance = ((ik_pos[0] - armIk_pos[0]) ** 2 + (ik_pos[1] - armIk_pos[1]) ** 2 + (ik_pos[2] - armIk_pos[2]) ** 2) ** 0.5
        # shoulder_matrix = cmds.getAttr(f"{shoulder}.worldMatrix")
        

        # sphere = cmds.sphere(name=f'{self.side}_armAutoClavicleSlide_NRB', radius=distance, sections=4, startSweep=160)[0]
        # cmds.delete(sphere, ch=True)
        # cmds.parent(sphere, self.module_trn)
        # cmds.matchTransform(sphere, self.clavicle_joint, rotation=False)
        # if self.side == "L":
        #     cmds.rotate(-90,-90,0, sphere)
        # elif self.side == "R":
        #     cmds.rotate(-90,90,0, sphere)
        
        # cmds.select(clear=True)
        # locator = cmds.spaceLocator(name=f'{self.side}_armAutoClavicleSlide_LOC')
        # cmds.geometryConstraint(sphere, locator)
        # float_constant_freeze = cmds.createNode("floatConstant", name=f"{self.side}_armAutoClavicleSlide_FCF")
        # cmds.setAttr(f"{float_constant_freeze}.inFloat", 0.0)
        # cmds.connectAttr(f"{float_constant_freeze}.outFloat", f"{locator[0]}.translateX")
        # cmds.connectAttr(f"{float_constant_freeze}.outFloat", f"{locator[0]}.translateY")
        # cmds.connectAttr(f"{float_constant_freeze}.outFloat", f"{locator[0]}.translateZ")
        # cmds.parent(locator, self.module_trn)
        
        # dupe = cmds.spaceLocator(name=f'{self.side}_armAutoClavicleSlideReduced_LOC')
        # parent_matrix = cmds.createNode("parentMatrix", name=f"{self.side}_armAutoClavicleSlideReduced_PMA")

        # cmds.setAttr(f"{parent_matrix}.inputMatrix", shoulder_matrix, type="matrix")
        # cmds.connectAttr(f"{armIk}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        # offset_m = self.get_offset_matrix(shoulder, armIk)
        # cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", offset_m, type="matrix")
        # pick_matrix = cmds.createNode("pickMatrix", name=f"{self.side}_armAutoClavicleSlideReduced_PMX")
        # cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{pick_matrix}.inputMatrix")
        # cmds.setAttr(f"{pick_matrix}.useRotate", 0) # Filter translation
        # cmds.setAttr(f"{pick_matrix}.useScale", 0) 
        # cmds.setAttr(f"{pick_matrix}.useShear", 0)
        # cmds.connectAttr(f"{pick_matrix}.outputMatrix", f"{locator[0]}.offsetParentMatrix")

        
        # offset=cmds.createNode("transform", name=f"{self.side}_armAutoClavicleSlide_OFF",  p=self.module_trn)
        # cmds.matchTransform(offset, shoulder, position=True, rotation=False)
        # cmds.parent(dupe, offset)
        # # cmds.matchTransform(dupe, shoulder, position=True, rotation=False)

        # parent_matrix_reduced = cmds.createNode("blendMatrix", name=f"{self.side}_armAutoClavicleSlideReduced_BMX")
        # cmds.connectAttr(f"{locator[0]}.worldMatrix[0]", f"{parent_matrix_reduced}.inputMatrix")
        # cmds.connectAttr(f"{offset}.worldMatrix[0]", f"{parent_matrix_reduced}.target[1].targetMatrix")
        # cmds.setAttr(f"{parent_matrix_reduced}.target[1].weight", 0.8)
        # offset_mult_matrix  = cmds.createNode("multMatrix", name=f"{self.side}_armAutoClavicleSlide_MMX")
        # cmds.connectAttr(f"{parent_matrix_reduced}.outputMatrix", f"{offset_mult_matrix}.matrixIn[0]")
        # cmds.connectAttr(f"{offset}.worldInverseMatrix[0]", f"{offset_mult_matrix}.matrixIn[1]")
        # cmds.connectAttr(f"{offset_mult_matrix}.matrixSum", f"{dupe[0]}.offsetParentMatrix")

        # aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_armAutoClavicleSlide_AIM")
        # cmds.connectAttr(f"{dupe[0]}.worldMatrix[0]", f"{aim_matrix}.inputMatrix")
        # cmds.connectAttr(f"{spine_joints}.worldMatrix[0]", f"{aim_matrix}.primaryTargetMatrix")
        # cmds.setAttr(f"{aim_matrix}.primaryInputAxisX", 1)
        # cmds.setAttr(f"{aim_matrix}.primaryInputAxisY", 0)
        # cmds.setAttr(f"{aim_matrix}.primaryInputAxisZ", 0)
        # cmds.setAttr(f"{aim_matrix}.secondaryInputAxisX", 0)
        # cmds.setAttr(f"{aim_matrix}.secondaryInputAxisY", 0)
        # cmds.setAttr(f"{aim_matrix}.secondaryInputAxisZ", 1)
        # cmds.setAttr(f"{aim_matrix}.primaryMode", 1) # Aim
        # cmds.setAttr(f"{aim_matrix}.secondaryMode", 2) # World Up
        # cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{created_grps[1]}.offsetParentMatrix") # ctl offset grp

        # cmds.addAttr(ctl_switch, shortName="autoClavicleIk", niceName="Auto Clavicle Ik", maxValue=1, minValue=0,defaultValue=0, keyable=True)
        # cmds.connectAttr(f"{ctl_switch}.autoClavicleIk", f"{aim_matrix}.envelope")

        # # cmds.connectAttr(f"{ctl_switch}.autoClavicleIk", f"{aim[0]}.{dupe[0]}W0")

        # # # cmds.parent(shoulder, self.clavicle_joint)
        # cmds.hide(sphere)
        # cmds.delete(shoulder)