"""Controller shape operations adapted from puiastre_tools (Apache-2.0).

Source: guidogonzalezc/puiastre_tools, scripts/puiastreTools/utils/curve_tool.py
Revision: 36a2acd4f57d8d5f65db9c38c0493dcf07330a5d
Adapted mirror_shapes and replace_shape_colored: native undo, curve-only edits,
namespaces, geometry snapshots and preservation of controller transforms.
"""
from contextlib import contextmanager

import maya.cmds as cmds


_DISPLAY = ('overrideEnabled', 'overrideRGBColors', 'overrideColor',
            'overrideColorRGB', 'overrideDisplayType', 'lineWidth', 'alwaysDrawOnTop')


def _curves(node):
    return cmds.listRelatives(node, shapes=True, noIntermediate=True,
                              type='nurbsCurve', fullPath=True) or []


def _transform(node):
    matches = cmds.ls(node, long=True, objectsOnly=True) or []
    if len(matches) != 1:
        raise ValueError('Select an unambiguous controller: %s' % node)
    node = matches[0]
    if cmds.nodeType(node) == 'nurbsCurve':
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    if not cmds.objectType(node, isAType='transform'):
        raise ValueError('Expected a controller transform: %s' % node)
    return node


def _editable(target):
    nodes = [target] + _curves(target)
    for node in nodes:
        if cmds.referenceQuery(node, isNodeReferenced=True):
            raise ValueError('Referenced controller is not editable: %s' % target)
        if cmds.lockNode(node, query=True, lock=True)[0]:
            raise ValueError('Locked controller or shape: %s' % node)
        if len(cmds.listRelatives(node, allParents=True) or []) > 1:
            raise ValueError('Instanced controller or shape: %s' % node)
    for shape in nodes[1:]:
        for attr in ('create', 'controlPoints'):
            if cmds.listConnections(shape + '.' + attr, source=True, destination=False):
                raise ValueError('Shape has construction history or driven CVs: %s' % shape)
        if cmds.listConnections(shape, source=False, destination=True, plugs=True,
                                type='geometryFilter'):
            raise ValueError('Shape drives a deformer: %s' % shape)
        for attr in ('local', 'worldSpace'):
            if cmds.listConnections(shape + '.' + attr, source=False, destination=True):
                raise ValueError('Shape has geometry consumers: %s' % shape)


def _display(source, target, color=None):
    for attr in _DISPLAY:
        plug = target + '.' + attr
        if not cmds.attributeQuery(attr, node=source, exists=True):
            continue
        if not cmds.getAttr(plug, settable=True):
            raise ValueError('Display attribute is locked or connected: %s' % plug)
        value = cmds.getAttr(source + '.' + attr)
        if isinstance(value, list):
            cmds.setAttr(plug, *value[0], type='double3')
        else:
            cmds.setAttr(plug, value)
    if color is not None:
        cmds.setAttr(target + '.overrideEnabled', True)
        cmds.setAttr(target + '.overrideRGBColors', False)
        cmds.setAttr(target + '.overrideColor', color)


@contextmanager
def _operation(name):
    selection = cmds.ls(selection=True, long=True) or []
    if not cmds.undoInfo(query=True, state=True):
        raise RuntimeError('Enable Maya Undo before editing controller shapes.')
    cmds.undoInfo(openChunk=True, chunkName=name)
    try:
        yield
        if (cmds.ls(selection=True, long=True) or []) != selection:
            cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    except Exception:
        cmds.undoInfo(closeChunk=True)
        if cmds.undoInfo(query=True, state=True) and cmds.undoInfo(query=True, undoName=True) == name:
            cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)


