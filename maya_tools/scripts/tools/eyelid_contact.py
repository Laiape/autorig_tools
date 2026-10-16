"""Undoable upgrade of the native legacy eyelid blink/rotation graph.

Preserve skin weights, bind matrices, controls, animation and joint identities.
Use upgrade() explicitly on an existing rig; new builds use EyelidModule.
"""
from maya import cmds
from maya.api import OpenMaya as om


def _source(plug):
    return cmds.connectionInfo(plug, sourceFromDestination=True)


def _shape(curve):
    return cmds.listRelatives(curve, shapes=True, noIntermediate=True, fullPath=True)[0]


def _rotation(ctl, placement, joint, stem):
    position = cmds.createNode('pickMatrix', name=stem+'ControlPosition_PMX')
    cmds.connectAttr(ctl+'.matrix', position+'.inputMatrix')
    for component in ('Rotate', 'Scale', 'Shear'):
        cmds.setAttr(position+'.use'+component, 0)
    cmds.connectAttr(position+'.outputMatrix', placement+'.matrixIn[0]', force=True)
    attachment = _source(joint+'.offsetParentMatrix')
    rotation = cmds.createNode('pickMatrix', name=stem+'ControlRotation_PMX')
    cmds.connectAttr(ctl+'.matrix', rotation+'.inputMatrix')
    for component in ('Translate', 'Scale', 'Shear'):
        cmds.setAttr(rotation+'.use'+component, 0)
    final = cmds.createNode('multMatrix', name=stem+'ControlRotation_MMX')
    cmds.connectAttr(rotation+'.outputMatrix', final+'.matrixIn[0]')
    cmds.connectAttr(attachment, final+'.matrixIn[1]')
    cmds.connectAttr(final+'.matrixSum', joint+'.offsetParentMatrix', force=True)


def _upgrade_side(prefix):
    ctl = prefix+'_eyeDirect_CTL'
    ref = prefix+'_eyelidBlink_BLS'
    paths = []
    for label, curve_label, attr in (('upper', 'Up', 'Upper_Blink'),
                                      ('lower', 'Down', 'Lower_Blink')):
        source = prefix+'_eyelid'+curve_label+'_CRV'
        output = prefix+'_eyelid'+curve_label+'Rebuilded_CRV'
        blink = prefix+'_'+label+'EyelidBlink_BLS'
        skin = prefix+'_'+label+'Eyelid_SKIN'
        pose = cmds.duplicate(source, name=prefix+'_eyelid'+curve_label+'Pose_CRV')[0]
        # Move the existing skin before the blink without rebinding or copying
        # weights. Its original static input is the blendShape's rest input.
        rest_input = _source(blink+'.input[0].inputGeometry')
        cmds.connectAttr(rest_input, skin+'.input[0].inputGeometry', force=True)
        cmds.connectAttr(skin+'.outputGeometry[0]', _shape(pose)+'.create', force=True)
        cmds.connectAttr(blink+'.outputGeometry[0]', _shape(output)+'.create', force=True)
        for blend, index in ((blink, 1), (ref, 0 if label == 'upper' else 1)):
            target = blend+'.inputTarget[0].inputTargetGroup[%d].inputTargetItem[6000].inputGeomTarget'%index
            cmds.connectAttr(_shape(pose)+'.worldSpace[0]', target, force=True)
        cmds.connectAttr(ctl+'.'+attr, prefix+'_'+label+'Blink_REV.inputX', force=True)
        clamp = cmds.createNode('clamp', name=prefix+'_'+label+'ContactAmount_CLP')
        cmds.setAttr(clamp+'.maxR', 1)
        cmds.connectAttr(ctl+'.'+attr, clamp+'.inputR')
        path_label = 'upper' if label == 'upper' else 'down'
        paths.append((sorted(cmds.ls(prefix+'_'+path_label+'Eyelid*_MTP', type='motionPath'),
                             key=lambda n: int(n.rsplit('Eyelid0', 1)[1].split('_')[0])), clamp+'.outputR'))

    parameters = [[cmds.getAttr(path+'.uValue') for path in paths_for_lid] for paths_for_lid, _ in paths]

    def shared(fraction):
        samples = []
        for values in parameters:
            position = fraction*(len(values)-1)
            index = min(int(position), len(values)-2)
            weight = position-index
            samples.append(values[index]*(1-weight)+values[index+1]*weight)
        return sum(samples)*.5

    for lid, (paths_for_lid, amount) in enumerate(paths):
        for index, path in enumerate(paths_for_lid):
            stem = path[:-4]
            parent = stem+'_PMT'
            parameter = cmds.createNode('blendTwoAttr', name=stem+'ContactU_BTA')
            cmds.setAttr(parameter+'.input[0]', parameters[lid][index])
            cmds.setAttr(parameter+'.input[1]', shared(index/float(len(paths_for_lid)-1)))
            cmds.connectAttr(amount, parameter+'.attributesBlender')
            cmds.connectAttr(parameter+'.output', path+'.uValue', force=True)
            offset = cmds.createNode('blendMatrix', name=stem+'ContactOffset_BMX')
            cmds.setAttr(offset+'.inputMatrix', cmds.getAttr(parent+'.target[0].offsetMatrix'), type='matrix')
            cmds.setAttr(offset+'.target[0].targetMatrix', list(om.MMatrix.kIdentity), type='matrix')
            cmds.connectAttr(amount, offset+'.target[0].weight')
            cmds.connectAttr(offset+'.outputMatrix', parent+'.target[0].offsetMatrix', force=True)
            label = 'upper' if lid == 0 else 'down'
            control_stem = prefix+'_'+label+'Eyelid0'+str(index)
            _rotation(control_stem+'_CTL', stem+'Skinning_MMT', control_stem+'Skinning_JNT', stem)
    return prefix


