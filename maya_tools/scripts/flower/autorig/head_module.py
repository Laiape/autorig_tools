"""Flower head attachment and settings, with its own module and skin groups."""
from maya import cmds
from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs
from . import common


class HeadModule(object):
    def __init__(self):
        self.modules = data_manager.DataExportBiped().get_data('basic_structure', 'modules_GRP')
        self.skel_grp = data_manager.DataExportBiped().get_data('basic_structure', 'skel_GRP')
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data('basic_structure', 'masterwalk_ctl')

    @organize_module_nurbs
    def make(self, side, entry, guides, stem):
        self.side, self.entry, self.guides, self.stem = side, entry, guides, stem
        self.module_name = side+'_flowerHead'
        self.module_trn = cmds.createNode('transform', name=self.module_name+'Module_GRP', parent=self.modules, skipSelect=True)
        self.skeleton_grp = cmds.createNode('transform', name=self.module_name+'Skinning_GRP', parent=self.skel_grp, skipSelect=True)
        self.controllers_grp = cmds.createNode('transform', name=self.module_name+'Controllers_GRP', parent=self.masterwalk_ctl, skipSelect=True)
        self.load_guides()
        self.controllers_creation()
        self.attachment_setup()
        self.settings_setup()
        self.export_data()
        return self.result

    def load_guides(self):
        self.guide_matrix = self.guides[self.entry['guide']]['joint_matrix']

    def controllers_creation(self):
        self.offsets, self.head_ctl = common.control(self.module_name, self.guide_matrix, self.controllers_grp,
                                                    radius=2.1, color=17, translate=True)
        if not cmds.attributeQuery('autorigTemplateShape', node=self.head_ctl, exists=True):
            cmds.rotate(0, 0, 90, self.head_ctl+'.cv[*]', relative=True, objectSpace=True)
        self.head_joint = common.joint(self.module_name+'Skinning_JNT', self.head_ctl, self.skeleton_grp)

    def attachment_setup(self):
        reference = common.attachment(self.module_name+'Attach_REF', self.guide_matrix,
                                      self.stem['controls'][-1], self.module_trn)
        common.follow(self.offsets[0], reference)
        self.world = cmds.createNode('transform', name='C_flowerWorld_REF', parent=self.module_trn, skipSelect=True)
        cmds.setAttr(self.world+'.inheritsTransform', 0)

    def settings_setup(self):
        for attr in ('petalCurl', 'petalSpread', 'petalTwist'):
            common.number(self.head_ctl, attr)
        for attr in ('showPetalDetails', 'showLeafDetails'):
            cmds.addAttr(self.head_ctl, longName=attr, attributeType='bool', defaultValue=False, keyable=False)
            cmds.setAttr(self.head_ctl+'.'+attr, channelBox=True)
        self.result = {'control': self.head_ctl, 'joint': self.head_joint, 'world': self.world,
                       'module': self.module_trn, 'skeleton_grp': self.skeleton_grp,
                       'controllers_grp': self.controllers_grp}

    def export_data(self):
        data_manager.DataExportBiped().append_data('flower_head_module', {
            'head_ctl': self.head_ctl, 'head_JNT': self.head_joint, 'module_GRP': self.module_trn,
            'skinning_GRP': self.skeleton_grp, 'controllers_GRP': self.controllers_grp})
