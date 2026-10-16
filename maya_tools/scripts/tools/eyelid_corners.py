"""Main-control lid rolls with corner falloff and tangent transport."""
from maya import cmds
from maya.api import OpenMaya as om

VERSION = 3


def current(prefix):
    plugs = [prefix+'_'+label+'LidJoined_CRV.eyelidCornerVersion'
             for label in ('upper','lower')]
    return all(cmds.objExists(plug) and cmds.getAttr(plug) == VERSION for plug in plugs)


def install(prefix, eye_matrix):
    """Retain the original main pivot and fade its roll towards each corner.

    Full central rotation fades smoothly to about seven percent at the next
    CV to each corner, and zero at the shared endpoints. The other lid does
    not inherit this roll. Blink and calibrated tangent transport stay intact.
    """
    if current(prefix):
        return []
    names = [prefix+'_'+label+'LidJoined_CRV' for label in ('upper','lower')]
    obsolete = []
    for pattern in ('_*LidPose_CVI','_eyelid*Shared_PMA','_*Lid*Delta_PMA',
                    '_*LidJoined*_PMA','_*LidJoined*Corner*_MD'):
        obsolete += cmds.ls(prefix+pattern) or []
    # Upgrade only this installer's old orbit math, retaining the posed curves
    # and all their skin data. Recreate exact names for a repeatable migration.
    previous = []
    for label in ('upper','lower'):
        previous += cmds.ls(prefix+'_'+label+'LidOrbit*') or []
    if previous:
        cmds.delete(previous)
    for lid, (label, curve_label) in enumerate((('upper','Up'),('lower','Down'))):
        stem = prefix+'_'+label+'LidOrbit'
        info = cmds.createNode('curveInfo', name=stem+'_CVI')
        source = cmds.connectionInfo(prefix+'_'+label+'LidRoll_TG.inputGeometry', sourceFromDestination=True)
        cmds.connectAttr(source, info+'.inputCurve')
        if not cmds.objExists(names[lid]):
            cmds.duplicate(prefix+'_eyelid'+curve_label+'_CRV', name=names[lid])
        shape = cmds.listRelatives(names[lid], shapes=True, noIntermediate=True, fullPath=True)[0]
        count = len(cmds.ls(names[lid]+'.cv[*]', fl=True))
        if count < 5:
            raise ValueError('Eyelid roll falloff requires at least five CVs')
        matrices = {}
        for index in range(count):
            t = min(index,count-1-index)/((count-1)*.5)
            smooth = 3*t*t-2*t*t*t
            own = smooth*smooth
            if own not in matrices:
                angle = cmds.createNode('plusMinusAverage', name=stem+'Angle%02d_PMA'%index)
                other = 'Down' if curve_label == 'Up' else 'Up'
                for slot, (ctl, weight) in enumerate(((curve_label,own),(other,0))):
                    mul = cmds.createNode('multDoubleLinear', name=stem+'Angle%02dWeight%d_MDL'%(index,slot))
                    cmds.connectAttr(prefix+'_eyelid'+ctl+'_CTL.rz', mul+'.input1')
                    cmds.setAttr(mul+'.input2', weight)
                    cmds.connectAttr(mul+'.output', angle+'.input1D[%d]'%slot)
                rotation = cmds.createNode('composeMatrix', name=stem+'%02d_CMX'%index)
                cmds.connectAttr(angle+'.output1D', rotation+'.inputRotateZ')
                matrix = cmds.createNode('multMatrix', name=stem+'%02d_MMX'%index)
                cmds.connectAttr(prefix+'_'+label+'LidRollPivot_INV.outputMatrix', matrix+'.matrixIn[0]')
                cmds.connectAttr(rotation+'.outputMatrix', matrix+'.matrixIn[1]')
                cmds.connectAttr(prefix+'_'+label+'LidRollPivot_MMX.matrixSum', matrix+'.matrixIn[2]')
                matrices[own] = matrix+'.matrixSum'
            point = cmds.createNode('pointMatrixMult', name=stem+'%02d_PMM'%index)
            cmds.connectAttr(matrices[own], point+'.inMatrix')
            for axis in 'xyz':
                cmds.connectAttr(info+'.controlPoints[%d].%sValue'%(index,axis), point+'.inPoint'+axis.upper())
                cmds.connectAttr(point+'.output'+axis.upper(), shape+'.controlPoints[%d].%sValue'%(index,axis), force=True)
        for blend,index in ((prefix+'_'+label+'EyelidBlink_BLS',1),(prefix+'_eyelidBlink_BLS',lid)):
            target = blend+'.inputTarget[0].inputTargetGroup[%d].inputTargetItem[6000].inputGeomTarget'%index
            cmds.connectAttr(shape+'.worldSpace[0]', target, force=True)
        plug = names[lid]+'.eyelidCornerVersion'
        if not cmds.objExists(plug):
            cmds.addAttr(names[lid], longName='eyelidCornerVersion', attributeType='long')
        cmds.setAttr(plug, VERSION)
    if obsolete:
        cmds.delete(list(set(obsolete)))
    return names


