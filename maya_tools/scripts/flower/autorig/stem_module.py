"""FK stem module using the shared Autorig module/skin/controller layout."""
from maya import cmds
from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs
from . import common


class StemModule(object):
    def __init__(self):
        self.modules = data_manager.DataExportBiped().get_data('basic_structure', 'modules_GRP')
        self.skel_grp = data_manager.DataExportBiped().get_data('basic_structure', 'skel_GRP')
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data('basic_structure', 'masterwalk_ctl')

    @organize_module_nurbs
    def make(self, side, entry, guides):
        self.side = side
        self.entry = entry
        self.guides = guides
        self.module_name = side+'_stem'
        self.module_trn = cmds.createNode('transform', name=self.module_name+'Module_GRP', parent=self.modules, skipSelect=True)
        self.skeleton_grp = cmds.createNode('transform', name=self.module_name+'Skinning_GRP', parent=self.skel_grp, skipSelect=True)
        self.controllers_grp = cmds.createNode('transform', name=self.module_name+'Controllers_GRP', parent=self.masterwalk_ctl, skipSelect=True)
        self.load_guides()
        self.controllers_creation()
        self.fk_setup()
        self.export_data()
        return self.result

    def load_guides(self):
        self.guide_matrices = [self.guides[name]['joint_matrix'] for name in self.entry['guides']]

    def controllers_creation(self):
        self.result = common.chain(self.entry, self.guides, self.controllers_grp, self.skeleton_grp, radius=0.65, color=14)

    def fk_setup(self):
        root = common.attachment(self.module_name+'Root_REF', self.guide_matrices[0], self.masterwalk_ctl, self.module_trn)
        common.follow(self.result['groups'][0][0], root)
        self.result.update(module=self.module_trn, skeleton_grp=self.skeleton_grp, controllers_grp=self.controllers_grp)

    def export_data(self):
        data_manager.DataExportBiped().append_data('stem_module', {
            'stem_ctl': self.result['controls'][0], 'stem_end_ctl': self.result['controls'][-1],
            'skinningJoints': self.result['joints'], 'module_GRP': self.module_trn,
            'skinning_GRP': self.skeleton_grp, 'controllers_GRP': self.controllers_grp})
