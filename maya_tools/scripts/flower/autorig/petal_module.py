"""Shell-specific FK petals and explicitly matched head/world space changes."""
from maya import cmds
from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs
from . import common


class PetalModule(object):
    def __init__(self):
        self.modules = data_manager.DataExportBiped().get_data('basic_structure', 'modules_GRP')
        self.skel_grp = data_manager.DataExportBiped().get_data('basic_structure', 'skel_GRP')
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data('basic_structure', 'masterwalk_ctl')

    @organize_module_nurbs
    def make(self, side, entry, guides, head):
        self.side, self.entry, self.guides, self.head = side, entry, guides, head
        self.module_name = entry['prefix']
        self.module_trn = cmds.createNode('transform', name=self.module_name+'Module_GRP', parent=self.modules, skipSelect=True)
        self.skeleton_grp = cmds.createNode('transform', name=self.module_name+'Skinning_GRP', parent=self.skel_grp, skipSelect=True)
        self.controllers_grp = cmds.createNode('transform', name=self.module_name+'Controllers_GRP', parent=self.masterwalk_ctl, skipSelect=True)
        self.load_guides()
        self.controllers_creation()
        self.space_setup()
        self.curl_setup()
        self.export_data()
        return self.result

    def load_guides(self):
        self.guide_matrices = [self.guides[name]['joint_matrix'] for name in self.entry['guides']]

    def controllers_creation(self):
        color = 18 if self.entry['layer'] == 'A' else 20
        self.result = common.chain(self.entry, self.guides, self.controllers_grp, self.skeleton_grp,
                                   radius=0.30, color=color, free_root=True)
        self.root_ctl = self.result['controls'][0]
        start, end = self.guide_matrices[0][12:15], self.guide_matrices[-1][12:15]
        common.raised_drawing(self.root_ctl, sum((a-b)**2 for a,b in zip(start, end))**0.5,
                              height=0.6 if self.entry['layer'] == 'A' else 0.9)
        cmds.addAttr(self.root_ctl, longName='space', attributeType='enum', enumName='Head:World', keyable=True)
        for attribute in ('curl', 'spread', 'twist'):
            common.number(self.root_ctl, attribute)

    def space_setup(self):
        group = self.result['groups'][0][0]
        rest = cmds.xform(group, query=True, worldSpace=True, matrix=True)
        cmds.setAttr(group+'.offsetParentMatrix', 1, 0, 0, 0, 0, 1, 0, 0,
                     0, 0, 1, 0, 0, 0, 0, 1, type='matrix')
        cmds.xform(group, worldSpace=True, matrix=rest)
        parent = cmds.parentConstraint(self.head['control'], self.head['world'], group, maintainOffset=True)[0]
        scale = cmds.scaleConstraint(self.head['control'], self.head['world'], group, maintainOffset=True)[0]
        condition = cmds.createNode('condition', name=self.module_name+'Space_COND')
        cmds.connectAttr(self.root_ctl+'.space', condition+'.firstTerm')
        cmds.setAttr(condition+'.secondTerm', 0)
        cmds.setAttr(condition+'.colorIfTrue', 1, 0, 0, type='double3')
        cmds.setAttr(condition+'.colorIfFalse', 0, 1, 0, type='double3')
        for constraint, command in ((parent, cmds.parentConstraint), (scale, cmds.scaleConstraint)):
            weights = command(constraint, query=True, weightAliasList=True)
            cmds.connectAttr(condition+'.outColorR', constraint+'.'+weights[0])
            cmds.connectAttr(condition+'.outColorG', constraint+'.'+weights[1])
            cmds.parent(constraint, self.module_trn, relative=True)
        self.result.update(module=self.module_trn, skeleton_grp=self.skeleton_grp, controllers_grp=self.controllers_grp)

    def curl_setup(self):
        common.add_rotation(self.module_name+'Spread', [self.root_ctl+'.spread', self.head['control']+'.petalSpread'],
                            self.result['groups'][0][1]+'.rotateZ')
        common.add_rotation(self.module_name+'Twist', [self.root_ctl+'.twist', self.head['control']+'.petalTwist'],
                            self.result['groups'][0][1]+'.rotateX')
        for index in range(1, len(self.result['controls'])):
            common.add_rotation(self.module_name+'Curl%02d' % index,
                                [self.root_ctl+'.curl', self.head['control']+'.petalCurl'],
                                self.result['groups'][index][1]+'.rotateZ', multiplier=0.5)
            for shape in cmds.listRelatives(self.result['controls'][index], shapes=True):
                cmds.connectAttr(self.head['control']+'.showPetalDetails', shape+'.visibility')

    def export_data(self):
        data_manager.DataExportBiped().append_data('petal_module', {
            self.module_name+'_ctl': self.root_ctl, self.module_name+'_skinningJoints': self.result['joints'],
            self.module_name+'_module_GRP': self.module_trn, self.module_name+'_skinning_GRP': self.skeleton_grp,
            self.module_name+'_controllers_GRP': self.controllers_grp})


def set_space(controls=None, space='World', key=True):
    """Match selected petal roots in world space, optionally keying a stepped release.

    This is an explicit animator action; no frame callback or expression is used.
    Root TRS compensates both the space group's change and its existing rest matrix.
    """
    controls = controls or cmds.ls(selection=True, type='transform') or []
    value = {'Head': 0, 'World': 1}[space]
    if not controls or any(not cmds.objExists(ctl+'.space') or 'petal' not in ctl for ctl in controls):
        raise ValueError('Select flower petal root controls with a space channel.')
    time = cmds.currentTime(query=True)
    attributes = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz']
    cmds.undoInfo(openChunk=True, chunkName='Flower petal space match')
    try:
        for ctl in controls:
            if cmds.getAttr(ctl+'.space') == value:
                continue
            matrix = cmds.xform(ctl, query=True, worldSpace=True, matrix=True)
            if key:
                for attr in attributes+['space']:
                    plug = ctl+'.'+attr
                    if cmds.keyframe(plug, query=True, keyframeCount=True):
                        cmds.setKeyframe(plug, time=time-1, insert=True)
                    else:
                        cmds.setKeyframe(plug, time=time-1, value=cmds.getAttr(plug, time=time-1))
                cmds.setKeyframe(ctl+'.space', time=time, value=value, outTangentType='step')
            else:
                cmds.setAttr(ctl+'.space', value)
            cmds.xform(ctl, worldSpace=True, matrix=matrix)
            if key:
                cmds.setKeyframe(ctl, attribute=attributes, time=time)
                cmds.keyTangent(ctl+'.space', edit=True, outTangentType='step')
    finally:
        cmds.undoInfo(closeChunk=True)
    return controls