def install_tangents(prefix):
    """Transport aim along the border with pose-independent bind calibration.

    Static guides supply rest tangent axes. Full blink shares the reference
    axis between both lids, preserving contact orientation and position.
    """
    paths = [sorted(cmds.ls(prefix+'_'+label+'Eyelid*_MTP', type='motionPath'),
                    key=lambda n:int(n.rsplit('Eyelid0',1)[1].split('_')[0]))
             for label in ('upper','down')]
    if not all(paths):
        return []
    if all(cmds.objExists(path[:-4]+'TangentAxis_BLC') for group in paths for path in group):
        return []
    axes = [[],[]]
    temporary = cmds.createNode('aimMatrix')
    cmds.setAttr(temporary+'.primaryInputAxis', 0,0,-1)
    try:
        for lid, curve_label in enumerate(('Up','Down')):
            selection = om.MSelectionList()
            selection.add(prefix+'_eyelid'+curve_label+'_CRV')
            dag = selection.getDagPath(0); dag.extendToShape()
            curve = om.MFnNurbsCurve(dag)
            for path in paths[lid]:
                stem = path[:-4]
                cmds.setAttr(temporary+'.inputMatrix', cmds.getAttr(stem+'Origin_F4X4.output'), type='matrix')
                cmds.setAttr(temporary+'.primaryTargetMatrix', cmds.getAttr(stem+'Skinning_AIM.primaryTargetMatrix'), type='matrix')
                rest = om.MMatrix(cmds.getAttr(temporary+'.outputMatrix'))
                parameter = cmds.getAttr(stem+'ContactU_BTA.input[0]')
                axes[lid].append((curve.tangent(parameter,om.MSpace.kWorld)*rest.inverse()).normal())
    finally:
        cmds.delete(temporary)

    def interpolate(values, fraction):
        position = fraction*(len(values)-1)
        index = min(int(position),len(values)-2)
        return values[index]*(1-(position-index))+values[index+1]*(position-index)

    changed = []
    for lid, group in enumerate(paths):
        for index, path in enumerate(group):
            stem = path[:-4]
            if cmds.objExists(stem+'TangentAxis_BLC'):
                continue
            fraction = index/float(len(group)-1)
            common = (interpolate(axes[0],fraction)+interpolate(axes[1],fraction)).normal()
            axis = axes[lid][index]
            info = cmds.createNode('pointOnCurveInfo', name=stem+'Tangent_PCI')
            cmds.connectAttr(cmds.connectionInfo(path+'.geometryPath',sourceFromDestination=True), info+'.inputCurve')
            cmds.connectAttr(cmds.connectionInfo(path+'.uValue',sourceFromDestination=True), info+'.parameter')
            blend = cmds.createNode('blendColors', name=stem+'TangentAxis_BLC')
            cmds.setAttr(blend+'.color1', common.x,common.y,common.z)
            cmds.setAttr(blend+'.color2', axis.x,axis.y,axis.z)
            label = 'upper' if lid == 0 else 'lower'
            cmds.connectAttr(prefix+'_'+label+'ContactAmount_CLP.outputR', blend+'.blender')
            aim = stem+'Skinning_AIM'
            cmds.setAttr(aim+'.secondaryMode', 2)
            cmds.connectAttr(blend+'.output', aim+'.secondaryInputAxis')
            cmds.connectAttr(info+'.normalizedTangent', aim+'.secondaryTargetVector')
            changed.append(aim)
    return changed
