"""Upgrade an existing neutral authored-frame quadruped without rebuilding skin.

Call upgrade_current_rig() only after preserving the artist scene. The caller
owns the undo chunk, reference comparison, versioned save and failure rollback.
This bounded migration supports the existing authored-frame native ribbon graph;
new builds use the normal SpineModule/NeckModule and shared builder instead.
"""
import re

import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.quadruped.autorig import spine_module, neck_module
from maya_tools.scripts.utils import matrix_manager


def _controls(kind):
    pattern = re.compile(r'^C_' + kind + r'(\d+)(Tan)?_CTL$')
    return sorted((ctl for ctl in cmds.ls('C_' + kind + '*_CTL', type='transform')
                   if pattern.match(ctl)), key=lambda ctl: int(pattern.match(ctl).group(1)))


def _authored_inputs(kind, joints):
    adapters = [f'C_{kind}{i:02d}AuthoredFrame_MMX' for i in range(len(joints))]
    if not all(cmds.objExists(node) for node in adapters):
        raise ValueError('Migration requires the existing authored-frame %s ribbon.' % kind)
    drivers = [cmds.connectionInfo(node + '.matrixIn[1]', sourceFromDestination=True) for node in adapters]
    if not all(drivers):
        raise ValueError('Incomplete upstream %s ribbon graph.' % kind)
    return adapters, drivers


def upgrade_current_rig():
    """Keep current static animator channels while calibrating at neutral."""
    required = ('C_body_CTL', 'C_pelvis_CTL', 'C_localChest_CTL', 'C_head_CTL',
                'C_spine00SolverFrame_MMX', 'C_neck00SolverFrame_MMX')
    if not all(cmds.objExists(node) for node in required):
        raise ValueError('Select an existing authored-frame quadruped rig before migration.')
    controls = _controls('spine') + _controls('neck') + [
        'C_body_CTL', 'C_head_CTL', 'C_localChest_CTL', 'C_pelvis_CTL']
    pose = {ctl: {attr: cmds.getAttr(ctl + '.' + attr)[0] for attr in ('translate', 'rotate')}
            for ctl in controls}
    for ctl in controls:
        for attr in ('translate', 'rotate'):
            for axis in 'XYZ':
                if cmds.listConnections(ctl + '.' + attr + axis, source=True, destination=False):
                    raise ValueError('Migrate an unanimated copy; channel is driven: ' + ctl + '.' + attr + axis)
    try:
        for ctl in controls:
            for attr in ('translate', 'rotate'):
                cmds.setAttr(ctl + '.' + attr, 0, 0, 0)
        result = _upgrade_neutral_rig()
        result['preserved_pose_channels'] = pose
        return result
    finally:
        for ctl, attributes in pose.items():
            for attr, value in attributes.items():
                cmds.setAttr(ctl + '.' + attr, *value)


