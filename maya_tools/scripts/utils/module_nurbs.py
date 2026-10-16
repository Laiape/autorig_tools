"""Keep construction NURBS inside their owning module without changing spaces."""
from functools import wraps

from maya import cmds
import maya.api.OpenMaya as om


def _nurbs_shapes():
    result = {}
    for kind in (om.MFn.kNurbsCurve, om.MFn.kNurbsSurface):
        iterator = om.MItDependencyNodes(kind)
        while not iterator.isDone():
            node = iterator.thisNode()
            fn = om.MFnDagNode(node)
            result[fn.uuid().asString()] = om.MObjectHandle(node)
            iterator.next()
    return result


def _path(handle):
    return om.MFnDagNode(handle.object()).fullPathName()


def animator_indicator_control(transform):
    """Resolve display-only PV/eye lines from their native endpoint drivers."""
    shapes = cmds.listRelatives(transform, shapes=True, noIntermediate=True,
                               fullPath=True, type='nurbsCurve') or []
    if len(shapes) != 1 or cmds.getAttr(transform+'.inheritsTransform'):
        return None
    if not cmds.getAttr(transform+'.overrideEnabled') or cmds.getAttr(transform+'.overrideDisplayType') != 2:
        return None
    shape = shapes[0]
    selection = om.MSelectionList(); selection.add(shape)
    curve = om.MFnNurbsCurve(selection.getDagPath(0))
    if curve.degree != 1 or curve.numCVs != 2:
        return None
    if any(cmds.listConnections(shape+'.'+plug, source=False, destination=True)
           for plug in ('worldSpace', 'local')):
        return None
    controls = set()
    for index in (0, 1):
        rows = [node for axis in ('xValue','yValue','zValue')
                for node in (cmds.listConnections('%s.controlPoints[%d].%s' % (shape, index, axis),
                             source=True, destination=False, type='rowFromMatrix') or [])]
        if len(set(rows)) != 1 or cmds.getAttr(rows[0]+'.input') != 3:
            return None
        sources = cmds.listConnections(rows[0]+'.matrix', source=True, destination=False, plugs=True) or []
        if len(sources) > 1:
            return None
        # Analytic limbs can feed a computed matrix at the bone endpoint.
        if not sources or not sources[0].endswith(('.worldMatrix', '.worldMatrix[0]')):
            continue
        node = sources[0].rsplit('.', 1)[0]
        if node.rsplit('|', 1)[-1].lower().endswith(('_ctl', '_ctrl')):
            controls.update(cmds.ls(node, long=True, type='transform') or [])
    return next(iter(controls)) if len(controls) == 1 else None


