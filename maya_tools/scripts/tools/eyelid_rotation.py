"""Whole-lid main Z rotation in the native eyelid construction space."""
from maya import cmds


def install(prefix, eye_matrix=None):
    """Install main-control Z roll with reduced influence near lid corners.

    Main Z is removed from partial skin inheritance. Restore the original
    moving main-control pivot; the downstream border applies spatial falloff
    before blink instead of rotating the whole opening around the eye.
    """
    changed = []
    if eye_matrix is None:
        eye_matrix = cmds.getAttr(prefix+'_upperEyelid00Skinning_AIM.primaryTargetMatrix')
    for label, curve_label in (('upper', 'Up'), ('lower', 'Down')):
        stem = prefix+'_'+label+'LidRoll'
        joint = prefix+'_eyelid'+curve_label+'Local_JNT'
        if cmds.objExists(stem+'_TG'):
            plug = stem+'Pivot_MMX.matrixIn[0]'
            source = cmds.connectionInfo(plug, sourceFromDestination=True)
            if source != joint+'.worldMatrix[0]':
                cmds.connectAttr(joint+'.worldMatrix[0]', plug, force=True)
            _remove_secondary_primary_z(prefix, curve_label)
            continue
        ctl = prefix+'_eyelid'+curve_label+'_CTL'
        local = prefix+'_eyelid'+curve_label+'Local_MMX'
        pose = prefix+'_eyelid'+curve_label+'Pose_CRV'
        shape = cmds.listRelatives(pose, shapes=True, noIntermediate=True, fullPath=True)[0]
        # Keep all authored TRS/shear/rotate-order channels except primary Z.
        compose = cmds.createNode('composeMatrix', name=stem+'Local_CMX')
        for channel, target in (('translate','inputTranslate'), ('scale','inputScale'),
                                ('shear','inputShear'), ('rotateOrder','inputRotateOrder')):
            cmds.connectAttr(ctl+'.'+channel, compose+'.'+target)
        for axis in 'XY':
            cmds.connectAttr(ctl+'.rotate'+axis, compose+'.inputRotate'+axis)
        cmds.connectAttr(compose+'.outputMatrix', local+'.matrixIn[0]', force=True)
        # Secondary skin inheritance must not add another weighted main roll.
        _remove_secondary_primary_z(prefix, curve_label)
        pivot = cmds.createNode('multMatrix', name=stem+'Pivot_MMX')
        cmds.connectAttr(joint+'.worldMatrix[0]', pivot+'.matrixIn[0]')
        cmds.connectAttr(pose+'.worldInverseMatrix[0]', pivot+'.matrixIn[1]')
        inverse = cmds.createNode('inverseMatrix', name=stem+'Pivot_INV')
        cmds.connectAttr(pivot+'.matrixSum', inverse+'.inputMatrix')
        rotation = cmds.createNode('composeMatrix', name=stem+'_CMX')
        cmds.connectAttr(ctl+'.rotateZ', rotation+'.inputRotateZ')
        matrix = cmds.createNode('multMatrix', name=stem+'_MMX')
        cmds.connectAttr(inverse+'.outputMatrix', matrix+'.matrixIn[0]')
        cmds.connectAttr(rotation+'.outputMatrix', matrix+'.matrixIn[1]')
        cmds.connectAttr(pivot+'.matrixSum', matrix+'.matrixIn[2]')
        source = cmds.connectionInfo(shape+'.create', sourceFromDestination=True)
        geometry = cmds.createNode('transformGeometry', name=stem+'_TG')
        cmds.connectAttr(source, geometry+'.inputGeometry')
        cmds.connectAttr(matrix+'.matrixSum', geometry+'.transform')
        cmds.connectAttr(geometry+'.outputGeometry', shape+'.create', force=True)
        changed.append(ctl)
    # The contact curve is already shared. A forced horizontal latitude would
    # erase the new tilt at full blink. Preserve sampled eye-local Y instead.
    for node in cmds.ls(prefix+'_*Eyelid*FlatY_BTA', type='blendTwoAttr') or []:
        plug = node+'.attributesBlender'
        source = cmds.connectionInfo(plug, sourceFromDestination=True)
        if source:
            cmds.disconnectAttr(source, plug)
        cmds.setAttr(plug, 0)
    from maya_tools.scripts.tools import eyelid_corners
    joined=eyelid_corners.install(prefix, eye_matrix)
    eyelid_corners.install_tangents(prefix)
    if joined and not changed:
        changed=[prefix+'_eyelid'+label+'_CTL' for label in ('Up','Down')]
    return changed


def _remove_secondary_primary_z(prefix, curve_label):
    """Persist the disabled inherited roll on scalar compose inputs.

    Locate the owned multipliers by name as well as type: old installs have
    already disconnected their driver and may have lost input[0] on save.
    """
    pattern = prefix+'_eyelid'+curve_label+'Rotation00Z_MUL*'
    for node in cmds.ls(pattern, type='multiply') or []:
        consumers = cmds.listConnections(node+'.output', source=False,
                                        destination=True, plugs=True,
                                        skipConversionNodes=True) or []
        for consumer in consumers:
            owner, attribute = consumer.rsplit('.', 1)
            if cmds.nodeType(owner) != 'composeMatrix' or attribute not in ('inputRotateZ', 'irz'):
                continue
            original = cmds.connectionInfo(consumer, sourceFromDestination=True)
            cmds.disconnectAttr(original, consumer)
            cmds.setAttr(consumer, 0)