def _upgrade_neutral_rig():
    """Preserve skin nodes/bind data and adapt the existing native graph."""
    if cmds.objExists('C_body_CTL.volumePreservation'):
        raise ValueError('This rig already has the new body/neck setup.')
    spine_controls, neck_controls = _controls('spine'), _controls('neck')
    if len(spine_controls) < 2 or len(neck_controls) < 2:
        raise ValueError('Expected existing central spine and neck controls.')
    controls = spine_controls + neck_controls + ['C_body_CTL', 'C_head_CTL', 'C_localChest_CTL', 'C_pelvis_CTL']
    for ctl in controls:
        for attribute in ('translate', 'rotate'):
            if max(abs(v) for v in cmds.getAttr(ctl + '.' + attribute)[0]) > 1e-7:
                raise ValueError('Preserve the pose and return %s.%s to neutral before migration.' % (ctl, attribute))
    if abs(cmds.getAttr('C_masterwalk_CTL.globalScale') - 1) > 1e-7:
        raise ValueError('Migration requires globalScale 1.')
    spine_joints = sorted(j for j in cmds.listRelatives('C_spineSkinning_GRP', allDescendents=True, type='joint')
                          if re.match(r'^C_spine\d+_JNT$', j))
    neck_joints = sorted(j for j in cmds.listRelatives('C_neckSkinning_GRP', allDescendents=True, type='joint')
                         if re.match(r'^C_neck\d+_JNT$', j)) + ['C_headSkinning_JNT']
    spine_adapters, spine_drivers = _authored_inputs('spine', spine_joints)
    neck_adapters, neck_drivers = _authored_inputs('neck', neck_joints)
    head_skin_rest = cmds.getAttr('C_headSkinning_JNT.worldMatrix[0]')

    spine = spine_module.SpineModule.__new__(spine_module.SpineModule)
    spine.side = 'C'
    spine.masterwalk_ctl = 'C_masterwalk_CTL'
    spine.controllers_grp = 'C_spineControllers_GRP'
    spine.skeleton_grp = 'C_spineSkinning_GRP'
    spine.body_ctl, spine.body_nodes = 'C_body_CTL', ['C_body_GRP']
    spine.spine_ctls = spine_controls
    spine.spine_nodes = [[ctl.replace('_CTL', '_GRP')] for ctl in spine_controls]
    spine.spine_guides_matrices = [cmds.getAttr(ctl + '.worldMatrix[0]') for ctl in spine_controls]
    spine.tangent_indices = {i for i, ctl in enumerate(spine_controls) if 'Tan' in ctl}
    spine.local_chest_ctl, spine.local_chest_nodes = 'C_localChest_CTL', ['C_localChest_GRP']
    spine.ribbon_tip_plug = spine_drivers[-1]
    for axis in 'XYZ':
        cmds.setAttr('C_localChest_CTL.scale' + axis, lock=False, keyable=True)
    spine.movable_body_pivot()
    spine.parent_spine_controls()
    spine.control_follow_setup()
    matrix_manager.space_switches('C_spine00_CTL', ['C_body_CTL', 'C_pelvis_CTL', 'C_masterwalk_CTL'],
                                  sources_names=['body', 'localHip', 'masterWalk'],
                                  default_translate=1, default_rotate=1, base_ctl='C_masterwalk_CTL')
    chest_drivers = spine.chest_spine_curve_drivers()
    for i, driver in enumerate(chest_drivers):
        cmds.connectAttr(driver + '.worldMatrix[0]' if driver.endswith('_CTL') else driver + '.matrixSum',
                         f'C_spine{i:02d}SolverFrame_MMX.matrixIn[1]', force=True)
    for i in range(1, len(chest_drivers)):
        for slot, driver in enumerate(chest_drivers[i - 1:i + 1], 1):
            plug = driver + ('.worldMatrix[0]' if driver.endswith('_CTL') else '.matrixSum')
            cmds.connectAttr(plug, f'C_spine0{i}StretchDist_DBT.inMatrix{slot}', force=True)
    volume_drivers = spine.volume_setup(spine_joints, drivers=spine_drivers, connect=False)
    for adapter, plug in zip(spine_adapters, volume_drivers):
        cmds.connectAttr(plug, adapter + '.matrixIn[1]', force=True)
    spine.local_chest_setup()

    neck = neck_module.NeckModule.__new__(neck_module.NeckModule)
    neck.side, neck.masterwalk_ctl = 'C', 'C_masterwalk_CTL'
    neck.neck_ctls, neck.neck_nodes = neck_controls, [ctl.replace('_CTL', '_GRP') for ctl in neck_controls]
    neck.neck_guides_matrices = [cmds.getAttr(ctl + '.worldMatrix[0]') for ctl in neck_controls]
    neck.head_ctl, neck.head_nodes = 'C_head_CTL', ['C_head_GRP']
    neck.head_guide_matrix = cmds.getAttr('C_head_CTL.worldMatrix[0]')
    neck.parent_neck_controls()
    neck.control_follow_setup()
    neck.local_head()
    # Retain the legacy float in saved files, hidden and disconnected from the
    # new switch. Old graph nodes are retained as a recovery record.
    cmds.setAttr('C_head_CTL.HEAD_FOLLOW', keyable=False, channelBox=False)
    if cmds.objExists('C_head_CTL.NECK_FOLLOW'):
        cmds.setAttr('C_head_CTL.NECK_FOLLOW', channelBox=False)
    last = len(neck_controls) - 1
    cmds.connectAttr('C_head_CTL.worldMatrix[0]', f'C_neck{last:02d}SolverFrame_MMX.matrixIn[1]', force=True)
    output = f'C_neck0{last}Stretch_MMX'
    cmds.connectAttr(f'C_neck{last:02d}SolverFrame_MMX.matrixSum', output + '.matrixIn[0]', force=True)
    previous = cmds.connectionInfo(output + '.matrixIn[1]', sourceFromDestination=True)
    if previous:
        cmds.disconnectAttr(previous, output + '.matrixIn[1]')
    cmds.setAttr(output + '.matrixIn[1]', list(om.MMatrix.kIdentity), type='matrix')
    cmds.connectAttr('C_head_CTL.worldMatrix[0]', f'C_neck0{last}StretchDist_DBT.inMatrix2', force=True)
    volume_drivers = neck.volume_setup(neck_joints, drivers=neck_drivers, connect=False)
    for adapter, plug in zip(neck_adapters, volume_drivers):
        cmds.connectAttr(plug, adapter + '.matrixIn[1]', force=True)
    neck.head_skinning_setup('C_headSkinning_JNT', rest=head_skin_rest)

    target = 'C_neck00_CTL'
    cmds.addAttr(target + '.SpaceFollow', edit=True, enumName='localChest:body:masterWalk')
    source = target.replace('_CTL', '_SourcesSpace_PMT')
    condition = cmds.createNode('condition', name='C_neck00_Space02_CON', ss=True)
    cmds.setAttr(condition + '.firstTerm', 2)
    cmds.setAttr(condition + '.colorIfTrueR', 1)
    cmds.setAttr(condition + '.colorIfFalseR', 0)
    cmds.connectAttr(target + '.SpaceFollow', condition + '.secondTerm')
    cmds.connectAttr(condition + '.outColorR', source + '.target[2].weight')
    offset = matrix_manager.get_offset_matrix('C_neck00_GRP', 'C_masterwalk_CTL')
    cmds.setAttr(source + '.target[2].offsetMatrix', offset, type='matrix')
    cmds.connectAttr('C_masterwalk_CTL.worldMatrix[0]', source + '.target[2].targetMatrix')
    return {'spine': spine_controls, 'neck': neck_controls, 'body_pivot': spine.body_pivot_ctl,
            'head': neck.head_ctl, 'skin_nodes_rebuilt': False}
