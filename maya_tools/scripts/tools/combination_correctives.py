"""Native combination targets with captured poses and rebuild metadata."""
import json
import re
import copy
from maya import cmds
from maya_tools.scripts.tools import pose_blendshapes as poses


def data(record):
    if not cmds.attributeQuery('combinationData', node=record, exists=True):
        return None
    snapshot = json.loads(cmds.getAttr(record + '.combinationData'))
    if cmds.attributeQuery('captureControllers', node=record, exists=True):
        for i, capture in enumerate(snapshot['captures']):
            nodes = cmds.listConnections(record + '.captureControllers[%d]' % i, s=True, d=False) or []
            if len(nodes) != 1:
                raise ValueError('Missing combination controller binding.')
            capture['controller'] = nodes[0]
    return snapshot


def restore(record, bs, index, snapshot, allocate_weights=False):
    drivers = snapshot['drivers']
    if len(set(drivers)) != len(drivers) or len(drivers) < 2 or index in drivers:
        raise ValueError('Choose at least two distinct existing driver targets.')
    available = cmds.getAttr(bs + '.weight', multiIndices=True) or []
    if allocate_weights:
        for driver in drivers:
            if driver not in available:
                cmds.setAttr(bs + '.weight[%d]' % driver, 0)
        available = cmds.getAttr(bs + '.weight', multiIndices=True) or []
    if any(i not in available for i in drivers):
        raise ValueError('A combination driver target is missing.')
    plug = bs + '.weight[%d]' % index
    source = cmds.connectionInfo(plug, sourceFromDestination=True)
    if source:
        cmds.disconnectAttr(source, plug)
    owned = cmds.listConnections(record + '.driverNodes', source=True, destination=False) or []
    if owned:
        cmds.delete(owned)
    for i in cmds.getAttr(record + '.driverNodes', multiIndices=True) or []:
        cmds.removeMultiInstance(record + '.driverNodes[%d]' % i, b=True)
    node = cmds.createNode('combinationShape', name=record + '_combine')
    cmds.setAttr(node + '.combinationMethod', 0)
    for position, driver in enumerate(drivers):
        cmds.connectAttr(bs + '.weight[%d]' % driver, node + '.inputWeight[%d]' % position)
    cmds.connectAttr(node + '.outputWeight', plug)
    cmds.connectAttr(node + '.message', record + '.driverNodes[0]')
    poses._string(record, 'combinationData', json.dumps(snapshot))
    if not cmds.attributeQuery('captureControllers', node=record, exists=True):
        cmds.addAttr(record, longName='captureControllers', attributeType='message', multi=True)
    for i, capture in enumerate(snapshot['captures']):
        cmds.connectAttr(capture['controller'] + '.message', record + '.captureControllers[%d]' % i, force=True)
    return node


@poses.undoable
def create(mesh, bs, drivers, name='Combination_BLS'):
    poses._idle()
    drivers = list(drivers)
    if len(set(drivers)) < 2 or len(set(drivers)) != len(drivers):
        raise ValueError('Select at least two different saved targets.')
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', name) or name in dict(poses.targets(bs)).values():
        raise ValueError('Use a unique ASCII target name.')
    captures = {}
    first = None
    for index in drivers:
        record = poses.pose_record(bs, index)
        if not record:
            raise ValueError('Every driver needs a saved controller pose.')
        existing = data(record)
        samples = existing['captures'] if existing else [{
            'controller': poses.linked(record, 'controller'),
            'channels': json.loads(cmds.getAttr(record + '.channels'))}]
        for sample in samples:
            for channel in sample['channels']:
                key = (sample['controller'], channel['channel'])
                if key in captures and captures[key]['pose'] != channel['pose']:
                    raise ValueError('Driver targets require conflicting controller values.')
                captures[key] = channel
        first = first or record
    groups = {}
    for (control, channel), value in captures.items():
        groups.setdefault(control, []).append(value)
    snapshot = {'version': 1, 'drivers': drivers, 'method': 'multiply',
                'captures': [{'controller': c, 'channels': v} for c, v in groups.items()]}
    control = poses.linked(first, 'controller')
    index, _ = poses._create_pose_target(poses.mesh_transform(mesh), bs, control, json.loads(cmds.getAttr(first + '.channels')))
    record = poses.pose_record(bs, index)
    cmds.aliasAttr(name, bs + '.weight[%d]' % index)
    cmds.setAttr(record + '.targetName', name, type='string')
    restore(record, bs, index, snapshot)
    poses.go_to_pose(bs, index)
    poses.begin_edit(mesh, bs, index)
    return index, name


def go_to_pose(snapshot, neutral=False):
    changes = {}
    for capture in snapshot['captures']:
        for value in capture['channels']:
            plug = capture['controller'] + '.' + value['channel']
            if not cmds.objExists(plug) or not cmds.getAttr(plug, settable=True):
                raise ValueError('A captured combination channel is missing, locked or driven: ' + plug)
            changes[plug] = value['default' if neutral else 'pose']
    for plug, value in changes.items():
        cmds.setAttr(plug, value)


def consumers(bs, index):
    return [r for r in poses._find(poses.POSE_MARKER)
            if poses.linked(r, 'blendShape') == bs and data(r) and index in data(r)['drivers']]


