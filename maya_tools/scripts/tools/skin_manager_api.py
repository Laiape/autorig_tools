import glob
import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import os
import json
import re

try:
    from maya_tools.scripts.utils import data_manager
    HAS_RIG_UTILS = True
except ImportError:
    HAS_RIG_UTILS = False

class SkinManager(object):
    SCENE_DEFORMERS_KEY = "__scene_deformers__"

    def __init__(self):
        self.ext = ".skc"
        self.folder_path, self.asset_name = self.get_path_and_name()
        self.json_path = self.get_latest_version_path()

        # Configuración de atributos y tolerancia
        self.k_skin_attrs = ["skinningMethod", "normalizeWeights", "maintainMaxInfluences", "maxInfluences", "weightDistribution"]
        self.tolerance = 1e-5

    def get_latest_version_path(self):
        """
        Escanea la carpeta skin_clusters y devuelve el path del archivo con la versión más alta.
        Si no existe ninguno, devuelve la ruta para una v001 por defecto.
        """
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
            return os.path.join(self.folder_path, f"{self.asset_name}_v001{self.ext}")

        pattern = f"{self.asset_name}_v*{self.ext}"
        files = glob.glob(os.path.join(self.folder_path, pattern))

        if not files:
            return os.path.join(self.folder_path, f"{self.asset_name}_v001{self.ext}")

        highest_version = -1
        latest_file = files[0]

        for f in files:
            try:
                filename = os.path.basename(f)
                ver_part = filename.split("_v")[-1].split(self.ext)[0]
                
                if ver_part.isdigit():
                    version_num = int(ver_part)
                    if version_num > highest_version:
                        highest_version = version_num
                        latest_file = f
            except (ValueError, IndexError):
                continue

        return os.path.normpath(latest_file)


    def get_path_and_name(self):
        """Calcula la ruta del JSON basándose en la estructura del proyecto."""
        try:
            # assets vive junto a scripts: <...>/maya_tools/scripts -> <...>/maya_tools
            script_path = os.path.realpath(__file__)
            root_github = script_path.split(os.sep + "scripts")[0]
        except NameError:
            root_github = cmds.workspace(q=True, rd=True)

        char_name = "asset"
        
        all_assemblies = cmds.ls(assemblies=True)
        scene_assemblies = [
            obj for obj in all_assemblies 
            if not cmds.listRelatives(obj, type='camera')
        ]

        if scene_assemblies:
            char_name = scene_assemblies[-1]
        
        if HAS_RIG_UTILS:
            try:
                dm_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
                if dm_name: char_name = dm_name
            except Exception: pass

        path = os.path.join(root_github, "assets", char_name, "skin_clusters")
        return os.path.normpath(path), char_name

    # ----------------------------------------------------------------
    # --- OPENMAYA HELPERS (Referencia) ---
    # ----------------------------------------------------------------
    def _get_dag_path(self, node_name):
        sel = om.MSelectionList()
        try:
            sel.add(node_name)
            path = sel.getDagPath(0)
            if path.node().hasFn(om.MFn.kTransform):
                # A transform can contain original/intermediate shapes before
                # its visible output. Bake exports use stable transform names.
                shapes = cmds.listRelatives(path.fullPathName(), shapes=True,
                                            noIntermediate=True, fullPath=True,
                                            type="mesh") or []
                if len(shapes) == 1:
                    selection = om.MSelectionList()
                    selection.add(shapes[0])
                    return selection.getDagPath(0)
            return path
        except:
            return None

    def _get_scene_skin_clusters(self):
        """Returns a set with the names of all skinClusters currently in the scene."""
        it_dep = om.MItDependencyNodes(om.MFn.kSkinClusterFilter)
        scene_skins = set()
        while not it_dep.isDone():
            fn = om.MFnDependencyNode(it_dep.thisNode())
            scene_skins.add(fn.name())
            it_dep.next()
        return scene_skins

    def _get_skin_clusters(self, dag_path):
        """
        Retorna los skinClusters en orden de deformación (Stack Order).
        Inner (primero en aplicarse) -> Outer (ultimo en aplicarse).
        """
        history = cmds.listHistory(dag_path.fullPathName(), pruneDagObjects=True, interestLevel=2) or []
        skins = [x for x in history if cmds.nodeType(x) == "skinCluster"]
        return list(reversed(skins))

    def _get_meshes_from_skin(self, skin_mobj):
        """
        Devuelve los paths de la malla solo si el skinCluster deforma mallas (MFn.kMesh).
        Ignora automáticamente los skinClusters aplicados a curvas NURBS u otros.
        """
        try:
            fn_skin = oma.MFnSkinCluster(skin_mobj)
            geoms = fn_skin.getOutputGeometry()
            found_paths = []
            
            has_mesh = False

            for node in geoms:
                # 1. Si deforma una curva (NURBS), abortamos y descartamos este skin
                if node.hasFn(om.MFn.kNurbsCurve):
                    continue
                if node.hasFn(om.MFn.kNurbsSurface):
                    continue      
                # 2. Si es una malla de polígonos, la procesamos
                if node.hasFn(om.MFn.kMesh):
                    has_mesh = True
                    fn_dag = om.MFnDagNode(node)
                    
                    # Solo guardamos la malla visible, no el nodo intermedio (...ShapeOrig)
                    if not fn_dag.isIntermediateObject:
                        found_paths.append(fn_dag.getPath())

            # Si encontró mallas válidas las devuelve, si no, devuelve una lista vacía
            return found_paths if has_mesh else []

        except Exception as e:
            om.MGlobal.displayWarning(f"Error recuperando geometría del skin: {e}")
            return []

    # ----------------------------------------------------------------
    # --- EXPORT SKINS (Lógica Referencia: Sparse & Stack) ---
    # ----------------------------------------------------------------
    def _export_geometry(self, mesh_fn):
        """Snapshot en espacio local; exportar/importar en la misma pose de referencia."""
        counts, connects = mesh_fn.getVertices()
        return {
            "points": [[p.x, p.y, p.z] for p in mesh_fn.getPoints(om.MSpace.kObject)],
            "polygon_counts": list(counts),
            "polygon_connects": list(connects),
        }

    def _same_topology(self, mesh_fn, geometry):
        counts, connects = mesh_fn.getVertices()
        return (mesh_fn.numVertices == len(geometry["points"])
                and list(counts) == geometry["polygon_counts"]
                and list(connects) == geometry["polygon_connects"])

    def _closest_surface_map(self, geometry, target_points):
        """Una correspondencia baricéntrica por vértice, reutilizable para todo el stack."""
        # MMeshData mantiene la superficie en memoria sin crear nodos en escena.
        mesh_data = om.MFnMeshData().create()
        source_fn = om.MFnMesh()
        source_mesh = source_fn.create(
            [om.MPoint(*p) for p in geometry["points"]],
            geometry["polygon_counts"], geometry["polygon_connects"],
            parent=mesh_data)
        intersector = om.MMeshIntersector()
        intersector.create(source_mesh, om.MMatrix())
        mapping = []
        for point in target_points:
            hit = intersector.getClosestPoint(point)
            if hit is None:
                raise ValueError("No se encontró un punto en la superficie original")
            vertices = source_fn.getPolygonTriangleVertices(hit.face, hit.triangle)
            u, v = hit.barycentricCoords
            coefficients = [max(0.0, c) for c in (u, v, 1.0 - u - v)]
            total = sum(coefficients)
            mapping.append(tuple((int(vertex), c / total)
                                 for vertex, c in zip(vertices, coefficients)))
        return mapping

    @staticmethod
    def _remap_weights(source_weights, stride, mapping):
        """Interpola pesos y blend weights sobre los triángulos originales."""
        result = [0.0] * (len(mapping) * stride)
        for target_index, samples in enumerate(mapping):
            target_offset = target_index * stride
            for source_index, coefficient in samples:
                source_offset = source_index * stride
                for influence in range(stride):
                    result[target_offset + influence] += (
                        source_weights[source_offset + influence] * coefficient)
        return result

    def _export_scene_deformers(self):
        """Snapshot geometry filters, settings, membership and connections.

        Captures sparse storable arrays and reports unsupported geometry/plugin
        values. Skin weights stay in the existing per-mesh skin section. This
        External geometry/plugin payloads are not included in the snapshot.
        """
        def export_attributes(fn):
            attributes = {}
            skipped = []
            errors = []

            def read_plug(plug):
                attr_fn = om.MFnAttribute(plug.attribute())
                if not attr_fn.storable or not attr_fn.readable:
                    return
                path = plug.partialName(
                    includeNonMandatoryIndices=True, includeInstancedIndices=True,
                    useAlias=False, useFullAttributePath=True, useLongNames=True)
                if path == "deformerData":
                    return  # Nonlinear handle output is derived from its settings.
                if fn.typeName == "skinCluster" and path.split("[", 1)[0] in (
                        "weightList", "blendWeights"):
                    return
                if plug.isArray:
                    for i in range(plug.numElements()):
                        read_plug(plug.elementByPhysicalIndex(i))
                    return
                if plug.isCompound:
                    for i in range(plug.numChildren()):
                        read_plug(plug.child(i))
                    return
                try:
                    data_type = cmds.getAttr(plug.name(), type=True)
                    # Opaque getAttr values print errors even when caught in Python.
                    if data_type not in (
                            "bool", "byte", "char", "short", "long", "enum",
                            "float", "double", "doubleAngle", "doubleLinear", "time",
                            "string", "matrix", "pointArray", "vectorArray",
                            "doubleArray", "Int32Array", "stringArray", "componentList"):
                        skipped.append({"attribute": path, "type": data_type})
                        return
                    value = cmds.getAttr(plug.name())
                    # Convert Maya tuples to JSON lists and reject plugin objects.
                    value = json.loads(json.dumps(value, allow_nan=False))
                    attributes[path] = {
                        "type": data_type, "value": value, "locked": plug.isLocked
                    }
                except Exception as exc:
                    errors.append({"attribute": path, "reason": str(exc)})

            for i in range(fn.attributeCount()):
                attr = fn.attribute(i)
                attr_fn = om.MFnAttribute(attr)
                if attr_fn.parent.isNull():
                    read_plug(fn.findPlug(attr, False))
            return attributes, skipped, errors

        nodes = []
        stacks = {}
        auxiliary_nodes = {}
        iterator = om.MItDependencyNodes(om.MFn.kGeometryFilt)
        while not iterator.isDone():
            obj = iterator.thisNode()
            fn = om.MFnDependencyNode(obj)
            name = fn.name()
            attributes, skipped, errors = export_attributes(fn)
            connections = []
            for plug in fn.getConnections():
                for source in plug.connectedTo(True, False):
                    connections.append({"source": source.name(), "destination": plug.name()})
                    # Nonlinear settings live on the handle shape, not the filter.
                    # Also keep handle transforms connected through matrix inputs.
                    if (plug.partialName(useLongNames=True) in ("deformerData", "matrix")
                            or om.MFnDependencyNode(source.node()).typeName == "clusterHandle"):
                        source_fn = om.MFnDependencyNode(source.node())
                        source_name = source_fn.name()
                        if source_name not in auxiliary_nodes:
                            values, unsupported, failures = export_attributes(source_fn)
                            auxiliary_nodes[source_name] = {
                                "name": source_name, "type": source_fn.typeName,
                                "attributes": values, "unsupported_attributes": unsupported,
                                "attribute_errors": failures,
                                "parent": (cmds.listRelatives(source_name, parent=True,
                                                              fullPath=True) or [None])[0],
                            }

            geometry_filter = oma.MFnGeometryFilter(obj)
            geometries = []
            for i in range(geometry_filter.numOutputConnections()):
                index = geometry_filter.indexForOutputConnection(i)
                path = geometry_filter.getPathAtIndex(index)
                shape = path.fullPathName()
                geometries.append({"index": index, "shape": shape})
                if shape not in stacks:
                    # Maya history is listed downstream to upstream; reverse it.
                    history = cmds.listHistory(shape, pruneDagObjects=True) or []
                    stack = []
                    for history_node in reversed(history):
                        selection = om.MSelectionList()
                        selection.add(history_node)
                        history_obj = selection.getDependNode(0)
                        if not history_obj.hasFn(om.MFn.kGeometryFilt):
                            continue
                        history_fn = oma.MFnGeometryFilter(history_obj)
                        outputs = [history_fn.getPathAtIndex(
                            history_fn.indexForOutputConnection(j)).fullPathName()
                            for j in range(history_fn.numOutputConnections())]
                        if shape in outputs and history_node not in stack:
                            stack.append(history_node)
                    stacks[shape] = stack
            members = []
            membership_mode = "component_tags"
            try:
                # Modern Maya deformers can use component tags without a set.
                deformer_set = geometry_filter.deformerSet
                if not deformer_set.isNull():
                    members = om.MFnSet(deformer_set).getMembers(False).getSelectionStrings()
                    membership_mode = "object_set"
            except RuntimeError:
                pass
            entry = {
                "name": name, "type": fn.typeName, "attributes": attributes,
                "connections": sorted(connections, key=lambda item: item["destination"]),
                "geometries": geometries, "members": list(members),
                "membership_mode": membership_mode,
                "unsupported_attributes": skipped, "attribute_errors": errors,
                "aliases": cmds.aliasAttr(name, query=True) or [],
            }
            if fn.typeName == "skinCluster":
                entry["weights_storage"] = "per_mesh_skin_section_if_in_export_scope"
            nodes.append(entry)
            iterator.next()
        return {"version": 1, "nodes": sorted(nodes, key=lambda item: item["name"]),
                "geometry_stacks": stacks,
                "auxiliary_nodes": sorted(auxiliary_nodes.values(), key=lambda item: item["name"])}

    @staticmethod
    def _resolve_deformer_node(name, geometry=False):
        """Resolve exact or unique short names; allow renamed output shapes."""
        matches = cmds.ls(name, long=True) or []
        if not matches:
            matches = cmds.ls(name.rsplit("|", 1)[-1], long=True) or []
        if len(matches) == 1:
            node = matches[0]
            if not geometry:
                return node
            if cmds.nodeType(node) == "transform":
                parent = node
            elif cmds.objectType(node, isAType="shape"):
                if not cmds.getAttr(node + ".intermediateObject"):
                    return node
                parent = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
            else:
                return None
        elif not matches and "|" in name:
            parent = SkinManager._resolve_deformer_node(name.rsplit("|", 1)[0])
        else:
            return None
        if geometry and parent and cmds.nodeType(parent) == "transform":
            shapes = cmds.listRelatives(parent, shapes=True, noIntermediate=True,
                                        fullPath=True) or []
            if len(shapes) == 1:
                return shapes[0]
        return None

    @staticmethod
    def _set_deformer_value(plug, data):
        value = data.get("value")
        if value is None:
            return
        data_type = data["type"]
        if data_type == "string":
            cmds.setAttr(plug, value, type="string")
        elif data_type == "matrix":
            cmds.setAttr(plug, *value, type="matrix")
        elif data_type in ("pointArray", "vectorArray", "doubleArray", "Int32Array",
                           "stringArray", "componentList"):
            cmds.setAttr(plug, len(value), *value, type=data_type)
        elif isinstance(value, (bool, int, float)):
            cmds.setAttr(plug, value)
        else:
            raise ValueError("Tipo no restaurable: " + data_type)

    def _import_scene_deformers(self, snapshot, replace_existing=False):
        """Recreate missing filters; let Maya build the geometry history wiring.

        Never reconnect exported input/original/output plugs: their intermediate
        shapes belong to the old history. Proximity drivers are bound with Maya's
        command, then saved driver parameters and external connections restored.
        """
        if not snapshot:
            return
        node_map = {}
        geometry_map = {}
        pending = []
        warnings = []
        created_count = 0
        auxiliary = {entry["name"]: entry for entry in snapshot.get("auxiliary_nodes", [])}

        def restore_auxiliary(name):
            existing = self._resolve_deformer_node(name)
            if existing:
                node_map[name] = existing
                return existing
            entry = auxiliary.get(name)
            if not entry:
                return None
            parent = entry.get("parent")
            if not parent and entry["type"].startswith("deform"):
                parent = name.rsplit("Shape", 1)[0]
            resolved_parent = restore_auxiliary(parent) if parent else None
            kwargs = {"name": name.rsplit("|", 1)[-1]}
            if resolved_parent:
                kwargs["parent"] = resolved_parent
            node = cmds.createNode(entry["type"], **kwargs)
            node_map[name] = node
            for attr, data in entry.get("attributes", {}).items():
                plug = node + "." + attr
                try:
                    if cmds.objExists(plug) and cmds.getAttr(plug, settable=True):
                        self._set_deformer_value(plug, data)
                except Exception as exc:
                    warnings.append("{}: {}".format(plug, exc))
            return node

        # Create all filters first, so inter-filter connections can resolve.
        for entry in snapshot.get("nodes", []):
            name, node_type = entry["name"], entry["type"]
            if node_type == "skinCluster":
                existing = self._resolve_deformer_node(name)
                if existing:
                    node_map[name] = existing
                continue  # Managed exclusively by the skin weights importer.
            existing = self._resolve_deformer_node(name)
            if existing:
                if cmds.nodeType(existing) != node_type:
                    warnings.append("{}: nombre ocupado por otro tipo; se salta.".format(name))
                    continue
                node_map[name] = existing
                if not replace_existing:
                    continue
            geometries = []
            index_map = {}
            for geometry in sorted(entry.get("geometries", []), key=lambda item: item["index"]):
                resolved = self._resolve_deformer_node(geometry["shape"], geometry=True)
                if not resolved:
                    break
                geometry_map[geometry["shape"]] = resolved
                geometries.append(resolved)
            if not geometries or len(geometries) != len(entry.get("geometries", [])):
                warnings.append("{}: falta geometria afectada; se salta.".format(name))
                continue
            driver_sources = []
            for connection in entry.get("connections", []):
                destination = connection["destination"].split(".", 1)[1]
                match = re.fullmatch(r"drivers\[(\d+)\]\.driverGeometry", destination)
                if match:
                    source_name = connection["source"].split(".", 1)[0]
                    resolved = self._resolve_deformer_node(source_name, geometry=True)
                    if resolved:
                        driver_sources.append((int(match.group(1)), resolved))
                    else:
                        warnings.append("{}: falta driver {}.".format(name, source_name))
            required_driver_count = sum(
                connection["destination"].endswith(".driverGeometry")
                for connection in entry.get("connections", []))
            if node_type == "proximityWrap" and (
                    not driver_sources or len(driver_sources) != required_driver_count):
                warnings.append("{}: drivers incompletos; se salta.".format(name))
                continue
            if any(driver in geometries for _, driver in driver_sources):
                warnings.append("{}: driver coincide con target; se salta.".format(name))
                continue
            try:
                if existing:
                    node = existing
                    current = cmds.deformer(node, query=True, geometry=True) or []
                    current_shapes = [self._resolve_deformer_node(g, geometry=True) for g in current]
                    if set(current_shapes) != set(geometries):
                        warnings.append("{}: deforma otras geometrías; se salta.".format(name))
                        continue
                else:
                    generated_handle = None
                    if node_type == "cluster":
                        node, generated_handle = cmds.cluster(geometries, name=name)
                    elif node_type == "nonLinear":
                        handle_sources = [connection["source"].split(".", 1)[0]
                                          for connection in entry.get("connections", [])
                                          if connection["destination"].endswith(".deformerData")]
                        handle_type = auxiliary.get(handle_sources[0], {}).get("type", "") if handle_sources else ""
                        subtype = {"deformBend": "bend", "deformFlare": "flare",
                                   "deformSine": "sine", "deformSquash": "squash",
                                   "deformTwist": "twist", "deformWave": "wave"}.get(handle_type)
                        if not subtype:
                            raise RuntimeError("Falta el tipo del handle nonlinear.")
                        node, generated_handle = cmds.nonLinear(geometries, type=subtype, name=name)
                    elif node_type == "blendShape":
                        node = cmds.blendShape(geometries, name=name, after=True)[0]
                    else:
                        node = cmds.deformer(geometries, type=node_type, name=name, after=True)[0]
                    if generated_handle:
                        handle_shape = (cmds.listRelatives(generated_handle, shapes=True,
                                                          fullPath=True) or [None])[0]
                        for connection in entry.get("connections", []):
                            source_name = connection["source"].split(".", 1)[0]
                            auxiliary_entry = auxiliary.get(source_name)
                            if not auxiliary_entry:
                                continue
                            generated = generated_handle if auxiliary_entry["type"] == "transform" else handle_shape
                            if not generated:
                                continue
                            node_map[source_name] = generated
                            for attr, data in auxiliary_entry.get("attributes", {}).items():
                                if attr == "deformerData":
                                    continue
                                plug = generated + "." + attr
                                if cmds.objExists(plug) and cmds.getAttr(plug, settable=True):
                                    self._set_deformer_value(plug, data)
                    created_count += 1
                node_map[name] = node
                actual_geometries = cmds.deformer(node, query=True, geometry=True) or []
                actual_indices = cmds.deformer(node, query=True, geometryIndices=True) or []
                for original in entry["geometries"]:
                    resolved = geometry_map[original["shape"]]
                    for actual, index in zip(actual_geometries, actual_indices):
                        if self._resolve_deformer_node(actual, geometry=True) == resolved:
                            index_map[original["index"]] = index
                driver_map = {}
                if node_type == "proximityWrap":
                    for index in cmds.proximityWrap(node, query=True, driverIndices=True) or []:
                        sources = cmds.listConnections(
                            "{}.drivers[{}].driverGeometry".format(node, index),
                            source=True, destination=False) or []
                        if sources:
                            cmds.proximityWrap(node, edit=True, removeDrivers=sources)
                    for old_index, driver in sorted(driver_sources):
                        new_index = cmds.proximityWrap(node, query=True, freeDriverIndex=True)
                        cmds.proximityWrap(node, edit=True, addDrivers=[driver], applyUserDefaults=False)
                        driver_map[old_index] = new_index
                pending.append((entry, node, index_map, driver_map))
            except Exception as exc:
                warnings.append("{}: {}".format(name, exc))

        def remap_attribute(attr, index_map, driver_map):
            def replace_index(match):
                field, index = match.group(1), int(match.group(2))
                mapping = driver_map if field == "drivers" else index_map
                return "{}[{}]".format(field, mapping.get(index, index))
            return re.sub(r"^(drivers|input|weightList|inputTarget)\[(\d+)\]",
                          replace_index, attr)

        for entry, node, index_map, driver_map in pending:
            aliases = entry.get("aliases", [])
            for alias, attr in zip(aliases[0::2], aliases[1::2]):
                try:
                    cmds.aliasAttr(alias, node + "." + attr)
                except Exception as exc:
                    warnings.append("{} alias {}: {}".format(node, alias, exc))
            connected = {connection["destination"].split(".", 1)[1]
                         for connection in entry.get("connections", [])}
            # Allocating blendShape target groups can reset their weights.
            attribute_items = sorted(entry.get("attributes", {}).items(),
                                     key=lambda item: item[0].startswith("weight["))
            for attr, data in attribute_items:
                if attr in connected or data.get("value") is None:
                    continue
                plug = node + "." + remap_attribute(attr, index_map, driver_map)
                try:
                    root_attr = attr.split(".", 1)[0].split("[", 1)[0]
                    if ((cmds.objExists(plug) or cmds.attributeQuery(root_attr, node=node, exists=True))
                            and not cmds.connectionInfo(plug, isDestination=True)):
                        cmds.setAttr(plug, lock=False)
                        self._set_deformer_value(plug, data)
                        cmds.setAttr(plug, lock=data.get("locked", False))
                except Exception as exc:
                    warnings.append("{}: {}".format(plug, exc))
            for connection in entry.get("connections", []):
                attr = connection["destination"].split(".", 1)[1]
                if (attr.startswith(("input[", "originalGeometry["))
                        or re.fullmatch(r"drivers\[\d+\]\.(driverGeometry|driverBindGeometry)", attr)):
                    continue  # These are reconstructed by Maya, not copied.
                source_name, source_attr = connection["source"].split(".", 1)
                source_node = node_map.get(source_name) or restore_auxiliary(source_name)
                if not source_node:
                    warnings.append("{}: falta conexion externa {}.".format(node, connection["source"]))
                    continue
                source = source_node + "." + source_attr
                destination = node + "." + remap_attribute(attr, index_map, driver_map)
                try:
                    if not cmds.isConnected(source, destination):
                        was_locked = cmds.getAttr(destination, lock=True)
                        cmds.setAttr(destination, lock=False)
                        try:
                            cmds.connectAttr(source, destination, force=True)
                        finally:
                            cmds.setAttr(destination, lock=was_locked)
                except Exception as exc:
                    warnings.append("{} -> {}: {}".format(source, destination, exc))

        managed = {entry["name"] for entry, _, _, _ in pending}
        for shape, stack in snapshot.get("geometry_stacks", {}).items():
            if not managed.intersection(stack):
                continue
            geometry = geometry_map.get(shape) or self._resolve_deformer_node(shape, geometry=True)
            if not geometry:
                continue
            resolved_stack = [node_map[name] for name in stack if name in node_map]
            for inner, outer in reversed(list(zip(resolved_stack, resolved_stack[1:]))):
                try:
                    cmds.reorderDeformers(outer, inner, geometry)
                except Exception as exc:
                    warnings.append("Orden {} / {}: {}".format(inner, outer, exc))
        for warning in dict.fromkeys(warnings):
            om.MGlobal.displayWarning(warning)
        om.MGlobal.displayInfo(
            "Deformadores: {} creados, {} restaurados, {} incidencias.".format(
                created_count, len(pending), len(set(warnings))))

    def export_skins(self, in_path=None):
        """
        Exporta los pesos. Si in_path es None, genera una NUEVA versión 
        basada en la más alta encontrada para no sobrescribir.
        """
        if in_path:
            save_path = os.path.normpath(in_path)
        else:
            # Lógica para generar la SIGUIENTE versión al exportar
            current_latest = self.get_latest_version_path()
            filename = os.path.basename(current_latest)
            
            try:
                # Si existe v005, la nueva será v006
                ver_str = filename.split("_v")[-1].split(self.ext)[0]
                new_version = int(ver_str) + 1
            except:
                new_version = 1
                
            save_path = os.path.join(self.folder_path, f"{self.asset_name}_v{new_version:03d}{self.ext}")

        self.json_path = save_path
        om.MGlobal.displayInfo(f"--- Exportando Skins a: {self.json_path} ---")
        
        sel = om.MGlobal.getActiveSelectionList()
        meshes_map = {} # Key: FullPath, Value: MDagPath

        # 1. Lógica de Selección (Mesh, Transform o SkinCluster)
        if sel.length() > 0:
            it_sel = om.MItSelectionList(sel)
            while not it_sel.isDone():
                obj = it_sel.getDependNode()
                
                if obj.hasFn(om.MFn.kSkinClusterFilter):
                    paths = self._get_meshes_from_skin(obj)
                    for p in paths: meshes_map[p.fullPathName()] = p
                
                elif obj.hasFn(om.MFn.kMesh):
                    path = it_sel.getDagPath()
                    path.extendToShape()
                    fn_dag = om.MFnDagNode(path)
                    if not fn_dag.isIntermediateObject:
                        meshes_map[path.fullPathName()] = path
                
                elif obj.hasFn(om.MFn.kTransform):
                    try:
                        path = it_sel.getDagPath()
                        path.extendToShape()
                        if path.node().hasFn(om.MFn.kMesh):
                            meshes_map[path.fullPathName()] = path
                    except: pass
                
                it_sel.next()
        else:
            # Si no hay selección, iteramos TODOS los skinClusters de la escena
            om.MGlobal.displayInfo("Sin selección. Escaneando escena completa...")
            it_dep = om.MItDependencyNodes(om.MFn.kSkinClusterFilter)
            while not it_dep.isDone():
                skin_obj = it_dep.thisNode()
                paths = self._get_meshes_from_skin(skin_obj)
                for p in paths: meshes_map[p.fullPathName()] = p
                it_dep.next()

        scene_deformers = self._export_scene_deformers()
        if not meshes_map and not scene_deformers["nodes"]:
            om.MGlobal.displayWarning("No se encontraron skins ni deformadores.")
            return

        # 2. Extracción de Datos
        full_data = {}
        
        for mesh_path in meshes_map.values():
            mesh_name = mesh_path.partialPathName() # Nombre corto para el JSON
            mf_mesh = om.MFnMesh(mesh_path)
            vtx_count = mf_mesh.numVertices
            
            # Obtenemos TODOS los skins en orden para mantener el Stack
            skins = self._get_skin_clusters(mesh_path)
            if not skins: continue

            om.MGlobal.displayInfo(f"Procesando: {mesh_name} | Skins: {len(skins)}")
            
            mesh_skins_data = []
            
            for skin_name in skins:
                sel_skin = om.MSelectionList()
                sel_skin.add(skin_name)
                mf_skin = oma.MFnSkinCluster(sel_skin.getDependNode(0))

                # Atributos
                attrs = {}
                for attr in self.k_skin_attrs:
                    try: attrs[attr] = cmds.getAttr(f"{skin_name}.{attr}")
                    except: pass

                # Influencias
                influences_paths = mf_skin.influenceObjects()
                inf_names = [p.partialPathName() for p in influences_paths]

                # --- Pesos SPARSE (Optimizado) ---
                single_comp = om.MFnSingleIndexedComponent()
                vertex_comp = single_comp.create(om.MFn.kMeshVertComponent)
                single_comp.setCompleteData(vtx_count)
                
                weights_marray, _ = mf_skin.getWeights(mesh_path, vertex_comp)
                flat_weights = list(weights_marray)
                
                sparse_weights = {}
                stride = len(inf_names)
                
                for inf_idx, inf_name in enumerate(inf_names):
                    j_indices = []
                    j_weights = []
                    
                    # Recorrer vértices para esta influencia
                    for v_idx in range(vtx_count):
                        val = flat_weights[v_idx * stride + inf_idx]
                        if val > self.tolerance:
                            j_indices.append(v_idx)
                            j_weights.append(round(val, 5))
                    
                    if j_indices:
                        sparse_weights[inf_name] = {"ix": j_indices, "vw": j_weights}

                # --- Blend Weights (Dual Quaternion) ---
                sparse_blend = {}
                try:
                    blend_weights_marray = mf_skin.getBlendWeights(mesh_path, vertex_comp)
                    flat_blend = list(blend_weights_marray)
                    b_indices = []
                    b_values = []
                    for v_idx, val in enumerate(flat_blend):
                        if val > self.tolerance:
                            b_indices.append(v_idx)
                            b_values.append(round(val, 5))
                    if b_indices:
                        sparse_blend = {"ix": b_indices, "vw": b_values}
                except: pass # Si no soporta blend weights, ignorar
                
                skin_entry = {
                    "name": skin_name,
                    "vertex_count": vtx_count,
                    "attributes": attrs,
                    "influences": inf_names, 
                    "sparse_weights": sparse_weights,
                    "sparse_blend": sparse_blend
                }
                mesh_skins_data.append(skin_entry)

            # Una copia por malla evita duplicar geometría con skins apilados.
            mesh_skins_data[0]["geometry"] = self._export_geometry(mf_mesh)
            full_data[mesh_name] = mesh_skins_data

        full_data[self.SCENE_DEFORMERS_KEY] = scene_deformers
        with open(self.json_path, 'w') as f:
            json.dump(full_data, f, separators=(',', ':')) # Separators comprime el JSON
            
        om.MGlobal.displayInfo(
            f"Export completado: {self.json_path} | "
            f"Deformadores: {len(scene_deformers['nodes'])}")

    # ----------------------------------------------------------------
    # --- IMPORT SKINS (Lógica Referencia: Reorder & Sparse) ---
    # ----------------------------------------------------------------
    def import_skins(self, in_path=None, replace_existing=False, import_method="auto"):
        """
        Importa los pesos desde un archivo JSON (.skc).
        Si in_path es None, busca automáticamente la versión más reciente.
        También reconstruye los deformadores ausentes de __scene_deformers__.
        Los existentes se conservan, salvo replace_existing=True. Las meshes y
        los drivers deben existir; las dependencias ausentes se notifican.

        import_method:
            "auto" (default): por índice si coincide la topología; en caso
                contrario, closest point on surface con interpolación baricéntrica.
            "index": exige la misma topología.
            "closestPoint": fuerza la proyección incluso con igual topología.
        La proyección requiere un .skc exportado con geometría. Usa el espacio
        local de ambas mallas y requiere la misma pose de referencia.

        replace_existing:
            False (default, flujo de build): los skinClusters que ya existen en
                escena con el mismo nombre se SALTAN y quedan los últimos del
                stack (no se pisan correctivas ni skins apilados).
            True (Character Manager): los skinClusters existentes con el mismo
                nombre se SUSTITUYEN por los del archivo — pesos, blend weights,
                influencias y atributos pasan a ser los del archivo. Los skins
                de escena que NO están en el archivo (p.ej. correctivas) se
                conservan y siguen quedando los últimos del stack.
        """
        if import_method not in ("auto", "index", "closestPoint"):
            raise ValueError("import_method debe ser 'auto', 'index' o 'closestPoint'")

        # 1. Determinar la ruta de importación
        if in_path:
            self.json_path = os.path.normpath(in_path)
        else:
            # Si no se da ruta, usamos nuestra lógica de "buscar el último"
            self.json_path = self.get_latest_version_path()

        # 2. Verificación de existencia
        if not os.path.exists(self.json_path):
            om.MGlobal.displayError(f"No se encontró el archivo de skin: {self.json_path}")
            return

        # 3. Lectura del archivo
        try:
            with open(self.json_path, 'r') as f:
                full_data = json.load(f)
        except Exception as e:
            om.MGlobal.displayError(f"Error al leer el JSON: {e}")
            return

        om.MGlobal.displayInfo("Importing skin weights…")

        # Registrar skin clusters ya existentes en escena ANTES de importar.
        # Estos no se importarán y siempre quedarán los últimos en el stack.
        existing_scene_skins = self._get_scene_skin_clusters()

        for mesh_name, skins_list in full_data.items():
            if mesh_name == self.SCENE_DEFORMERS_KEY:
                continue
            # Buscar Mesh en escena
            mesh_path = self._get_dag_path(mesh_name)
            if not mesh_path:
                found = self.find_mesh_in_scene(mesh_name)
                if found: mesh_path = self._get_dag_path(found)
            
            if not mesh_path:
                om.MGlobal.displayWarning(f"Saltando malla no encontrada: {mesh_name}")
                continue
            
            mesh_path.extendToShape()
            mf_mesh = om.MFnMesh(mesh_path)
            processed_skins = []
            geometry = next((s["geometry"] for s in skins_list if "geometry" in s), None)
            same_topology = self._same_topology(mf_mesh, geometry) if geometry else None
            surface_mapping = None
            # Capturar antes de crear skins o cambiar pesos en el stack.
            target_points = mf_mesh.getPoints(om.MSpace.kObject)

            for skin_data in skins_list:
                skin_name = skin_data["name"]
                target_vtx_count = skin_data["vertex_count"]

                if skin_name in existing_scene_skins and not replace_existing:
                    continue

                topology_matches = (mf_mesh.numVertices == target_vtx_count
                                    and same_topology is not False)
                use_surface = (import_method == "closestPoint"
                               or (import_method == "auto" and not topology_matches))
                if use_surface:
                    if not geometry:
                        om.MGlobal.displayWarning(
                            f"{skin_name}: el .skc antiguo no contiene geometría para "
                            "closest point. Reexporta desde la malla original; se salta este skin.")
                        continue
                    if len(geometry["points"]) != target_vtx_count:
                        om.MGlobal.displayWarning(f"Geometría incompatible con {skin_name}; se salta.")
                        continue
                    if surface_mapping is None:
                        try:
                            surface_mapping = self._closest_surface_map(geometry, target_points)
                        except Exception as e:
                            om.MGlobal.displayWarning(f"No se pudo proyectar {mesh_name}: {e}")
                            break
                    om.MGlobal.displayInfo(f"{skin_name}: importando por closest point on surface.")
                elif not topology_matches:
                    om.MGlobal.displayWarning(f"Topología incorrecta para {skin_name}; se salta (modo index).")
                    continue

                json_influences = skin_data["influences"]
                
                # Crear o Editar SkinCluster
                skin_exists = cmds.objExists(skin_name) and cmds.nodeType(skin_name) == "skinCluster"
                mf_skin = None
                
                if skin_exists:
                    # Para sustituir, el skin existente debe deformar ESTA malla;
                    # si el nombre choca con un skin de otra malla, se salta.
                    skin_geo = cmds.skinCluster(skin_name, q=True, geometry=True) or []
                    mesh_shape = mesh_path.partialPathName()
                    if not any(mesh_shape == g or g.endswith(f"|{mesh_shape}")
                               or mesh_shape.endswith(f"|{g}") for g in skin_geo):
                        om.MGlobal.displayWarning(
                            f"{skin_name} existe pero no deforma {mesh_name}; se salta.")
                        continue
                    sel_s = om.MSelectionList()
                    sel_s.add(skin_name)
                    mf_skin = oma.MFnSkinCluster(sel_s.getDependNode(0))
                    scene_infs = [p.partialPathName() for p in mf_skin.influenceObjects()]
                    missing_infs = [inf for inf in json_influences if inf not in scene_infs and cmds.objExists(inf)]
                    if missing_infs:
                        # Bloquear pesos existentes para no destruirlos al añadir huesos
                        cmds.skinCluster(skin_name, e=True, lw=True) 
                        cmds.skinCluster(skin_name, e=True, addInfluence=missing_infs, weight=0.0)
                        cmds.skinCluster(skin_name, e=True, lw=False)
                else:
                    valid_joints = [j for j in json_influences if cmds.objExists(j)]
                    if not valid_joints: 
                        om.MGlobal.displayWarning(f"No hay joints válidos para {skin_name}")
                        continue
                    
                    # IMPORTANTE: multi=True permite stackear deformadores
                    new_skin = cmds.skinCluster(valid_joints, mesh_path.fullPathName(), n=skin_name, toSelectedBones=True, multi=True)[0]
                    skin_name = new_skin  # Maya puede renombrar por colisión: usar SIEMPRE el nodo real
                    sel_s = om.MSelectionList()
                    sel_s.add(new_skin)
                    mf_skin = oma.MFnSkinCluster(sel_s.getDependNode(0))

                # Restaurar Atributos
                for attr, val in skin_data.get("attributes", {}).items():
                    try: cmds.setAttr(f"{skin_name}.{attr}", val)
                    except: pass
                
                # Mapeo de Influencias
                scene_inf_paths = mf_skin.influenceObjects()
                scene_inf_names = [p.partialPathName() for p in scene_inf_paths]
                scene_inf_map = {name: i for i, name in enumerate(scene_inf_names)}

                num_verts = mf_mesh.numVertices
                num_scene_infs = len(scene_inf_names)
                full_weight_list = [0.0] * (target_vtx_count * num_scene_infs)
                
                # --- Reconstruir Pesos SPARSE ---
                sparse_data = skin_data.get("sparse_weights", {})
                
                for j_name, data_block in sparse_data.items():
                    if j_name not in scene_inf_map: continue
                    scene_inf_idx = scene_inf_map[j_name]
                    indices = data_block["ix"]
                    values = data_block["vw"]
                    for v_idx, weight_val in zip(indices, values):
                        flat_index = (v_idx * num_scene_infs) + scene_inf_idx
                        full_weight_list[flat_index] = weight_val

                if use_surface:
                    full_weight_list = self._remap_weights(
                        full_weight_list, num_scene_infs, surface_mapping)
                
                # Aplicar Pesos
                m_influence_indices = om.MIntArray(list(range(num_scene_infs)))
                final_weights = om.MDoubleArray(full_weight_list)
                
                single_comp = om.MFnSingleIndexedComponent()
                vertex_comp = single_comp.create(om.MFn.kMeshVertComponent)
                single_comp.setCompleteData(num_verts)
                
                prev_norm = cmds.getAttr(f"{skin_name}.normalizeWeights")
                cmds.setAttr(f"{skin_name}.normalizeWeights", 0) # Desactivar norma para setWeights exacto
                
                try:
                    mf_skin.setWeights(mesh_path, vertex_comp, m_influence_indices, final_weights, False)
                finally:
                    cmds.setAttr(f"{skin_name}.normalizeWeights", prev_norm)

                # Aplicar Blend Weights
                sparse_blend = skin_data.get("sparse_blend", {})
                if sparse_blend:
                    full_blend = [0.0] * target_vtx_count
                    for v_idx, val in zip(sparse_blend["ix"], sparse_blend["vw"]):
                        full_blend[v_idx] = val
                    if use_surface:
                        full_blend = self._remap_weights(full_blend, 1, surface_mapping)
                    mf_skin.setBlendWeights(mesh_path, vertex_comp, om.MDoubleArray(full_blend))
                elif skin_exists:
                    # Sustitución de un skin existente y el archivo no trae blend
                    # weights: dejarlos a cero para que el estado == archivo.
                    mf_skin.setBlendWeights(mesh_path, vertex_comp, om.MDoubleArray([0.0] * num_verts))

                processed_skins.append(skin_name)

            # --- Reordenamiento de Deformers (Stack Order) ---
            # Orden deseado (inner → outer):
            #   1. imported skins (del archivo)
            #   2. pre-existing skins (los que ya estaban en escena, siempre los últimos)
            if processed_skins:
                current_hist = cmds.listHistory(mesh_path.fullPathName(), pruneDagObjects=True, interestLevel=1) or []
                current_skins = [x for x in current_hist if cmds.nodeType(x) == "skinCluster"]
                current_skins = list(reversed(current_skins))  # [Inner, ..., Outer]

                # Un skin sustituido está en ambos sets: cuenta como importado
                # (inner), no como pre-existente, para no duplicarlo en el orden.
                pre_existing_here = [s for s in current_skins
                                     if s in existing_scene_skins and s not in processed_skins]
                desired_order = processed_skins + pre_existing_here

                # reorderDeformers inserta el segundo deformer ANTES del primero.
                for inner, outer in reversed(list(zip(desired_order, desired_order[1:]))):
                    try:
                        cmds.reorderDeformers(outer, inner, mesh_path.fullPathName())
                    except Exception as e:
                        om.MGlobal.displayWarning(f"No se pudo ordenar {inner} antes de {outer}: {e}")
        
        self._import_scene_deformers(
            full_data.get(self.SCENE_DEFORMERS_KEY), replace_existing=replace_existing)
        om.MGlobal.displayInfo("Skin weights and scene deformers imported.")

    def find_mesh_in_scene(self, name):
        """Helper para fallback de búsqueda."""
        if cmds.objExists(name): return name
        matches = cmds.ls(f"*{name}", type="transform")
        for m in matches:
            if m.endswith(f"|{name}") or m.endswith(f":{name}"): return m
        return matches[0] if matches else None
    

    def copy_skin_cluster():
        """
        Transfers all skinClusters from Source to Target mesh.
        - Matches joints exactly.
        - Appends _COPY to the name.
        - Copies weights.
        - Performs a self-mirror on the result.
        """
        
        sel = cmds.ls(sl=True)
        if not sel or len(sel) != 2:
            cmds.warning("Please select exactly two meshes: Source then Target.")
            return

        source_node = sel[0]
        target_node = sel[1]

        source_shapes = cmds.listRelatives(source_node, shapes=True) or []
        target_shapes = cmds.listRelatives(target_node, shapes=True) or []
        
        if not source_shapes or not target_shapes:
            om.MGlobal.displayError("Selection must be geometry with valid shapes.")
            return


        history = cmds.listHistory(source_shapes[0], pruneDagObjects=False, fullNodeName=True) or []
        source_skins = [node for node in history if cmds.nodeType(node) == "skinCluster"]

        source_skins.reverse()

        if not source_skins:
            om.MGlobal.displayWarning(f"No skinClusters found on {source_node}.")
            return

        om.MGlobal.displayInfo(f"Found {len(source_skins)} skinClusters on {source_node}. Beginning transfer...")

        for src_skin in source_skins:
            

            influences = cmds.skinCluster(src_skin, query=True, influence=True)

            new_name = f"{src_skin}_COPY"
            
            if cmds.objExists(new_name):
                om.MGlobal.displayWarning(f"{new_name} already exists. Maya will rename it automatically.")

            om.MGlobal.displayInfo(f"Processing: {src_skin} -> {new_name}")

            new_skin = cmds.skinCluster(
                influences, 
                target_node, 
                name=new_name, 
                toSelectedBones=False, 
                bindMethod=0, 
                normalizeWeights=1, 
                weightDistribution=0,
                mi=1,
                omi=False,
                dr=4.0,
                rui=False,
                multi=True 
            )[0]

        
            method = cmds.getAttr(f"{src_skin}.skinningMethod")
            cmds.setAttr(f"{new_skin}.skinningMethod", method)
            
        
            cmds.copySkinWeights(
                ss=src_skin, 
                ds=new_skin, 
                noMirror=True, 
                surfaceAssociation='closestPoint', 
                influenceAssociation=['label', 'oneToOne', 'closestJoint'],
                normalize=True 
            )

        
            cmds.copySkinWeights(
                ss=new_skin, 
                ds=new_skin, 
                mirrorMode='YZ', 
                surfaceAssociation='closestPoint', 
                influenceAssociation=['label', 'oneToOne'], 
                normalize=True
            )
            
            om.MGlobal.displayInfo(f"Successfully created and mirrored: {new_skin}")

        om.MGlobal.displayInfo("--- Transfer Complete ---")