def restore_animator_indicators(root=None):
    """Restore misplaced display lines below modules_GRP in existing rigs.

    Reparenting is one explicit undoable action. Keep world CV inputs, local
    channels, visibility and deformation untouched; skip locked/referenced nodes.
    """
    if root is not None:
        roots = cmds.ls(root, long=True, type='transform') or []
        if len(roots) != 1:
            raise ValueError('Choose one character root.')
        shapes = cmds.ls(roots[0], dag=True, long=True, type='nurbsCurve') or []
    else:
        shapes = cmds.ls(long=True, type='nurbsCurve') or []
    planned = {}
    skipped = []
    for shape in shapes:
        parent = (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
        if not parent or not any(p.rsplit(':', 1)[-1] == 'modules_GRP' for p in parent.split('|')):
            continue
        control = animator_indicator_control(parent)
        if not control:
            continue
        if cmds.referenceQuery(parent, isNodeReferenced=True) or cmds.lockNode(parent, query=True, lock=True)[0]:
            skipped.append(parent)
            continue
        planned[parent] = control
    selection = []
    for item in cmds.ls(selection=True, long=True) or []:
        node, separator, component = item.partition('.')
        selection.append((cmds.ls(node, uuid=True)[0], separator+component))
    moved = []
    cmds.undoInfo(openChunk=True, chunkName='Restore PV and eye indicator curves')
    try:
        for curve, control in planned.items():
            old_parent = cmds.listRelatives(curve, parent=True, fullPath=True)[0]
            new = cmds.parent(curve, control, relative=True)[0]
            moved.append((cmds.ls(new, long=True)[0], old_parent))
    except Exception:
        for curve, old_parent in reversed(moved):
            cmds.parent(curve, old_parent, relative=True)
        raise
    finally:
        if selection:
            current = [path+component for uuid, component in selection
                       for path in (cmds.ls(uuid, long=True) or [])]
            cmds.select(current, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(closeChunk=True)
    return {'restored': [curve for curve, old_parent in moved], 'skipped': skipped}


def organize_nurbs(module, shapes):
    """Parent internal curve/surface transforms below ``module``.

    ``shapes`` contains shape names or MObjectHandles, including intermediate
    shapes. Controller shapes and animator-facing PV/eye lines keep their
    animation hierarchy. For geometry in
    an existing space, a transform under the module follows the original
    parent's world matrix; relative parenting keeps TRS, OPM, parentMatrix and
    skin/deformer input coordinates unchanged, including at future frames.
    """
    module = (cmds.ls(module, long=True) or [None])[0]
    if not module:
        raise ValueError("The owning module group does not exist")
    transforms = {}
    for shape in shapes:
        if isinstance(shape, om.MObjectHandle):
            if not shape.isValid() or not shape.isAlive():
                continue
            path = _path(shape)
        else:
            path = shape
        parents = cmds.listRelatives(path, allParents=True, fullPath=True) or []
        if len(parents) != 1:
            # An instanced shape has several owners; leave its existing spaces.
            continue
        transform = parents[0]
        if cmds.nodeType(transform) != "transform":
            continue
        if transform.rsplit("|", 1)[-1].lower().endswith(("_ctl", "_ctrl")) or animator_indicator_control(transform):
            continue
        selection = om.MSelectionList(); selection.add(transform)
        handle = om.MObjectHandle(selection.getDependNode(0))
        transforms[handle.hashCode()] = handle
    ordered = sorted(transforms.values(), key=lambda h: _path(h).count("|"))
    group = None
    spaces = {}
    moved = []
    for handle in ordered:
        transform = _path(handle)
        if transform.startswith(module + "|"):
            continue
        if group is None:
            group = cmds.createNode("transform", name=module.rsplit("|", 1)[-1].replace("Module_GRP", "Nurbs_GRP"), parent=module)
            cmds.setAttr(group + ".inheritsTransform", False)
        parent = (cmds.listRelatives(transform, parent=True, fullPath=True) or [None])[0]
        destination = group
        if parent:
            if parent not in spaces:
                space = cmds.createNode("transform", name=parent.rsplit("|", 1)[-1] + "_NurbsSpace_GRP", parent=group)
                cmds.setAttr(space + ".inheritsTransform", False)
                cmds.connectAttr(parent + ".worldMatrix[0]", space + ".offsetParentMatrix")
                spaces[parent] = space
            destination = spaces[parent]
        cmds.parent(transform, destination, relative=True)
        moved.append(_path(handle))
    return moved


def organize_module_nurbs(make):
    """Organize every internal NURBS created by a module's complete make call."""
    @wraps(make)
    def wrapped(self, *args, **kwargs):
        depth = getattr(self, "_module_nurbs_build_depth", 0)
        self._module_nurbs_build_depth = depth + 1
        before = _nurbs_shapes() if depth == 0 else None
        try:
            result = make(self, *args, **kwargs)
            if depth == 0:
                after = _nurbs_shapes()
                created = [handle for uuid, handle in after.items() if uuid not in before]
                module = getattr(self, "module_trn", None)
                if module and cmds.objExists(module):
                    organize_nurbs(module, created)
            return result
        finally:
            self._module_nurbs_build_depth = depth
    return wrapped
