"""Native visibility switching for explicitly tagged model LOD groups."""
from maya import cmds

ROLE_ATTRIBUTE = 'autorigLodRole'


def configure(settings_ctl, geo_root):
    """Expose Low Res / High Res, initially High, for explicitly tagged groups.

    Shared geometry stays outside these groups. This controls display only;
    it makes no claim that hidden deformation work is bypassed.
    """
    groups = {'Low': [], 'High': []}
    for node in cmds.ls(geo_root, dag=True, type='transform', long=True) or []:
        if cmds.attributeQuery(ROLE_ATTRIBUTE, node=node, exists=True):
            role = cmds.getAttr(node + '.' + ROLE_ATTRIBUTE)
            if role in groups:
                groups[role].append(node)
    if not all(groups.values()):
        return {}
    if not cmds.attributeQuery('resolution', node=settings_ctl, exists=True):
        cmds.addAttr(settings_ctl, longName='resolution', niceName='Resolution',
                     attributeType='enum', enumName='Low Res:High Res', defaultValue=1)
    else:
        cmds.addAttr(settings_ctl + '.resolution', edit=True, defaultValue=1)
    cmds.setAttr(settings_ctl + '.resolution', keyable=False, channelBox=True)
    prefix = settings_ctl.rsplit('|', 1)[-1]
    for value, role in enumerate(('Low', 'High')):
        name = prefix + '_' + role + 'Res_COND'
        condition = name if cmds.objExists(name) else cmds.createNode('condition', name=name)
        cmds.setAttr(condition + '.operation', 0)
        cmds.setAttr(condition + '.secondTerm', value)
        cmds.setAttr(condition + '.colorIfTrueR', 1)
        cmds.setAttr(condition + '.colorIfFalseR', 0)
        if not cmds.isConnected(settings_ctl + '.resolution', condition + '.firstTerm'):
            cmds.connectAttr(settings_ctl + '.resolution', condition + '.firstTerm', force=True)
        for group in groups[role]:
            if not cmds.isConnected(condition + '.outColorR', group + '.visibility'):
                cmds.connectAttr(condition + '.outColorR', group + '.visibility', force=True)
    return groups