def upgrade(controls=None):
    """Upgrade standard legacy eyelids in one undo chunk; refuse unknown graphs.

    Pass eyeDirect controller names to restrict the operation to a character.
    Repeated runs skip upgraded sides. The caller owns native backup/save.
    """
    controls = controls if controls is not None else cmds.ls('*_eyeDirect_CTL', recursive=True)
    prefixes = []
    roll_only = []
    from maya_tools.scripts.tools import eyelid_corners
    for ctl in controls:
        prefix = ctl.rsplit('|', 1)[-1].removesuffix('_eyeDirect_CTL')
        if cmds.objExists(prefix+'_upperContactAmount_CLP'):
            if (not eyelid_corners.current(prefix)
                    or not cmds.objExists(prefix+'_upperEyelid00TangentAxis_BLC')):
                roll_only.append(prefix)
            continue
        for label, curve_label in (('upper', 'Up'), ('lower', 'Down')):
            skin = prefix+'_'+label+'Eyelid_SKIN'
            blink = prefix+'_'+label+'EyelidBlink_BLS'
            output = prefix+'_eyelid'+curve_label+'Rebuilded_CRV'
            if (_source(_shape(output)+'.create') != skin+'.outputGeometry[0]'
                    or _source(skin+'.input[0].inputGeometry') != blink+'.outputGeometry[0]'):
                raise RuntimeError('Unsupported eyelid history: '+output)
            if cmds.referenceQuery(skin, isNodeReferenced=True):
                raise RuntimeError('Upgrade the source rig for referenced eyelids: '+skin)
            path_label = 'upper' if label == 'upper' else 'down'
            paths = cmds.ls(prefix+'_'+path_label+'Eyelid*_MTP', type='motionPath')
            if len(paths) < 2:
                raise RuntimeError('Missing eyelid attachment paths: '+prefix)
            for path in paths:
                parent = path[:-4]+'_PMT'
                if _source(path+'.uValue') or _source(parent+'.target[0].offsetMatrix'):
                    raise RuntimeError('Custom driven eyelid attachment: '+path)
            if cmds.objExists(prefix+'_eyelid'+curve_label+'Pose_CRV'):
                raise RuntimeError('Existing eyelid pose curve: '+prefix)
        prefixes.append(prefix)
    if not prefixes and not roll_only:
        return []
    if not cmds.undoInfo(q=True, state=True):
        raise RuntimeError('Enable Maya undo before upgrading eyelids')
    selection = cmds.ls(sl=True, long=True)
    cmds.undoInfo(openChunk=True, chunkName='Eyelid contact and rotation')
    try:
        result = [_upgrade_side(prefix) for prefix in prefixes]
        from maya_tools.scripts.tools import eyelid_rotation
        for prefix in prefixes + roll_only:
            eyelid_rotation.install(prefix)
        result += roll_only
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    except Exception:
        cmds.undoInfo(closeChunk=True)
        cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    return result