def dependency_order(bs, index):
    """Validate the complete dependency graph before copying anything."""
    visited, visiting, order = set(), set(), []
    def visit(i):
        if i in visiting:
            raise ValueError('Combination dependency cycle.')
        if i in visited:
            return
        record = poses.pose_record(bs, i)
        if not record or i not in dict(poses.targets(bs)):
            raise ValueError('Missing saved corrective dependency: %d' % i)
        visiting.add(i)
        snapshot = data(record)
        for driver in snapshot['drivers'] if snapshot else []:
            visit(driver)
        visiting.remove(i); visited.add(i); order.append(i)
    visit(index)
    return order


def _unique_name(bs, desired):
    aliases = set(dict(poses.targets(bs)).values())
    candidate, i = desired, 2
    while candidate in aliases:
        candidate = desired.removesuffix('_BLS') + '_%02d_BLS' % i; i += 1
    return candidate


def _set_name(bs, index, name):
    name = _unique_name(bs, name)
    cmds.aliasAttr(name, bs + '.weight[%d]' % index)
    cmds.setAttr(poses.pose_record(bs, index) + '.targetName', name, type='string')
    return name


@poses.undoable
def mirror(mesh, bs, index):
    from maya_tools.scripts.tools import rig_roles, rig_validation
    poses._idle()
    mesh = poses.mesh_transform(mesh)
    order = dependency_order(bs, index)
    controls = {}
    for i in order:
        record = poses.pose_record(bs, i)
        snapshot = data(record)
        samples = snapshot['captures'] if snapshot else [{'controller': poses.linked(record, 'controller'),
                                                         'channels': json.loads(cmds.getAttr(record + '.channels'))}]
        for sample in samples:
            control = sample['controller']
            root = rig_roles.root_for(control)
            binding = next((b for b in rig_roles.bindings(root) if b['node'] == rig_roles.path(control)), None) if root else None
            leaf = control.rsplit('|',1)[-1].split(':')[-1]
            central = binding['side'] == 'C' if binding else leaf.startswith('C_')
            controls[control] = control if central else poses._right_controller(control)
    neutral, _ = rig_validation._neutral_values(rig_roles.root_for(mesh))
    neutral.update({bs + '.weight[%d]' % i: 0 for i, _ in poses.targets(bs)})
    selection = cmds.ls(selection=True, long=True) or []
    mapping = {}
    try:
        with poses._temporary_values(neutral):
            for i in order:
                record = poses.pose_record(bs, i)
                snapshot = data(record)
                source_control = poses.linked(record, 'controller')
                if not snapshot and controls[source_control] == source_control:
                    mapping[i] = i  # A central jaw driver is shared, not duplicated.
                    continue
                if not snapshot:
                    mapping[i] = poses.mirror_target(mesh, bs, i)[0]
                    continue
                base = poses._mesh_points(mesh)
                cmds.setAttr(bs + '.weight[%d]' % i, 1)
                corrected = poses._mesh_points(mesh)
                cmds.setAttr(bs + '.weight[%d]' % i, 0)
                deltas = poses._mirror_deltas(mesh, base, corrected)
                copied = copy.deepcopy(snapshot)
                copied['drivers'] = [mapping[d] for d in snapshot['drivers']]
                for sample in copied['captures']:
                    old = sample['controller']; new = controls[old]
                    if old != new:
                        sample['channels'] = poses._mirrored_channels(mesh, old, new, sample['channels'])
                    sample['controller'] = new
                first = copied['captures'][0]
                destination, _ = poses._create_pose_target(mesh, bs, first['controller'], first['channels'])
                name = _set_name(bs, destination, dict(poses.targets(bs))[i].removesuffix('_BLS') + '_Mirrored_BLS')
                restore(poses.pose_record(bs, destination), bs, destination, copied)
                with poses._temporary_values({bs + '.weight[%d]' % destination: 1}):
                    cmds.sculptTarget(bs, edit=True, target=destination)
                    try:
                        for vertex, delta in deltas.items():
                            cmds.move(delta.x, delta.y, delta.z, mesh+'.vtx[%d]' % vertex, relative=True, objectSpace=True)
                    finally:
                        cmds.sculptTarget(bs, edit=True, target=-1)
                mapping[i] = destination
        return mapping[index], dict(poses.targets(bs))[mapping[index]]
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)


@poses.undoable
def transfer(source_mesh, bs, index, target_mesh, destination_bs=None, controller_map=None, **options):
    from maya_tools.scripts.tools import corrective_transfer
    poses._idle()
    order = dependency_order(bs, index)
    controller_map = controller_map or {}
    # Resolve every captured controller before introducing destination nodes.
    controls = {}
    for i in order:
        record = poses.pose_record(bs, i)
        snapshot = data(record)
        samples = snapshot['captures'] if snapshot else [{'controller': poses.linked(record, 'controller')}]
        for sample in samples:
            control = sample['controller']
            controls[control] = corrective_transfer._destination_controller(control, target_mesh, controller_map.get(control))
    mapping, results = {}, {}
    for i in order:
        result = corrective_transfer.transfer_target(source_mesh, bs, i, target_mesh, destination_bs=destination_bs,
            controller=controls[poses.linked(poses.pose_record(bs, i), 'controller')], _single=True, **options)
        destination_bs = result['blendShape']
        mapping[i] = result['index']; results[i] = result
        snapshot = data(poses.pose_record(bs, i))
        if snapshot:
            copied = copy.deepcopy(snapshot)
            copied['drivers'] = [mapping[d] for d in snapshot['drivers']]
            for sample in copied['captures']:
                sample['controller'] = controls[sample['controller']]
            restore(poses.pose_record(destination_bs, result['index']), destination_bs, result['index'], copied)
    result = results[index]
    result['dependency_targets'] = mapping
    return result
