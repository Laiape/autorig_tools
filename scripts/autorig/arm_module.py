import maya.cmds as cmds
from importlib import reload
import os

from utils import data_manager
from utils import guides_manager
from utils import curve_tool

from autorig.utilities import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)

reload(matrix_manager)

class ArmModule(object):

    def __init__(self):

        """
        Initialize the ArmModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):

        """ 
        Create the arm module structure and controllers. Call this method with the side ('L' or 'R') to create the respective arm module.
        Args:
            side (str): The side of the arm ('L' or 'R').

        """
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_armModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_armSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_armControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()

    def lock_attributes(self, ctl, attr):

        """
        Lock specified attributes on the module transform node.
        Args:
            attrs (list): List of attributes to lock.
        """
        if attr == "None":
            attrs = ["scaleX", "scaleY", "scaleZ", "visibility"]
        elif not isinstance(attr, list):
            attrs = [attr]
        for attr in ["scaleX", "scaleY", "scaleZ", "visibility"] + attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def load_guides(self):

        self.arm_chain = guides_manager.get_guides(f"{self.side}_shoulder_JNT")
        cmds.parent(self.arm_chain[0], self.module_trn)
        self.settings_loc = guides_manager.get_guides(f"{self.side}_armSettings_LOC")

    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"])
        # self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"])
        # cmds.matchTransform(self.settings_node[0], self.settings_loc[0], pos=True, rot=True)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        self.pair_blends = []
        self.fk_chain = []
        self.ik_chain = []

        for joint in self.arm_chain:

            pair_blend = cmds.createNode("pairBlend", name=joint.replace("JNT", "PBL"), ss=True)
            cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{pair_blend}.weight")

            cmds.select(clear=True)
            fk_joint = cmds.joint(name=joint.replace("_JNT", "Fk_JNT"))
            cmds.makeIdentity(fk_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)
            cmds.parent(fk_joint, self.module_trn)

            cmds.select(clear=True)
            ik_joint = cmds.joint(name=joint.replace("_JNT", "Ik_JNT"))
            cmds.matchTransform(ik_joint, joint, pos=True, rot=True)
            cmds.makeIdentity(ik_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)

            if self.ik_chain:
                cmds.parent(ik_joint, self.ik_chain[-1])

            self.fk_chain.append(fk_joint)
            self.ik_chain.append(ik_joint)
            self.pair_blends.append(pair_blend)

            cmds.connectAttr(f"{fk_joint}.translate", f"{pair_blend}.inTranslate2")
            cmds.connectAttr(f"{ik_joint}.translate", f"{pair_blend}.inTranslate1")
            cmds.connectAttr(f"{fk_joint}.rotate", f"{pair_blend}.inRotate2")
            cmds.connectAttr(f"{ik_joint}.rotate", f"{pair_blend}.inRotate1")
            cmds.connectAttr(f"{pair_blend}.outTranslate", f"{joint}.translate")
            cmds.connectAttr(f"{pair_blend}.outRotate", f"{joint}.rotate")

        # cmds.parent(self.fk_chain[0], self.module_trn)
        cmds.parent(self.ik_chain[0], self.module_trn)

    def controllers_creation(self):

        """
        Create controllers for the arm module.
        """
        self.fk_nodes = []
        self.fk_controllers = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armFkControllers_GRP", ss=True, p=self.controllers_grp)

        for i, joint in enumerate(self.fk_chain):

            fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", ""), offset=["GRP"]) # create FK controllers
            
            cmds.matchTransform(fk_node[0], self.arm_chain[i], pos=True, rot=True)

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            if i == 0:
                matrix_manager.fk_constraint(joint, "None", self.pair_blends[i])
            else:
                matrix_manager.fk_constraint(joint, self.fk_chain[i-1], self.pair_blends[i])

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)


        self.ik_controllers = []
        self.ik_controllers = []

        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armIkControllers_GRP", ss=True, p=self.controllers_grp)

        self.ik_wrist_nodes, self.ik_wrist_ctl = curve_tool.create_controller(name=f"{self.side}_armIkWrist", offset=["GRP", "SPC"])
        cmds.parent(self.ik_wrist_nodes[0], ik_controllers_trn)
        cmds.matchTransform(self.ik_wrist_nodes[0], self.arm_chain[-1], pos=True, rot=True)

        reverse_node = cmds.createNode("reverse", name=f"{self.side}_armIkFK_REV", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{ik_controllers_trn}.visibility")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{fk_controllers_trn}.visibility")

