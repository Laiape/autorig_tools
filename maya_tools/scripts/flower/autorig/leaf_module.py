"""One native Autorig module per leaf, attached to its authored stem anchor."""
from maya import cmds
from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs
from . import common


class LeafModule(object):
    def __init__(self):
        self.modules = data_manager.DataExportBiped().get_data('basic_structure', 'modules_GRP')
        self.skel_grp = data_manager.DataExportBiped().get_data('basic_structure', 'skel_GRP')
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data('basic_structure', 'masterwalk_ctl')

    @organize_module_nurbs
    def make(self, side, entry, guides, stem, head):
        self.side, self.entry, self.guides = side, entry, guides
        self.stem, self.head = stem, head
        self.module_name = entry['prefix']
        self.module_trn = cmds.createNode('transform', name=self.module_name+'Module_GRP', parent=self.modules, skipSelect=True)
        self.skeleton_grp = cmds.createNode('transform', name=self.module_name+'Skinning_GRP', parent=self.skel_grp, skipSelect=True)
        self.controllers_grp = cmds.createNode('transform', name=self.module_name+'Controllers_GRP', parent=self.masterwalk_ctl, skipSelect=True)
        self.load_guides()
        self.controllers_creation()
        self.attachment_setup()
        self.curl_setup()
        self.export_data()
        return self.result

    def load_guides(self):
        self.guide_matrices = [self.guides[name]['joint_matrix'] for name in self.entry['guides']]

    def controllers_creation(self):
        self.result = common.chain(self.entry, self.guides, self.controllers_grp, self.skeleton_grp, radius=0.42, color=18)
        start, end = self.guide_matrices[0][12:15], self.guide_matrices[-1][12:15]
        common.raised_drawing(self.result['controls'][0], sum((a-b)**2 for a,b in zip(start, end))**0.5)

    def attachment_setup(self):
        reference = common.attachment(self.module_name+'Attach_REF', self.guide_matrices[0],
                                      self.stem['controls'][self.entry['attachment']], self.module_trn)
        common.follow(self.result['groups'][0][0], reference)
        self.result.update(module=self.module_trn, skeleton_grp=self.skeleton_grp, controllers_grp=self.controllers_grp)

    def curl_setup(self):
        root = self.result['controls'][0]
        common.number(root, 'curl')
        for index in range(1, len(self.result['controls'])):
            common.add_rotation(self.module_name+'Curl%02d' % index, [root+'.curl'],
                                self.result['groups'][index][1]+'.rotateZ', multiplier=0.5)
            for shape in cmds.listRelatives(self.result['controls'][index], shapes=True):
                cmds.connectAttr(self.head['control']+'.showLeafDetails', shape+'.visibility')

    def export_data(self):
        data_manager.DataExportBiped().append_data('leaf_module', {
            self.module_name+'_ctl': self.result['controls'][0],
            self.module_name+'_skinningJoints': self.result['joints'],
            self.module_name+'_module_GRP': self.module_trn,
            self.module_name+'_skinning_GRP': self.skeleton_grp,
            self.module_name+'_controllers_GRP': self.controllers_grp})
