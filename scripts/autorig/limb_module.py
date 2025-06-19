import maya.cmds as cmds
import maya.api.OpenMaya as om
import os
from importlib import reload
from scripts.utils import data_export
from scripts.utils import guides_manager
from scripts.utils import curve_tool

reload(data_export)
reload(guides_manager)
reload(curve_tool)

class LimbModule(object):

    def __init__(self):

        self.complete_path = os.path.realpath(__file__)
        self.relative_path = self.complete_path.split("\scripts")[0]
        self.guides_path = os.path.join(self.relative_path, "guides", "character_guides.guides")
        self.curves_path = os.path.join(self.relative_path, "curves", "arm_ctl.json")

        self.data_exporter = data_export.DataExport()

        self.modules_grp = self.data_exporter.get_data("basic_structure", "modules_GRP")
        self.skel_grp = self.data_exporter.get_data("basic_structure", "skel_GRP")
        self.masterWalk_ctl = self.data_exporter.get_data("basic_structure", "masterWalk_CTL")

        self.module = "Limb"

    def make(self, side):

        self.side = side

        self.module_trn = cmds.createNode("transform", name=f"{self.side}_{self.module}Module_GRP", ss=True, p=self.modules_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_{self.module}Controllers_GRP", ss=True, p=self.masterWalk_ctl)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_{self.module}Skinning_GRP", ss=True, p=self.skel_grp)


    def blend_chains(guides):

        fk_chain = []
        ik_chain = []
        blend_chain = []
        names = ["Fk", "Ik", "Blend"]



class ArmModule(LimbModule):

    def __init__(self):

        super(ArmModule, self).__init__()
                 
    def make(self, side):

        self.side = side

        self.module = "arm"
        super(ArmModule, self).make(side)

        

    def load_guides(self):

        self.arm_chain = guides_manager.guide_import(joint_name=f"{self.side}_shoulder_JNT", all_descendents=True, filePath=self.guides_path)
        


class LegModule(LimbModule):

    def make(self, side):

        self.side = side


    def load_guides(self):

        pass
