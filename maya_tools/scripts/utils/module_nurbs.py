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


def organize_nurbs(module, shapes):
    """Parent internal curve/surface transforms below ``module``.

    ``shapes`` contains shape names or MObjectHandles, including intermediate
    shapes. Controller shapes keep their animation hierarchy. For geometry in
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
        if transform.rsplit("|", 1)[-1].lower().endswith(("_ctl", "_ctrl")):
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
