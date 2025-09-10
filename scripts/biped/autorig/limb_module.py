import maya.cmds as cmds
import maya.api.OpenMaya as om
import os
from importlib import reload
from scripts.utils import data_manager
from scripts.utils import guides_manager_new
from scripts.utils import curve_tool

reload(data_manager)
reload(guides_manager_new)
reload(curve_tool)

class LimbModule(object):

    def __init__(self):

        self.complete_path = os.path.realpath(__file__)
        self.relative_path = self.complete_path.split("\scripts")[0]
        self.guides_path = os.path.join(self.relative_path, "guides", "character_guides.guides")
        self.curves_path = os.path.join(self.relative_path, "curves", "curves.json")

        self.modules = data_manager.DataExport().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExport().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExport().get_data("basic_structure", "masterwalk_ctl")


        self.module = "limb"
        self.limb_chain = []

    def make(self, side):

        self.side = side

        self.module_trn = cmds.createNode("transform", name=f"{self.side}_{self.module}Module_GRP", ss=True, p=self.modules)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_{self.module}Controllers_GRP", ss=True, p=self.masterwalk_ctl)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_{self.module}Skinning_GRP", ss=True, p=self.skel_grp)

        self.blend_chains()

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def blend_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        self.pair_blends = []
        self.fk_chain = []
        self.ik_chain = []

        for joint in self.limb_chain:

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

        cmds.parent(self.ik_chain[0], self.module_trn)


class ArmModule(LimbModule):

    def __init__(self):

        super(ArmModule, self).__init__()
                 
    def make(self, side):

        self.side = side
        self.module = "arm"

        self.load_guides()

        super(ArmModule, self).make(side)
  

    def load_guides(self):

        """
        Load guides from arm
        """

        self.limb_chain = guides_manager_new.get_guides(joint_name=f"{self.side}_shoulder_JNT")
        self.settings_loc = guides_manager_new.get_guides(joint_name=f"{self.side}_armSettings_LOC")[0]
        

class LegModule(LimbModule):

    def make(self, side):

        self.side = side
        self.module = "leg"
        super(LegModule, self).make(side)

    def load_guides(self):

        """
        Load guides from leg
        """

        self.limb_chain = guides_manager_new.get_guides(joint_name=f"{self.side}_hip_JNT")
        self.settings_loc = guides_manager_new.get_guides(joint_name=f"{self.side}_legSettings_LOC")[0]
