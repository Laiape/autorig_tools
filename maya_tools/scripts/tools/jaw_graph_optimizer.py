"""Upgrade owned native lip orientation graphs without rebuilding skin or controls."""
import re

from maya import cmds


_IDENTITY = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)


def _source(plug):
    return cmds.connectionInfo(plug, sourceFromDestination=True) or ''


def _constant(plug):
    if _source(plug):
        raise ValueError('Animated or externally driven setting: ' + plug)
    return cmds.getAttr(plug)


def optimize(namespace=''):
    """Apply the current builder's orientation layout as one undoable transaction.

    Only recognized AutoRig nodes with their authored inputs are eligible.
    The uvPin position path, equal corner rotation interpolations and equal
    rest-compensated corner frames are shared. Zero-weight corner blends are
    bypassed. All singularity guards, rest offsets and skin joints are retained.
    Returns deleted node names; running it again makes no further edits.
    """
    prefix = namespace.rstrip(':') + ':' if namespace else ''
    pending, removed, rewired = set(), [], []

    def nodes(pattern, kind):
        return sorted(cmds.ls(prefix + pattern, type=kind) or [])

    def local(node):
        return node[len(prefix):]

    def redirect(old, new):
        for destination in cmds.listConnections(old, source=False, destination=True,
                                                plugs=True, skipConversionNodes=False) or []:
            settings = {}
            target = re.fullmatch(r'(.+\.target\[\d+\])\.targetMatrix', destination)
            if target and cmds.nodeType(destination.split('.', 1)[0]) == 'blendMatrix':
                # Disconnecting targetMatrix can delete its entire multi element.
                # Preserve the component weights and their drivers before force
                # reconnecting, otherwise Maya restores the default weights of 1.
                for attr in ('weight', 'translateWeight', 'rotateWeight',
                             'scaleWeight', 'shearWeight', 'useMatrix'):
                    plug = target[1] + '.' + attr
                    settings[plug] = (_source(plug), cmds.getAttr(plug))
            cmds.connectAttr(new, destination, force=True)
            for plug, (source, value) in settings.items():
                if source:
                    if not cmds.isConnected(source, plug):
                        cmds.connectAttr(source, plug, force=True)
                else:
                    cmds.setAttr(plug, value)
            rewired.append((old, new, destination))

    undo = cmds.undoInfo(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=True)
    cmds.undoInfo(openChunk=True, chunkName='Optimize jaw orientation')
    try:
        for aim in nodes('*Lip*Vector_AMX', 'aimMatrix'):
            if not re.fullmatch(r'[LRC]_(upper|lower)Lip\d+Vector_AMX', local(aim)):
                continue
            compose = aim.removesuffix('Vector_AMX') + 'Position_CMX'
            position = aim.removesuffix('Vector_AMX') + 'Pin_TFM'
            if not cmds.objExists(compose) or not cmds.objExists(position):
                continue
            if (_source(aim + '.inputMatrix') != compose + '.outputMatrix' or
                    _source(compose + '.inputTranslate') != position + '.output'):
                continue
            pin = _source(position + '.input')
            if not pin or cmds.nodeType(pin.split('.', 1)[0]) != 'uvPin':
                continue
            if cmds.referenceQuery(aim, isNodeReferenced=True):
                continue
            # Retain the generic compose path if an artist extended it.
            if (_source(compose + '.useEulerRotation') or
                    not cmds.getAttr(compose + '.useEulerRotation')):
                continue
            if any(cmds.listConnections(compose + '.input' + attr,
                                        source=True, destination=False) or
                   any(abs(v - expected) > 1e-12 for v in cmds.getAttr(compose + '.input' + attr)[0])
                   for attr, expected in (('Rotate', 0.), ('Scale', 1.), ('Shear', 0.))):
                continue
            cmds.connectAttr(pin, aim + '.inputMatrix', force=True)
            rewired.append((compose + '.outputMatrix', pin, aim + '.inputMatrix'))
            if not cmds.listConnections(compose + '.outputMatrix', source=False, destination=True):
                pending.add(compose)

        rotations = {}
        for node in nodes('*Lip*CornerRotation_BMX', 'blendMatrix'):
            if not re.fullmatch(r'[LR]_(upper|lower)Lip\d+CornerRotation_BMX', local(node)):
                continue
            if cmds.referenceQuery(node, isNodeReferenced=True) or _source(node + '.inputMatrix'):
                continue
            if tuple(cmds.getAttr(node + '.inputMatrix')) != _IDENTITY:
                continue
            if cmds.getAttr(node + '.target', multiIndices=True) != [0]:
                continue
            try:
                settings = tuple(_constant(node + '.' + attr) for attr in (
                    'nodeState', 'envelope', 'target[0].weight', 'target[0].translateWeight',
                    'target[0].rotateWeight', 'target[0].scaleWeight', 'target[0].shearWeight',
                    'target[0].useMatrix'))
            except ValueError:
                continue
            key = (_source(node + '.target[0].targetMatrix'), settings)
            if not key[0] or settings[0] != 0:
                continue
            if key in rotations:
                redirect(node + '.outputMatrix', rotations[key] + '.outputMatrix')
                pending.add(node)
            else:
                rotations[key] = node

        frames = {}
        for node in nodes('C_lipCorner*Frame_MMX', 'multMatrix'):
            if not re.fullmatch(r'C_lipCorner\d+Frame_MMX', local(node)):
                continue
            if cmds.referenceQuery(node, isNodeReferenced=True):
                continue
            if cmds.getAttr(node + '.matrixIn', multiIndices=True) != [0, 1]:
                continue
            if _source(node + '.matrixIn[0]') or _source(node + '.nodeState'):
                continue
            if cmds.getAttr(node + '.nodeState') != 0:
                continue
            key = (_source(node + '.matrixIn[1]'), tuple(cmds.getAttr(node + '.matrixIn[0]')))
            if key[0] not in (prefix + 'L_lipCorner_CTL.worldMatrix[0]',
                              prefix + 'R_lipCorner_CTL.worldMatrix[0]'):
                continue
            if key in frames:
                redirect(node + '.matrixSum', frames[key] + '.matrixSum')
                pending.add(node)
            else:
                frames[key] = node

        for node in nodes('C_*LipCorner*Blend_BMX', 'blendMatrix'):
            if not re.fullmatch(r'C_(upper|lower)LipCorner\d+Blend_BMX', local(node)):
                continue
            if cmds.referenceQuery(node, isNodeReferenced=True):
                continue
            if cmds.getAttr(node + '.target', multiIndices=True) != [0]:
                continue
            try:
                weights = [_constant(node + '.target[0].' + attr) for attr in (
                    'translateWeight', 'rotateWeight', 'scaleWeight', 'shearWeight')]
                state = _constant(node + '.nodeState')
            except ValueError:
                continue
            original = _source(node + '.inputMatrix')
            if original and state == 0 and weights == [0., 0., 0., 0.]:
                redirect(node + '.outputMatrix', original)
                pending.add(node)

        for node in sorted(pending):
            # Keep custom metadata consumers and any other artist extensions.
            if not cmds.listConnections(node, source=False, destination=True):
                cmds.delete(node)
                removed.append(node)
        cmds.dgdirty(allPlugs=True)
    except BaseException:
        cmds.undoInfo(closeChunk=True)
        cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    finally:
        cmds.undoInfo(stateWithoutFlush=undo)
    return {'removed': removed, 'rewired': rewired}
