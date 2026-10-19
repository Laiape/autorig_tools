"""Shared authoring helpers; runtime evaluation uses native Maya nodes."""
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import curve_tool, data_manager


def structure(key):
    return data_manager.DataExportBiped().get_data('basic_structure', key)


def control(name, matrix, parent, radius=0.5, color=17, translate=False, scale=False):
    locked = ['v'] + ([] if translate else ['tx', 'ty', 'tz'])
    locked += [] if scale else ['sx', 'sy', 'sz']
    groups, ctl = curve_tool.create_controller(name=name, offset=['GRP', 'AUTO', 'ANM'],
                                              parent=parent, matrix=matrix, locked_attrs=locked)
    if not cmds.attributeQuery('autorigTemplateShape', node=ctl, exists=True):
        # Default circles face down the chain's local X axis.
        old = cmds.listRelatives(ctl, shapes=True, fullPath=True) or []
        temp = cmds.circle(normal=(1, 0, 0), radius=radius, constructionHistory=False)[0]
        for shape in cmds.listRelatives(temp, shapes=True, fullPath=True):
            cmds.parent(shape, ctl, shape=True, relative=True)
        cmds.delete(temp, *old)
    for shape in cmds.listRelatives(ctl, shapes=True, fullPath=True) or []:
        cmds.setAttr(shape+'.overrideEnabled', 1)
        cmds.setAttr(shape+'.overrideColor', color)
        cmds.setAttr(shape+'.lineWidth', 1.7)
    return groups, ctl


def joint(name, ctl, parent):
    node = cmds.createNode('joint', name=name, parent=parent)
    cmds.setAttr(node+'.segmentScaleCompensate', 0)
    cmds.setAttr(node+'.radius', 0.15)
    matrix = cmds.createNode('multMatrix', name=name.replace('_JNT', '_MMX'))
    cmds.connectAttr(ctl+'.worldMatrix[0]', matrix+'.matrixIn[0]')
    cmds.connectAttr(parent+'.worldInverseMatrix[0]', matrix+'.matrixIn[1]')
    cmds.connectAttr(matrix+'.matrixSum', node+'.offsetParentMatrix')
    return node


def chain(entry, guides, control_parent, joint_parent, radius, color, free_root=False):
    controls, joints, groups = [], [], []
    for index, guide in enumerate(entry['guides']):
        prefix = '%s%02d' % (entry['prefix'], index)
        offsets, ctl = control(prefix, guides[guide]['joint_matrix'],
                               controls[-1] if controls else control_parent,
                               radius=radius, color=color,
                               translate=free_root and index == 0, scale=free_root and index == 0)
        jnt = joint(prefix+'Skinning_JNT', ctl, joints[-1] if joints else joint_parent)
        controls.append(ctl); joints.append(jnt); groups.append(offsets)
    return {'controls': controls, 'joints': joints, 'groups': groups, 'entry': entry}


def number(node, name, default=0., minimum=None, maximum=None):
    options = dict(longName=name, attributeType='double', defaultValue=default, keyable=True)
    if minimum is not None:
        options['minValue'] = minimum
    if maximum is not None:
        options['maxValue'] = maximum
    cmds.addAttr(node, **options)
    return node+'.'+name


def add_rotation(name, plugs, destination, multiplier=1.):
    add = cmds.createNode('plusMinusAverage', name=name+'_PMA')
    for index, plug in enumerate(plugs):
        cmds.connectAttr(plug, '%s.input1D[%s]' % (add, index))
    source = add+'.output1D'
    if multiplier != 1.:
        mult = cmds.createNode('multiply', name=name+'_MUL')
        cmds.connectAttr(source, mult+'.input[0]')
        cmds.setAttr(mult+'.input[1]', multiplier)
        source = mult+'.output'
    cmds.connectAttr(source, destination)


def point_list(mesh):
    selection = om.MSelectionList(); selection.add(mesh)
    path = selection.getDagPath(0); path.extendToShape()
    return path, list(om.MFnMesh(path).getPoints(om.MSpace.kWorld))


def raised_drawing(ctl, length, height=0.5):
    """Keep a root pivot at the attachment while exposing its selectable drawing."""
    if cmds.attributeQuery('autorigTemplateShape', node=ctl, exists=True):
        return
    cmds.rotate(0, 0, 90, ctl+'.cv[*]', relative=True, objectSpace=True)
    cmds.move(length*0.7, height, 0, ctl+'.cv[*]', relative=True, objectSpace=True)


def follow(target, source, maintain_offset=True):
    """Use the actual parent inverse while preserving the authored rest frame."""
    parent = cmds.listRelatives(target, parent=True, fullPath=True)
    world = om.MMatrix(cmds.getAttr(target+'.worldMatrix[0]'))
    source_world = om.MMatrix(cmds.getAttr(source+'.worldMatrix[0]'))
    offset = world*source_world.inverse() if maintain_offset else om.MMatrix()
    matrix = cmds.createNode('multMatrix', name=target.replace('_GRP', '').replace('_REF', '')+'Follow_MMX')
    cmds.setAttr(matrix+'.matrixIn[0]', list(offset), type='matrix')
    cmds.connectAttr(source+'.worldMatrix[0]', matrix+'.matrixIn[1]')
    if parent:
        cmds.connectAttr(parent[0]+'.worldInverseMatrix[0]', matrix+'.matrixIn[2]')
    cmds.xform(target, matrix=om.MMatrix.kIdentity)
    cmds.connectAttr(matrix+'.matrixSum', target+'.offsetParentMatrix', force=True)
    return matrix


def attachment(name, matrix, source, module):
    reference = cmds.createNode('transform', name=name, parent=module, skipSelect=True)
    cmds.xform(reference, worldSpace=True, matrix=matrix)
    follow(reference, source)
    return reference


def settings_drawing(ctl, letter='F', force=False):
    """Use the repository's letter-curve helper without changing settings TRS."""
    if not force and cmds.attributeQuery('autorigTemplateShape', node=ctl, exists=True):
        return
    text = curve_tool.text_curve('C_flowerSettingsDrawing_TMP', letter=letter)
    box = cmds.exactWorldBoundingBox(text)
    factor = 2.5/max(box[4]-box[1], 1e-8)
    cmds.scale(factor, factor, factor, text+'.cv[*]', relative=True, objectSpace=True)
    cmds.move(9, 4, 0, text+'.cv[*]', relative=True, objectSpace=True)
    old = cmds.listRelatives(ctl, shapes=True, fullPath=True, type='nurbsCurve') or []
    for index, shape in enumerate(cmds.listRelatives(text, shapes=True, fullPath=True, type='nurbsCurve') or []):
        shape = cmds.parent(shape, ctl, shape=True, relative=True)[0]
        shape = cmds.rename(shape, ctl+'LetterShape%02d' % index)
        cmds.setAttr(shape+'.overrideEnabled', 1)
        cmds.setAttr(shape+'.overrideColor', 17)
        cmds.setAttr(shape+'.lineWidth', 2.)
    cmds.delete(text, *old)
