"""Static calibration between authored animator frames and solver frames.

Only build-time Python runs here. Animation uses native matrix nodes. The
optional authored_guide_orientation build setting preserves legacy defaults.
"""
import maya.cmds as cmds
import maya.api.OpenMaya as om


def enabled():
    from maya_tools.scripts.utils import rig_manager
    asset = rig_manager.get_character_name_from_build()
    settings = rig_manager.build_rig_from_data(asset) if asset else None
    return bool((settings or {}).get('authored_guide_orientation', 0))


def matrix_plug(node):
    for attr in ('worldMatrix[0]', 'matrixSum', 'outputMatrix', 'output'):
        if cmds.objExists(node + '.' + attr):
            return node + '.' + attr
    raise ValueError('No matrix output: %s' % node)


def control_drivers(controls, authored, solver, name):
    """Keep controls in authored frames while providing solver-space drivers."""
    result = []
    for index, (ctl, source, target) in enumerate(zip(controls, authored, solver)):
        node = cmds.createNode('multMatrix', name='%s%02dSolverFrame_MMX' % (name, index), skipSelect=True)
        offset = om.MMatrix(target) * om.MMatrix(source).inverse()
        cmds.setAttr(node + '.matrixIn[0]', list(offset), type='matrix')
        cmds.connectAttr(matrix_plug(ctl), node + '.matrixIn[1]')
        result.append(node)
    return result


def calibrated_output(driver, target_rest, name, rotation_only=False, scale_plug=None):
    """Calibrate a new driver to its authored rest, keeping positions optional."""
    actual = om.MMatrix(cmds.getAttr(driver))
    target = om.MMatrix(target_rest)
    if rotation_only:
        actual = om.MTransformationMatrix(actual).rotation(asQuaternion=True).asMatrix()
        target = om.MTransformationMatrix(target).rotation(asQuaternion=True).asMatrix()
    offset = target * actual.inverse()
    node = cmds.createNode('multMatrix', name=name + '_MMX', skipSelect=True)
    translation = om.MVector(offset[12], offset[13], offset[14])
    if scale_plug and translation.length() > 1e-8:
        transform = om.MTransformationMatrix(offset)
        cmx = cmds.createNode('composeMatrix', name=name + '_CMX', skipSelect=True)
        rotation = transform.rotation().asVector()
        cmds.setAttr(cmx + '.inputRotate', *(v * 180.0 / 3.141592653589793 for v in rotation))
        mul = cmds.createNode('multiplyDivide', name=name + 'Scale_MDV', skipSelect=True)
        cmds.setAttr(mul + '.input1', translation.x, translation.y, translation.z)
        for axis in 'XYZ':
            cmds.connectAttr(scale_plug, mul + '.input2' + axis)
        cmds.connectAttr(mul + '.output', cmx + '.inputTranslate')
        cmds.connectAttr(cmx + '.outputMatrix', node + '.matrixIn[0]')
    else:
        cmds.setAttr(node + '.matrixIn[0]', list(offset), type='matrix')
    cmds.connectAttr(driver, node + '.matrixIn[1]')
    return node + '.matrixSum'


def interpolate(frames, parameter):
    """Interpolate authored rotations by distance, without re-aiming the axes."""
    positions = [om.MVector(m[12], m[13], m[14]) for m in frames]
    lengths = [(b - a).length() for a, b in zip(positions, positions[1:])]
    distance = min(1.0, max(0.0, parameter)) * sum(lengths)
    for i, length in enumerate(lengths):
        if distance <= length or i == len(lengths) - 1:
            weight = min(1.0, max(0.0, distance / length)) if length > 1e-8 else 0.0
            a = om.MTransformationMatrix(om.MMatrix(frames[i]))
            b = om.MTransformationMatrix(om.MMatrix(frames[i + 1]))
            rotation = om.MQuaternion.slerp(a.rotation(asQuaternion=True), b.rotation(asQuaternion=True), weight)
            matrix = list(rotation.asMatrix())
            matrix[12:15] = list(positions[i] * (1.0 - weight) + positions[i + 1] * weight)
            return matrix
        distance -= length
    return list(frames[0])


def orient_outputs(joints, authored_frames, name, parameters=None):
    """Preserve ribbon positions and transport each authored rest orientation."""
    parameters = parameters if parameters is not None else [i / float(max(1, len(joints) - 1)) for i in range(len(joints))]
    for index, (joint, parameter) in enumerate(zip(joints, parameters)):
        plug = joint + '.offsetParentMatrix'
        driver = cmds.connectionInfo(plug, sourceFromDestination=True)
        if not driver:
            raise ValueError('Expected a newly constructed matrix-driven joint: %s' % joint)
        target = interpolate(authored_frames, parameter)
        corrected = calibrated_output(driver, target, '%s%02dAuthoredFrame' % (name, index), rotation_only=True)
        cmds.connectAttr(corrected, plug, force=True)