def _replace(source, target, mirror=False, color=None):
    """Snapshot each source curve without duplicating its rig hierarchy."""
    old_shapes = _curves(target)
    new_shapes = []
    for shape in _curves(source):
        new_shape = cmds.createNode('nurbsCurve', parent=target, skipSelect=True)
        new_shapes.append(new_shape)
        # Force the local curve data before disconnecting. This retains degree,
        # knots, rational weights and form and uses only undoable Maya commands.
        cmds.connectAttr(shape + '.local', new_shape + '.create')
        cmds.dgeval(new_shape + '.local')
        cmds.disconnectAttr(shape + '.local', new_shape + '.create')
        if mirror:
            source_cvs = cmds.ls(shape + '.cv[*]', flatten=True) or []
            for index, cv in enumerate(source_cvs):
                x, y, z = cmds.pointPosition(cv, world=True)
                cmds.xform(new_shape + '.cv[%d]' % index,
                           worldSpace=True, translation=(-x, y, z))
        shape_color = color
        if mirror and cmds.getAttr(shape + '.overrideEnabled') and not cmds.getAttr(shape + '.overrideRGBColors'):
            index = cmds.getAttr(shape + '.overrideColor')
            shape_color = {6: 13, 18: 4}.get(index, index)
        _display(shape, new_shape, shape_color)
    if old_shapes:
        cmds.delete(old_shapes)
    leaf = target.rsplit('|', 1)[-1]
    for index, shape in enumerate(new_shapes):
        cmds.rename(shape, leaf + ('Shape' if index == 0 else 'Shape%d' % index))


def mirror_shapes(controllers=None):
    """Mirror all L_*_CTL curves to their R_ peers across world X=0.

    Optional controllers limits the sources. Controller transforms, animation,
    hierarchy and non-curve shapes are preserved. Unsafe targets are skipped.
    """
    sources = controllers if controllers is not None else cmds.ls(type='transform', long=True)
    pairs = []
    for node in sources or []:
        source = _transform(node)
        leaf = source.rsplit('|', 1)[-1]
        namespace, _, name = leaf.rpartition(':')
        if not name.startswith('L_') or not name.endswith('_CTL') or not _curves(source):
            continue
        peer = (namespace + ':' if namespace else '') + 'R_' + name[2:]
        sibling = source.rsplit('|', 1)[0] + '|' + peer
        matches = [sibling] if cmds.objExists(sibling) else (cmds.ls(peer, long=True, type='transform') or [])
        if len(matches) != 1:
            cmds.warning('Missing or ambiguous mirror target for %s: %s' % (source, peer))
            continue
        target = matches[0]
        try:
            _editable(target)
        except ValueError as error:
            cmds.warning(str(error))
            continue
        pairs.append((source, target))
    if not pairs:
        cmds.warning('No editable L_/R_ controller pairs found.')
        return []
    with _operation('Mirror Controller Shapes'):
        for source, target in pairs:
            color = None
            if cmds.getAttr(source + '.overrideEnabled') and not cmds.getAttr(source + '.overrideRGBColors'):
                index = cmds.getAttr(source + '.overrideColor')
                color = {6: 13, 18: 4}.get(index, index)
            _display(source, target, color)
            _replace(source, target, mirror=True)
    return [target for _, target in pairs]


def replace_shape_colored():
    """Copy first selected controller's local shapes to all following targets.

    L_/R_/C_ targets use blue (6), red (13) and yellow (17), respectively.
    Source and target transforms and non-curve shapes are preserved.
    """
    selection = cmds.ls(selection=True, long=True) or []
    if len(selection) < 2:
        cmds.warning('Select the source first, followed by one or more targets.')
        return []
    source = _transform(selection[0])
    if not _curves(source):
        cmds.warning('Source has no visible NURBS curve shapes: %s' % source)
        return []
    targets = []
    for node in selection[1:]:
        try:
            target = _transform(node)
            if target == source or target in targets:
                continue
            _editable(target)
            targets.append(target)
        except ValueError as error:
            cmds.warning(str(error))
    if not targets:
        return []
    with _operation('Replace Controller Shapes'):
        for target in targets:
            name = target.rsplit('|', 1)[-1].rsplit(':', 1)[-1]
            color = {'L': 6, 'R': 13, 'C': 17}.get(name[:1])
            if color is not None:
                for attr in ('overrideEnabled', 'overrideRGBColors', 'overrideColor'):
                    if not cmds.getAttr(target + '.' + attr, settable=True):
                        raise ValueError('Display attribute is locked or connected: %s.%s' % (target, attr))
                cmds.setAttr(target + '.overrideEnabled', True)
                cmds.setAttr(target + '.overrideRGBColors', False)
                cmds.setAttr(target + '.overrideColor', color)
            _replace(source, target, color=color)
    return targets
