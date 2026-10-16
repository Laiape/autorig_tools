"""Build-time placement and visibility for digit settings controls."""
import maya.cmds as cmds
import maya.api.OpenMaya as om


def configure_digit_settings(settings_ctl, chains, follow_matrix=None):
    """Place settings above all digits and hide their FK groups by default.

    Only drawing visibility is driven. A native matrix offset follows the paw
    when supplied, keeping settings separate from the groups it hides.
    """
    chains = [list(chain) for chain in chains if chain]
    if not chains:
        return
    points = [cmds.xform(ctl, q=True, ws=True, t=True) for chain in chains for ctl in chain]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    span = max(hi[0] - lo[0], hi[2] - lo[2], .1)
    position = [(lo[0] + hi[0]) * .5, hi[1] + span * .65, (lo[2] + hi[2]) * .5]
    rest = om.MMatrix([1,0,0,0, 0,1,0,0, 0,0,1,0, *position,1])
    # Both digit builders keep their settings offsets under a named GRP.
    group = cmds.ls(settings_ctl.rsplit('|', 1)[-1].replace('_CTL', '_GRP'), long=True)[0]
    if follow_matrix:
        offset = rest * om.MMatrix(cmds.getAttr(follow_matrix)).inverse()
        node = cmds.createNode('multMatrix', name=settings_ctl.rsplit('|',1)[-1].replace('_CTL','Follow_MMX'), ss=True)
        cmds.setAttr(node + '.matrixIn[0]', list(offset), type='matrix')
        cmds.connectAttr(follow_matrix, node + '.matrixIn[1]')
        cmds.setAttr(group + '.inheritsTransform', 0)
        cmds.connectAttr(node + '.matrixSum', group + '.offsetParentMatrix')
        cmds.xform(group, m=om.MMatrix.kIdentity)
    else:
        cmds.xform(group, ws=True, m=list(rest))

    attr = 'Controllers_Visibility'
    cmds.addAttr(settings_ctl, longName=attr, niceName='Controllers Visibility',
                 attributeType='bool', defaultValue=False)
    cmds.setAttr(settings_ctl + '.' + attr, channelBox=True)
    for chain in chains:
        root = chain[0].rsplit('|',1)[-1].replace('_CTL','_GRP')
        cmds.connectAttr(settings_ctl + '.' + attr, root + '.visibility')
