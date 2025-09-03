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

class FingersModule(object):

    def __init__(self):

        """
        Initialize the fingersModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")
        

    def make(self, side):

        """ 
        Create the fingers module structure and controllers. Call this method with the side ('L' or 'R') to create the respective fingers module.
        Args:
            side (str): The side of the fingers ('L' or 'R').

        """
        self.side = side
        self.wrist_jnt = data_manager.DataExport().get_data("arm_module", f"{self.side}_wrist_JNT")
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_fingersModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_fingersSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_fingersControllers_GRP", ss=True, p=self.masterwalk_ctl)
        cmds.setAttr(f"{self.controllers_grp}.inheritsTransform", 0)

        self.load_guides()
        # self.create_finger_blends()
        self.fk_fingers()
        self.parent_fingers_to_wrist()
        self.attributes_setup()

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
        self.thumb = guides_manager.get_guides(f"{self.side}_thumb00_JNT")
        cmds.parent(self.thumb[0], self.module_trn)
        cmds.select(clear=True)
        self.index = guides_manager.get_guides(f"{self.side}_index00_JNT")
        cmds.parent(self.index[0], self.module_trn)
        cmds.select(clear=True)
        self.middle = guides_manager.get_guides(f"{self.side}_middle00_JNT")
        cmds.parent(self.middle[0], self.module_trn)
        cmds.select(clear=True)
        self.ring = guides_manager.get_guides(f"{self.side}_ring00_JNT")
        cmds.parent(self.ring[0], self.module_trn)
        cmds.select(clear=True)
        self.pinky = guides_manager.get_guides(f"{self.side}_pinky00_JNT")
        cmds.parent(self.pinky[0], self.module_trn)
        cmds.select(clear=True)

        self.fingers = [self.thumb, self.index, self.middle, self.ring, self.pinky]

    def create_finger_blends(self):

        fk_finger_joints_trn = cmds.createNode("transform", name=f"{self.side}_fkFingersJoints_GRP", ss=True, p=self.module_trn)
        ik_finger_joints_trn = cmds.createNode("transform", name=f"{self.side}_ikFingersJoints_GRP", ss=True, p=self.module_trn)

        self.fk_chain = []
        self.ik_chain = []

        for finger in self.fingers:
                
            for joint in finger:

                cmds.select(clear=True)
                fk_joint = cmds.joint(name=joint.replace("_JNT", "Fk_JNT"))
                cmds.makeIdentity(fk_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)

                cmds.select(clear=True)
                ik_joint = cmds.joint(name=joint.replace("_JNT", "Ik_JNT"))
                cmds.matchTransform(ik_joint, joint, pos=True, rot=True)
                cmds.makeIdentity(ik_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)

                if self.ik_chain:
                    if "*End*" not in self.ik_chain[-1]:
                        cmds.parent(ik_joint, self.ik_chain[-1])
                    else:
                        cmds.parent(ik_joint, ik_finger_joints_trn)

                if self.fk_chain:
                    if "*End*" not in self.fk_chain[-1]:
                        cmds.parent(fk_joint, self.fk_chain[-1])
                    else:
                        cmds.parent(fk_joint, fk_finger_joints_trn)

                self.fk_chain.append(fk_joint)
                self.ik_chain.append(ik_joint)


            cmds.parent(self.ik_chain[0], ik_finger_joints_trn)
            cmds.parent(self.fk_chain[0], fk_finger_joints_trn)

    def fk_fingers(self):

        self.fk_thumb_nodes = []
        self.fk_index_nodes = []
        self.fk_middle_nodes = []
        self.fk_ring_nodes = []
        self.fk_pinky_nodes = []
        self.fk_thumb_sdk = []
        self.fk_index_sdk = []
        self.fk_middle_sdk = []
        self.fk_ring_sdk = []
        self.fk_pinky_sdk = []
        self.fk_thumb_ctl = []
        self.fk_index_ctl = []
        self.fk_middle_ctl = []
        self.fk_ring_ctl = []
        self.fk_pinky_ctl = []
        self.skinning_jnts = []

        thumb_skinning_trn = cmds.createNode("transform", name=f"{self.side}_thumbSkinning_GRP", ss=True, p=self.skeleton_grp)
        index_skinning_trn = cmds.createNode("transform", name=f"{self.side}_indexSkinning_GRP", ss=True, p=self.skeleton_grp)
        middle_skinning_trn = cmds.createNode("transform", name=f"{self.side}_middleSkinning_GRP", ss=True, p=self.skeleton_grp)
        ring_skinning_trn = cmds.createNode("transform", name=f"{self.side}_ringSkinning_GRP", ss=True, p=self.skeleton_grp)
        pinky_skinning_trn = cmds.createNode("transform", name=f"{self.side}_pinkySkinning_GRP", ss=True, p=self.skeleton_grp)

        for finger in self.fingers:

            for i, joint in enumerate(finger):

                if "End" not in joint:
                    
                    cmds.select(clear=True)
                    skinning_jnt = cmds.joint(name=joint.replace("_JNT", "Skinning_JNT"))
                    cmds.connectAttr(f"{joint}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")

                    fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", ""), offset=["GRP", "SDK"])
                    cmds.matchTransform(fk_node[0], joint, pos=True, rot=True)
                    # cmds.setAttr(f"{fk_node[0]}.inheritsTransform", 0)
                    if "thumb" in joint:
                        if self.fk_thumb_ctl:
                            cmds.parent(fk_node[0], self.fk_thumb_ctl[-1])  
                            # cmds.parent(skinning_jnt, self.skinning_jnts[-1])
                        cmds.parent(skinning_jnt, thumb_skinning_trn)

                        self.fk_thumb_ctl.append(fk_ctl)
                        self.fk_thumb_nodes.append(fk_node[0])
                        self.fk_thumb_sdk.append(fk_node[1])
                    elif "index" in joint:
                        if self.fk_index_ctl:
                            cmds.parent(fk_node[0], self.fk_index_ctl[-1])

                        cmds.parent(skinning_jnt, index_skinning_trn)
                        self.fk_index_ctl.append(fk_ctl)
                        self.fk_index_nodes.append(fk_node[0])
                        self.fk_index_sdk.append(fk_node[1])
                    elif "middle" in joint:
                        if self.fk_middle_ctl:
                            cmds.parent(fk_node[0], self.fk_middle_ctl[-1])

                        cmds.parent(skinning_jnt, middle_skinning_trn)
                        self.fk_middle_ctl.append(fk_ctl)
                        self.fk_middle_nodes.append(fk_node[0])
                        self.fk_middle_sdk.append(fk_node[1])

                    elif "ring" in joint:
                        if self.fk_ring_ctl:
                            cmds.parent(fk_node[0], self.fk_ring_ctl[-1])

                        cmds.parent(skinning_jnt, ring_skinning_trn)
                        self.fk_ring_ctl.append(fk_ctl)
                        self.fk_ring_nodes.append(fk_node[0])
                        self.fk_ring_sdk.append(fk_node[1])

                    elif "pinky" in joint:
                        if self.fk_pinky_ctl:
                            cmds.parent(fk_node[0], self.fk_pinky_ctl[-1])

                        cmds.parent(skinning_jnt, pinky_skinning_trn)
                        self.fk_pinky_ctl.append(fk_ctl)
                        self.fk_pinky_nodes.append(fk_node[0])
                        self.fk_pinky_sdk.append(fk_node[1])

                    if i == 0:
                        matrix_manager.fk_constraint(joint, None, False, None)
                    else:
                        matrix_manager.fk_constraint(joint, finger[i - 1], False, None)

                    self.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
                    cmds.xform(joint, m=om.MMatrix.kIdentity)
            

        cmds.parent(self.fk_thumb_nodes[0], self.controllers_grp)
        cmds.parent(self.fk_index_nodes[0], self.controllers_grp)
        cmds.parent(self.fk_middle_nodes[0], self.controllers_grp)
        cmds.parent(self.fk_ring_nodes[0], self.controllers_grp)
        cmds.parent(self.fk_pinky_nodes[0], self.controllers_grp)

        self.finger_attributes_nodes, self.finger_attributes_ctl = curve_tool.create_controller(name=f"{self.side}_fingersAttributes", offset=["GRP"])
        cmds.parent(self.finger_attributes_nodes[0], self.controllers_grp)
        point_temp = cmds.pointConstraint(self.fk_middle_ctl[0], self.fk_middle_ctl[1], self.finger_attributes_nodes[0], mo=False)
        cmds.delete(point_temp)
        self.lock_attributes(self.finger_attributes_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])

    

    def parent_fingers_to_wrist(self):

        """
        Parent the finger controllers to the wrist controller.
        """
        

        for finger in [self.fk_thumb_nodes[0], self.fk_index_nodes[0], self.fk_middle_nodes[0], self.fk_ring_nodes[0], self.fk_pinky_nodes[0], self.finger_attributes_nodes[0]]:

            cmds.select(clear=True)
            temp_locator = cmds.spaceLocator(name=finger.replace("GRP", "LOC"))[0]
            cmds.matchTransform(temp_locator, finger, pos=True, rot=True)
            parent_matrix = cmds.createNode("parentMatrix", name=finger.replace("GRP", "PM"), ss=True)
            cmds.connectAttr(f"{temp_locator}.worldMatrix[0]", f"{parent_matrix}.inputMatrix")
            cmds.connectAttr(f"{self.wrist_jnt}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
            offset_matrix = self.get_offset_matrix(finger, self.wrist_jnt)
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", offset_matrix, type="matrix")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{finger}.offsetParentMatrix")

            cmds.xform(finger, m=om.MMatrix.kIdentity)
            cmds.delete(temp_locator)

    def attributes_setup(self):

        
        cmds.addAttr(self.finger_attributes_ctl, longName="CURL", attributeType="float", defaultValue=0, max=10, min=-10, keyable=True)
        cmds.addAttr(self.finger_attributes_ctl, longName="SPREAD", attributeType="float", defaultValue=0, max=10, min=-10, keyable=True)
        cmds.addAttr(self.finger_attributes_ctl, longName="TWIST", attributeType="float", defaultValue=0, max=10, min=-10, keyable=True)
        cmds.addAttr(self.finger_attributes_ctl, longName="FAN", attributeType="float", defaultValue=0, max=10, min=-10, keyable=True)


        self.fingers_attributes_callback(self.fk_thumb_nodes[0], values=[0,0,0,0,0,0, 10, -10])
        self.fingers_attributes_callback(self.fk_thumb_sdk[1], values=[-90, 20, -20, 20, 20, -20, 0, 0])
        self.fingers_attributes_callback(self.fk_thumb_sdk[2], values=[-80, 18, 0, 0, 10, -10, 0, 0])

        self.fingers_attributes_callback(self.fk_index_nodes[1], values=[-90, 20, -25, 15, 20, -20, 30, -30])
        self.fingers_attributes_callback(self.fk_index_nodes[2], values=[-80, 18, 0, 0, 10, -10, 0, 0])
        self.fingers_attributes_callback(self.fk_index_nodes[3], values=[-80, 15, 0, 0, 5, -5, 0, 0])

        self.fingers_attributes_callback(self.fk_middle_nodes[1], values=[-90, 20, 2, -2, 20, -20, -2, 2])
        self.fingers_attributes_callback(self.fk_middle_nodes[2], values=[-80, 18, 0, 0, 10, -10, 0, 0])
        self.fingers_attributes_callback(self.fk_middle_nodes[3], values=[-80, 15, 0, 0, 5, -5, 0, 0])

        self.fingers_attributes_callback(self.fk_ring_nodes[1], values=[-90, 20, 15, -10, 20, -20, -20, 20])
        self.fingers_attributes_callback(self.fk_ring_nodes[2], values=[-80, 18, 0, 0, 10, -10, 0, 0])
        self.fingers_attributes_callback(self.fk_ring_nodes[3], values=[-80, 15, 0, 0, 5, -5, 0, 0])

        self.fingers_attributes_callback(self.fk_pinky_nodes[1], values=[-90, 20, 30, -15, 20, -20, -50, 50])
        self.fingers_attributes_callback(self.fk_pinky_nodes[2], values=[-80, 18, 0, 0, 10, -10, 0, 0])
        self.fingers_attributes_callback(self.fk_pinky_nodes[3], values=[-80, 15, 0, 0, 5, -5, 0, 0])

    def fingers_attributes_callback(self, ctl, values=[]):

        cmds.select(ctl)
        cmds.setDrivenKeyframe(at="rz", dv=0, cd=f"{self.finger_attributes_ctl}.CURL", v=0)
        cmds.setDrivenKeyframe(at="rz", dv=10, cd=f"{self.finger_attributes_ctl}.CURL", v=values[0])
        cmds.setDrivenKeyframe(at="rz", dv=-10, cd=f"{self.finger_attributes_ctl}.CURL", v=values[1])

        cmds.setDrivenKeyframe(at="ry", dv=0, cd=f"{self.finger_attributes_ctl}.SPREAD", v=0)
        cmds.setDrivenKeyframe(at="ry", dv=10, cd=f"{self.finger_attributes_ctl}.SPREAD", v=values[2])
        cmds.setDrivenKeyframe(at="ry", dv=-10, cd=f"{self.finger_attributes_ctl}.SPREAD", v=values[3])

        cmds.setDrivenKeyframe(at="rx", dv=0, cd=f"{self.finger_attributes_ctl}.TWIST", v=0)
        cmds.setDrivenKeyframe(at="rx", dv=10, cd=f"{self.finger_attributes_ctl}.TWIST", v=values[4])
        cmds.setDrivenKeyframe(at="rx", dv=-10, cd=f"{self.finger_attributes_ctl}.TWIST", v=values[5])

        cmds.setDrivenKeyframe(at="rz", dv=0, cd=f"{self.finger_attributes_ctl}.FAN", v=0)
        cmds.setDrivenKeyframe(at="rz", dv=10, cd=f"{self.finger_attributes_ctl}.FAN", v=values[6])
        cmds.setDrivenKeyframe(at="rz", dv=-10, cd=f"{self.finger_attributes_ctl}.FAN", v=values[7])

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
