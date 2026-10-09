# -*- coding: utf-8 -*-
"""Create configured Proximity Wraps with multiple drivers."""
import re
import maya.cmds as cmds


SETTINGS = {
    "envelope": 1,
    "maxDrivers": 5,
    "falloffScale": 1,
    "dropoffRateScale": 0,
    "scaleCompensation": 1,
    "wrapMode": 1,          # Surface
    "coordinateFrames": 0,  # Driver
    "smoothNormals": 5,
    "spanSamples": 2,
    "smoothInfluences": 20,
    "softNormalization": False,
    "useBindTags": False,
}


def mesh_shape(node):
    matches = cmds.ls(node, long=True) or []
    if len(matches) != 1 or "." in matches[0]:
        raise RuntimeError("Selecciona objetos completos y con nombres unicos.")
    node = matches[0]
    if cmds.nodeType(node) == "mesh":
        shapes = [node] if not cmds.getAttr(node + ".intermediateObject") else []
    elif cmds.nodeType(node) == "transform":
        shapes = cmds.listRelatives(
            node, shapes=True, noIntermediate=True, fullPath=True, type="mesh"
        ) or []
    else:
        shapes = []
    if len(shapes) != 1:
        raise RuntimeError("Selecciona una mesh individual, no un grupo: " + node)
    if cmds.referenceQuery(shapes[0], isNodeReferenced=True):
        raise RuntimeError("Este script trabaja con meshes locales: " + node)
    if len(cmds.ls(shapes[0], long=True, allPaths=True) or []) != 1:
        raise RuntimeError("No se admiten meshes instanciadas: " + node)
    return shapes[0]


def direct_deformers(shape):
    """Filter history by actual deformer membership, excluding driver history."""
    result = []
    for node in cmds.listHistory(shape, pruneDagObjects=True) or []:
        if cmds.nodeType(node) not in ("skinCluster", "proximityWrap"):
            continue
        geometries = cmds.deformer(node, query=True, geometry=True) or []
        members = set()
        for geometry in geometries:
            resolved = cmds.ls(geometry, long=True) or []
            if len(resolved) != 1:
                raise RuntimeError("No se pudo resolver la geometria de " + node)
            member = resolved[0]
            if cmds.nodeType(member) == "transform":
                members.update(cmds.listRelatives(
                    member, shapes=True, noIntermediate=True, fullPath=True
                ) or [])
            else:
                members.add(member)
        if shape in members:
            result.append((node, members))
    return result


def apply_to_selected(drivers):
    if not cmds.undoInfo(query=True, state=True):
        raise RuntimeError("Activa Undo en Maya antes de ejecutar el script.")
    if isinstance(drivers, str):
        drivers = [drivers]
    drivers = list(dict.fromkeys(mesh_shape(node) for node in drivers))
    if not drivers:
        raise RuntimeError("Carga al menos una mesh como origen.")
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        raise RuntimeError("Selecciona los cinturones que quieres procesar.")
    targets = list(dict.fromkeys(mesh_shape(node) for node in selection))
    if set(drivers).intersection(targets):
        raise RuntimeError("La seleccion de cinturones no debe incluir meshes de origen.")

    # Validate everything before deleting any node.
    plans = []
    for shape in targets:
        if cmds.lockNode(shape, query=True, lock=True)[0]:
            raise RuntimeError("Mesh bloqueada: " + shape)
        deformers = direct_deformers(shape)
        for node, members in deformers:
            if members != {shape}:
                raise RuntimeError(
                    "{} afecta a varias meshes. No se ha modificado nada.".format(node)
                )
            if (cmds.referenceQuery(node, isNodeReferenced=True)
                    or cmds.lockNode(node, query=True, lock=True)[0]):
                raise RuntimeError("Deformer referenciado o bloqueado: " + node)
        plans.append((shape, [node for node, _ in deformers]))

    created = []
    failure = None
    changed = False
    cmds.undoInfo(openChunk=True, chunkName="Cinturones_ProximityWrap")
    try:
        for shape, old_nodes in plans:
            if old_nodes:
                changed = True
                cmds.delete(old_nodes)
            parent = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
            short_name = parent.rsplit("|", 1)[-1]
            name = re.sub(r"[^A-Za-z0-9_:]", "_", short_name) + "_PRX"
            # Only the belt receives the deformer; drivers are added separately.
            node = cmds.deformer(shape, type="proximityWrap", name=name, after=True)[0]
            changed = True
            created.append(node)
            for attr, value in SETTINGS.items():
                cmds.setAttr(node + "." + attr, value)
            cmds.proximityWrap(
                node, edit=True, addDrivers=drivers, applyUserDefaults=False
            )
            indices = cmds.proximityWrap(node, query=True, driverIndices=True) or []
            if len(indices) != len(drivers):
                raise RuntimeError("No se han conectado todos los drivers a " + node)
            for attr, value in SETTINGS.items():
                if cmds.getAttr(node + "." + attr) != value:
                    raise RuntimeError("Ajuste incorrecto: " + node + "." + attr)
        cmds.select(selection, replace=True)
    except Exception as exc:
        failure = exc
    finally:
        cmds.undoInfo(closeChunk=True)
    if failure is not None:
        if changed:
            cmds.undo()
        raise RuntimeError("No se ha completado el montaje: {}".format(failure))
    for node in created:
        print("Creado: {} | drivers: {}".format(node, ", ".join(drivers)))
    return created


def show_window():
    window = "cinturonesProximityWrapUI"
    if cmds.window(window, exists=True):
        cmds.deleteUI(window)
    cmds.window(window, title="Cinturones - Proximity Wrap", sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(label="1. En pose de bind, selecciona una o varias meshes de origen.", align="left")
    field = cmds.textScrollList(height=100, allowMultiSelection=True)
    state = {"drivers": []}

    def load_driver(*unused):
        try:
            selected = cmds.ls(selection=True, long=True) or []
            if not selected:
                raise RuntimeError("Selecciona una o varias meshes de origen.")
            drivers = list(dict.fromkeys(mesh_shape(node) for node in selected))
            state["drivers"] = drivers
            cmds.textScrollList(field, edit=True, removeAll=True)
            cmds.textScrollList(field, edit=True, append=drivers)
        except Exception as exc:
            cmds.warning(str(exc))

    def apply(*unused):
        try:
            if not state["drivers"]:
                raise RuntimeError("Carga primero las meshes de origen.")
            nodes = apply_to_selected(state["drivers"])
            cmds.text(status, edit=True, label="Creados {} deformers. Un Undo revierte el lote.".format(len(nodes)))
        except Exception as exc:
            cmds.warning(str(exc))
            cmds.text(status, edit=True, label="Error: consulta el Script Editor.")

    cmds.button(label="Cargar origenes seleccionados (reemplaza la lista)", command=load_driver)
    cmds.separator(height=10)
    cmds.text(label="2. Selecciona las meshes de los cinturones y aplica.", align="left")
    cmds.text(label="Borra sus skinClusters y Proximity Wrap anteriores.", align="left")
    cmds.text(label="Surface | Normals 5 | Influences 20 | Nombre: <mesh>_PRX", align="left")
    cmds.button(label="Aplicar a cinturones seleccionados", height=36, command=apply)
    status = cmds.text(label="Listo.", align="left")
    cmds.showWindow(window)


