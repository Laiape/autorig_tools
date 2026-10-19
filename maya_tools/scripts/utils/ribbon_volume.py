"""Native inverse-length volume for matrix-driven spine and neck ribbons."""
import maya.cmds as cmds


def create_volume_matrix(drivers, control, masterwalk, name):
    """Read upstream solved positions; never read the scaled output joints."""
    cmds.addAttr(control, longName='volumePreservation', niceName='Volume Preservation',
                 attributeType='double', minValue=0, maxValue=1, defaultValue=1, keyable=True)
    total = cmds.createNode('plusMinusAverage', name=name + 'Length_PMA', ss=True)
    rest = 0.0
    for i in range(1, len(drivers)):
        distance = cmds.createNode('distanceBetween', name=name + f'{i:02d}_DBT', ss=True)
        for slot, plug in enumerate(drivers[i - 1:i + 1], 1):
            cmds.connectAttr(plug, distance + f'.inMatrix{slot}')
        rest += cmds.getAttr(distance + '.distance')
        cmds.connectAttr(distance + '.distance', total + f'.input1D[{i - 1}]')
    normalize = cmds.createNode('multiplyDivide', name=name + 'Length_MDV', ss=True)
    cmds.setAttr(normalize + '.operation', 2)
    cmds.connectAttr(total + '.output1D', normalize + '.input1X')
    cmds.connectAttr(masterwalk + '.globalScale', normalize + '.input2X')
    ratio = cmds.createNode('multiplyDivide', name=name + 'Ratio_MDV', ss=True)
    cmds.setAttr(ratio + '.operation', 2)
    cmds.connectAttr(normalize + '.outputX', ratio + '.input1X')
    cmds.setAttr(ratio + '.input2X', max(rest / cmds.getAttr(masterwalk + '.globalScale'), 1e-8))
    limit = cmds.createNode('clamp', name=name + 'Ratio_CLP', ss=True)
    cmds.setAttr(limit + '.minR', 1e-4)
    cmds.setAttr(limit + '.maxR', 1e4)
    cmds.connectAttr(ratio + '.outputX', limit + '.inputR')
    power = cmds.createNode('multiplyDivide', name=name + 'Inverse_MDV', ss=True)
    cmds.setAttr(power + '.operation', 3)
    cmds.setAttr(power + '.input2X', -.5)
    cmds.connectAttr(limit + '.outputR', power + '.input1X')
    blend = cmds.createNode('blendTwoAttr', name=name + '_BTA', ss=True)
    cmds.setAttr(blend + '.input[0]', 1)
    cmds.connectAttr(power + '.outputX', blend + '.input[1]')
    cmds.connectAttr(control + '.volumePreservation', blend + '.attributesBlender')
    volume = cmds.createNode('composeMatrix', name=name + '_CMX', ss=True)
    # Both quadruped ribbon solvers use X longitudinally. Apply volume here,
    # before calibration into possibly unrelated authored skin-joint axes.
    for axis in 'YZ':
        cmds.connectAttr(blend + '.output', volume + '.inputScale' + axis)
    return volume + '.outputMatrix'
