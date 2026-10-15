"""Experimental compression-driven, geometry-based cartoon wrinkles in Bifrost.

Build on a neutral, fixed-topology skinned mesh. The serialized graph computes
compression, spatial filtering and normal displacement without Python callbacks.
This is pose-reactive geometry, not a time-stepped physical skin simulation.
"""
import math
import hashlib
import json
from contextlib import contextmanager

import maya.cmds as cmds
import maya.api.OpenMaya as om


REGIONS = ("Forehead", "Eyes", "Cheeks", "Nose", "Chin")


@contextmanager
def primary_inputs_for_skin_export():
    """Expose owned skin outputs to Maya's DAG skin API without baking detail."""
    inputs, consumers = {}, {}
    modified = cmds.file(query=True, modified=True)
    undo = cmds.undoInfo(query=True, state=True)
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        for settings in cmds.ls('*_Settings', type='transform') or []:
            if not cmds.attributeQuery('wrinkleInPlace', node=settings, exists=True) or not cmds.getAttr(settings + '.wrinkleInPlace'):
                continue
            prefix = settings.rsplit('_Settings', 1)[0]
            shape = cmds.connectionInfo(settings + '.sourceMesh', sourceFromDestination=True).split('.')[0]
            destination = shape + '.inMesh'
            upstream = cmds.connectionInfo(prefix + 'GraphShape.AnimatedFace', sourceFromDestination=True)
            inputs[destination] = cmds.connectionInfo(destination, sourceFromDestination=True)
            cmds.connectAttr(upstream, destination, force=True)
            for destination, route in json.loads(cmds.getAttr(settings + '.wrinklePrimaryConsumers') or '{}').items():
                incoming = cmds.connectionInfo(destination, sourceFromDestination=True)
                if incoming == route['replacement']:
                    consumers[destination] = incoming
                    cmds.connectAttr(route['original'], destination, force=True)
        yield
    finally:
        for destination, source in consumers.items():
            cmds.connectAttr(source, destination, force=True)
        for destination, source in inputs.items():
            cmds.connectAttr(source, destination, force=True)
        cmds.undoInfo(stateWithoutFlush=undo)
        cmds.file(modified=modified)


def _mesh_fn(mesh):
    shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or []
    shape = mesh if cmds.nodeType(mesh) == "mesh" else next(
        (s for s in shapes if cmds.nodeType(s) == "mesh"), None)
    if not shape:
        raise ValueError("Select a polygon mesh in its neutral pose.")
    path = om.MSelectionList().add(shape).getDagPath(0)
    return shape, path, om.MFnMesh(path)


def _smooth(a, b, x):
    t = max(0., min(1., (x - a) / max(b - a, 1e-8)))
    return t * t * (3. - 2. * t)


def _fold(distance, width=.3):
    """Broad shoulders around a soft valley; no high-frequency noise."""
    q = distance / width
    return .45 * math.exp(-.25 * q * q) - math.exp(-q * q)


def edward_flow_patterns(points, normals):
    """Edward-specific rest-space flow fields, in the asset's centimeter space.

    Masks exclude scalp/back/ears, lip seam and the moving eyelid margins.
    Keeping these fields on vertex IDs makes them follow the animated skin.
    """
    result = {region: [] for region in REGIONS}
    for point, normal in zip(points, normals):
        x, y, z = point.x, point.y, point.z
        ax = abs(x)
        front = _smooth(3., 7., z) * _smooth(.05, .5, normal.z)
        lip_radius = math.sqrt((x / 3.25) ** 2 + ((y - 189.1) / 1.35) ** 2)
        eye_radius = math.sqrt(((ax - 4.6) / 2.5) ** 2 + ((y - 199.8) / 1.7) ** 2)
        safe = front * _smooth(1.05, 1.45, lip_radius) * _smooth(1., 1.3, eye_radius)
        forehead = math.exp(-(x / 6.5) ** 6) * sum(
            _fold(y - level - .025 * x * x, .34) for level in (205.1, 206.8, 208.5))
        furrow = math.exp(-((y - 204.9) / 2.3) ** 4) * sum(
            _fold(x - side * .65, .23) for side in (-1., 1.))
        forehead = forehead + .7 * furrow
        dx, dy = ax - 6.95, y - 199.7
        radius = math.hypot(dx, dy)
        angle = math.atan2(dy, max(.01, dx))
        eyes = _smooth(.3, .9, dx) * _smooth(.4, 1., radius) * (1. - _smooth(2.3, 3.3, radius))
        eyes *= sum(_fold(radius * (angle - a), .22) for a in (-.55, 0., .55))
        cheek_flow = 2.9 + .075 * (y - 191.8) ** 2
        cheeks = math.exp(-((y - 190.) / 4.8) ** 6) * sum(
            _fold(ax - cheek_flow - offset, .34) for offset in (0., .9))
        nose = math.exp(-(x / 1.6) ** 6) * sum(
            _fold(y - level, .25) for level in (200.9, 202.))
        chin = math.exp(-(x / 3.5) ** 6) * sum(
            _fold(y - level + .018 * x * x, .33) for level in (183.9, 185.4))
        for region, pattern in zip(REGIONS, (forehead, eyes, cheeks, nose, chin)):
            result[region].append(max(-1., min(1., safe * pattern)))
    return result


class _Graph:
    def __init__(self, graph):
        self.graph = graph
        self.order = 0

    def node(self, namespace, kind, name):
        old = cmds.vnnCompound(self.graph, "/", addNode="BifrostGraph," + namespace + "," + kind)[0]
        cmds.vnnCompound(self.graph, "/", renameNode=(old, name))
        cmds.vnnNode(self.graph, "." + name, setMetaData=("LayoutPos", "%s %s" % (self.order % 9 * 240, self.order // 9 * 170)))
        self.order += 1
        return "." + name

    def connect(self, source, target):
        cmds.vnnConnect(self.graph, source, target)

    def scalar(self, name, value):
        node = self.node("Core::Constants", "float", name)
        cmds.vnnNode(self.graph, node, setPortDefaultValues=("value", str(value)))
        return node + ".output"

    def operation(self, kind, name, inputs):
        node = self.node("Core::Math", kind, name)
        for i, source in enumerate(inputs):
            cmds.vnnNode(self.graph, node, createInputPort=("term%d" % i, "auto"))
            self.connect(source, node + ".term%d" % i)
        return node + ".output"

    def sample(self, name, array, indices):
        node = self.node("Core::Array", "get_from_array", name)
        self.connect(array, node + ".array")
        self.connect(indices, node + ".index")
        return node + ".value"

    def clamp(self, name, value):
        node = self.node("Core::Math", "clamp", name)
        self.connect(value, node + ".value")
        # Explicit scalar sources broadcast across arrays. Defaults on auto
        # ports can specialize to empty arrays and silently clamp to zero.
        self.connect(self.scalar(name + "Min", 0.), node + ".min")
        self.connect(self.scalar(name + "Max", 1.), node + ".max")
        return node + ".clamped"

    def input(self, name, kind, data=None):
        cmds.vnnNode(self.graph, ".input", createOutputPort=(name, kind))
        if data is not None:
            # Maya's Bifrost array ports are multi attributes, not typed arrays.
            for start in range(0, len(data), 2048):
                values = data[start:start + 2048]
                cmds.setAttr("%s.%s[%d:%d]" % (self.graph, name, start, start + len(values) - 1),
                             *values, size=len(values))
        return "." + name

    def indices(self, name, values):
        # Default-zero multi elements disappear in native Maya serialization.
        # Store IDs plus one, including local filter IDs, then decode in Bifrost.
        encoded = self.input(name + 'Encoded', 'array<long>', [v + 1 for v in values])
        one = self.node('Core::Constants', 'long', name + 'IndexOffset')
        cmds.vnnNode(self.graph, one, setPortDefaultValues=('value', '1'))
        return self.operation('subtract', name + 'Decoded', [encoded, one + '.output'])


def build(mesh=None, prefix="EdwardWrinkles", patterns=None, hide_source=False,
          rest_data=None, control_fields=None, compact=False, in_place=False):
    """Build native wrinkles on fixed topology, optionally in the source output.

    In-place output preserves primary history and reroutes existing consumers.
    For other assets pass region arrays in ``patterns`` instead of Edward's map.
    """
    if mesh is None:
        selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        if len(selected) != 1:
            raise ValueError("Select exactly one neutral facial mesh.")
        mesh = selected[0]
    if cmds.objExists(prefix + "_GRP"):
        raise ValueError("A wrinkle prototype with this name already exists.")
    shape, path, mesh_fn = _mesh_fn(mesh)
    upstream = cmds.connectionInfo(shape + '.inMesh', sourceFromDestination=True)
    if in_place and not upstream:
        raise ValueError('In-place wrinkles require an existing upstream deformation output.')
    if in_place and hide_source:
        raise ValueError('The in-place source is also the displayed output; do not hide it.')
    points = mesh_fn.getPoints(om.MSpace.kObject)
    normals = mesh_fn.getVertexNormals(True, om.MSpace.kObject)
    patterns = patterns or edward_flow_patterns(points, normals)
    if set(patterns) != set(REGIONS) or any(len(patterns[r]) != len(points) for r in REGIONS):
        raise ValueError("Each region must contain one scalar per source vertex.")
    # Four edge-connected samples capture compression in different directions.
    # Isolated points have no displacement because their patterns are zeroed.
    neighbor_arrays = [[] for _ in range(4)]
    lengths = [[] for _ in range(4)]
    iterator = om.MItMeshVertex(path)
    while not iterator.isDone():
        index = iterator.index()
        neighbors = list(iterator.getConnectedVertices())
        neighbors.sort(key=lambda n: math.atan2(points[n].y - points[index].y,
                                                points[n].x - points[index].x))
        for sample in range(4):
            neighbor = neighbors[min(len(neighbors) - 1, sample * len(neighbors) // 4)] if neighbors else index
            neighbor_arrays[sample].append(neighbor)
            lengths[sample].append(max((points[index] - points[neighbor]).length(), 1e-6))
        if not neighbors:
            for region in REGIONS:
                patterns[region][index] = 0.
        iterator.next()
    if rest_data is not None:
        neighbor_arrays = rest_data["neighbors"]
        lengths = rest_data["lengths"]
        if len(neighbor_arrays) != 4 or len(lengths) != 4 or any(
                len(array) != len(points) for array in neighbor_arrays + lengths):
            raise ValueError("Wrinkle rest arrays do not match the source topology.")
        if any(not 0 <= value < len(points) for array in neighbor_arrays for value in array):
            raise ValueError("Invalid wrinkle neighbor index.")
        if any(not math.isfinite(value) or value <= 0 for array in lengths for value in array):
            raise ValueError("Invalid wrinkle rest length.")
    control_fields = control_fields or []
    for field in control_fields:
        if not cmds.objExists(field["controller"]):
            raise ValueError("Missing wrinkle controller: " + field["controller"])
        for region, mask in field["masks"].items():
            if region not in REGIONS or len(mask) != len(points) or any(
                    not math.isfinite(value) or not 0 <= value <= 1 for value in mask):
                raise ValueError("Invalid local wrinkle mask.")
    regional = None
    if compact:
        from maya_tools.scripts.tools import wrinkle_regions_core
        # Match the encoded float32 fields used by the serialized legacy graph.
        import struct
        stored = {r: [struct.unpack('f', struct.pack('f', v + 2.))[0] - 2.
                      for v in values] for r, values in patterns.items()}
        regional = wrinkle_regions_core.plan(stored, neighbor_arrays)
    from maya_tools.scripts.utils.build_timing import measure
    with measure('Load Bifrost plugin'):
        cmds.loadPlugin("bifrostGraph", quiet=True)
    cmds.undoInfo(openChunk=True, chunkName="Bifrost cartoon wrinkles")
    chunk_open = True
    group = converter = None
    consumers, primary_nodes = {}, []
    try:
        group = cmds.createNode("transform", name=prefix + "_GRP")
        source_namespace = shape.rsplit("|", 1)[-1].rsplit(":", 1)
        deformers_group = (source_namespace[0] + ":" if len(source_namespace) == 2 else "") + "deformers_GRP"
        if cmds.objExists(deformers_group):
            cmds.parent(group, deformers_group, absolute=True)
        settings = cmds.createNode("transform", name=prefix + "_Settings", parent=group)
        if regional is not None:
            def float32(value):
                return struct.unpack('f', struct.pack('f', value))[0]
            fields = {'patterns': stored,
                      'rest': {'neighbors': neighbor_arrays,
                               'lengths': [[float32(v) for v in row] for row in lengths]},
                      'masks': {str(i): {r: [max(0., min(1., float32(v + 2.) - 2.)) for v in values]
                                        for r, values in field['masks'].items()}
                                for i, field in enumerate(control_fields)}}
            cmds.addAttr(settings, longName='wrinkleRegionalFields', dataType='string')
            cmds.setAttr(settings + '.wrinkleRegionalFields', json.dumps(fields, separators=(',', ':')), type='string')
        defaults = {"Envelope": 1., "Depth": .3, "CompressionStart": .015,
                    "CompressionRange": .1, "ManualActivation": 0.}
        defaults.update({region: 1. for region in REGIONS})
        for attr, default in defaults.items():
            args = {"longName": attr, "attributeType": "double", "defaultValue": default,
                    "minValue": .001 if attr == "CompressionRange" else 0., "keyable": True}
            if attr in ("Envelope", "ManualActivation"):
                args["maxValue"] = 1.
            cmds.addAttr(settings, **args)
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            cmds.setAttr(settings + "." + attr, lock=True, keyable=False)
        graph = cmds.createNode("bifrostGraphShape", name=prefix + "GraphShape")
        if regional is not None:
            cmds.addAttr(graph, longName='regionalSupport', dataType='string')
            cmds.setAttr(graph + '.regionalSupport', json.dumps(regional), type='string')
        graph_parent = cmds.listRelatives(graph, parent=True)[0]
        cmds.parent(graph_parent, group)
        cmds.setAttr(graph + ".visibility", 0)
        primary_input = upstream if in_place else shape + '.outMesh'
        g = _Graph(graph)
        graph_nodes = cmds.vnnCompound(graph, "/", listNodes=True) or []
        if "input" not in graph_nodes:
            cmds.vnnCompound(graph, "/", addIONode=True)
        if "output" not in graph_nodes:
            cmds.vnnCompound(graph, "/", addIONode=False)
        cmds.vnnChangeBracket(graph, open=True)
        try:
            geometry = g.input("AnimatedFace", "Object")
            cmds.connectAttr(primary_input, graph + '.AnimatedFace')
            for attr in defaults:
                g.input(attr, "float")
                cmds.connectAttr(settings + "." + attr, graph + "." + attr)
            for index, field in enumerate(control_fields):
                control = field["controller"]
                field["port"] = "Local%d" % index
                for attr, label, maximum in (("wrinkleDepth", "Wrinkle Depth", None),
                                              ("wrinkleValue", "Wrinkle Value", 1.)):
                    if not cmds.attributeQuery(attr, node=control, exists=True):
                        kwargs = dict(longName=attr, niceName=label, attributeType="double",
                                      defaultValue=1., minValue=0., keyable=True)
                        if maximum is not None:
                            kwargs["maxValue"] = maximum
                        cmds.addAttr(control, **kwargs)
                    elif attr == "wrinkleValue":
                        # Reset-to-default must enable wrinkles on reused controls.
                        # Saved/current values still round-trip independently.
                        cmds.addAttr(control + "." + attr, edit=True, defaultValue=1.)
                    plug = control + "." + attr
                    if attr in field.get("values", {}) and cmds.getAttr(plug, settable=True):
                        cmds.setAttr(plug, field["values"][attr])
                    port = field["port"] + ("Depth" if attr == "wrinkleDepth" else "Value")
                    g.input(port, "float")
                    cmds.connectAttr(plug, graph + "." + port)
            positions_node = g.node("Geometry::Properties", "get_point_position", "AnimatedPositions")
            g.connect(geometry, positions_node + ".geometry")
            positions = positions_node + ".point_position"
            active_indices = compression_indices = None
            compression_positions = final_positions = positions
            if regional is not None:
                active_indices = g.indices('ActiveIndices', regional['active'])
                compression_indices = g.indices('CompressionIndices', regional['compression'])
                compression_positions = g.sample('CompressionPositions', positions, compression_indices)
                final_positions = g.sample('ActivePositions', positions, active_indices)
            normalized = g.node("Geometry::Mesh", "update_mesh_normals", "AnimatedNormals")
            g.connect(geometry, normalized + ".mesh")
            one, three = g.scalar("One", 1), g.scalar("Three", 3)
            quarter, half, two = g.scalar("Quarter", .25), g.scalar("Half", .5), g.scalar("Two", 2)
            compressions, ids = [], []
            for i in range(4):
                neighbor_values, rest_values = neighbor_arrays[i], lengths[i]
                if regional is not None:
                    neighbor_values = [neighbor_values[j] for j in regional['compression']]
                    rest_values = [rest_values[j] for j in regional['compression']]
                indices = g.indices("Neighbor%d" % i, neighbor_values); ids.append(indices)
                rest = g.input("RestLength%d" % i, "array<float>", rest_values)
                runtime_indices = indices
                neighbor_positions = g.sample("NeighborPositions%d" % i, positions, runtime_indices)
                edge = g.operation("subtract", "EdgeVector%d" % i, [compression_positions, neighbor_positions])
                length = g.node("Core::Math", "length", "EdgeLength%d" % i)
                g.connect(edge, length + ".vector")
                ratio = g.operation("divide", "StretchRatio%d" % i, [length + ".length", rest])
                compression = g.operation("subtract", "Compression%d" % i, [one, ratio])
                compressions.append(g.clamp("PositiveCompression%d" % i, compression))
            average = g.operation("multiply", "AverageCompression", [g.operation("add", "EdgeCompressionSum", compressions), quarter])
            for step in range(2):
                self_values = average
                filter_ids = ids
                if regional is not None:
                    mapping = regional['stages'][step]
                    self_ids = g.indices('Filter%dSelfIndices' % step, mapping['self'])
                    self_values = g.sample('Filter%dSelf' % step, average, self_ids)
                    filter_ids = [g.indices('Filter%dNeighbor%dIndices' % (step, i), a)
                                  for i, a in enumerate(mapping['neighbors'])]
                neighborhood = [g.sample("Filter%dNeighbor%d" % (step, i), average, index) for i, index in enumerate(filter_ids)]
                neighbors = g.operation("multiply", "Filter%dAverage" % step, [g.operation("add", "Filter%dSum" % step, neighborhood), quarter])
                average = g.operation("multiply", "Filter%dSmooth" % step, [g.operation("add", "Filter%dBlend" % step, [self_values, neighbors]), half])
            above_start = g.operation("subtract", "CompressionOnset", [average, ".CompressionStart"])
            above_start = g.clamp("AboveCompressionStart", above_start)
            amount = g.operation("divide", "CompressionGain", [above_start, ".CompressionRange"])
            activation = g.clamp("Activation", g.operation("add", "ManualPreview", [amount, ".ManualActivation"]))
            squared = g.operation("multiply", "ActivationSquared", [activation, activation])
            curve = g.operation("subtract", "EaseOut", [three, g.operation("multiply", "DoubleActivation", [activation, two])])
            activation = g.operation("multiply", "SmoothActivation", [squared, curve])
            region_fields = []
            # Maya omits default-zero multi attributes on save. Encoding
            # bounded [-1, 1] flow fields as [1, 3] preserves their full length,
            # including completely inactive regions, in both .ma and .mb.
            flow_offset = g.scalar("FlowStorageOffset", 2)
            for region in REGIONS:
                pattern_values = patterns[region]
                if regional is not None:
                    pattern_values = [pattern_values[i] for i in regional['active']]
                pattern = g.input(region + "FlowEncoded", "array<float>",
                                  [value + 2 for value in pattern_values])
                pattern = g.operation("subtract", region + "Flow", [pattern, flow_offset])
                local_amounts = []
                for field in control_fields:
                    if region not in field["masks"]:
                        continue
                    port = field["port"]
                    mask_name = port + region + "MaskEncoded"
                    mask_values = field['masks'][region]
                    if regional is not None:
                        mask_values = [mask_values[i] for i in regional['active']]
                    mask = g.input(mask_name, "array<float>",
                                   [value + 2 for value in mask_values])
                    mask = g.operation("subtract", port + region + "Mask", [mask, flow_offset])
                    local_amounts.append(g.operation("multiply", port + region + "Strength",
                                                    [mask, "." + port + "Depth", "." + port + "Value"]))
                if local_amounts:
                    pattern = g.operation("multiply", region + "LocalFlow",
                                          [pattern, g.operation("add", region + "LocalStrength", local_amounts)])
                region_fields.append(g.operation("multiply", region + "Amount", [pattern, "." + region]))
            flow = g.operation("add", "CartoonFlow", region_fields)
            depth = g.operation("multiply", "WrinkleDepth", [flow, activation, ".Depth", ".Envelope"])
            normal_values = normalized + '.point_normal'
            if regional is not None:
                normal_values = g.sample('ActiveNormals', normal_values, active_indices)
            delta = g.operation("multiply", "NormalDisplacement", [normal_values, depth])
            deformed = g.operation("add", "WrinkledPositions", [final_positions, delta])
            if regional is not None:
                scatter = g.node('Core::Array', 'set_in_array', 'ScatterActivePositions')
                g.connect(positions, scatter + '.array')
                g.connect(active_indices, scatter + '.index')
                g.connect(deformed, scatter + '.value')
                deformed = scatter + '.out_array'
            set_positions = g.node("Geometry::Properties", "set_point_position", "ApplyWrinkles")
            g.connect(geometry, set_positions + ".geometry")
            g.connect(deformed, set_positions + ".positions")
            output_normals = g.node("Geometry::Mesh", "update_mesh_normals", "OutputNormals")
            g.connect(set_positions + ".out_geometry", output_normals + ".mesh")
            cmds.vnnNode(graph, ".output", createInputPort=("WrinkledFace", "Object"))
            g.connect(output_normals + ".out_mesh", ".WrinkledFace")
        finally:
            with measure('Compile wrinkle graph'):
                cmds.vnnChangeBracket(graph, close=True)
        converter = cmds.createNode("bifrostGeoToMaya", name=prefix + "_ToMaya")
        cmds.connectAttr(graph + ".WrinkledFace", converter + ".bifrostGeo")
        source_transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        if in_place:
            # Preserve primary geometry for garments/pins rather than feeding final detail back.
            for source_plug in (shape + '.outMesh', shape + '.worldMesh[0]'):
                destinations = cmds.listConnections(source_plug, source=False, destination=True, plugs=True) or []
                if not destinations:
                    continue
                replacement = upstream
                if source_plug.endswith('.worldMesh[0]'):
                    transform = cmds.createNode('transformGeometry', name=prefix + '_PrimaryWorld')
                    primary_nodes.append(transform)
                    cmds.connectAttr(upstream, transform + '.inputGeometry')
                    cmds.connectAttr(source_transform + '.worldMatrix[0]', transform + '.transform')
                    replacement = transform + '.outputGeometry'
                for destination in destinations:
                    cmds.connectAttr(replacement, destination, force=True)
                    consumers[destination] = {'original': source_plug, 'replacement': replacement}
            output, output_shape = source_transform, shape
            cmds.connectAttr(converter + '.mayaMesh[0]', shape + '.inMesh', force=True)
            cmds.addAttr(settings, longName='wrinkleInPlace', attributeType='bool', defaultValue=True)
            cmds.addAttr(settings, longName='wrinklePrimaryConsumers', dataType='string')
            cmds.setAttr(settings + '.wrinklePrimaryConsumers', json.dumps(consumers), type='string')
            if primary_nodes:
                cmds.addAttr(settings, longName='wrinklePrimaryNodes', attributeType='message', multi=True)
                for index, node in enumerate(primary_nodes):
                    cmds.connectAttr(node + '.message', settings + '.wrinklePrimaryNodes[%d]' % index)
        else:
            # Utility groups are normally hidden; display output belongs to geometry.
            display_parent = cmds.listRelatives(source_transform, parent=True, fullPath=True) or []
            output = cmds.createNode("transform", name=prefix + "_Face", **({'parent': display_parent[0]} if display_parent else {}))
            output_shape = cmds.createNode("mesh", name=prefix + "_FaceShape", parent=output)
            cmds.connectAttr(converter + ".mayaMesh[0]", output_shape + ".inMesh")
            cmds.setAttr(output + ".inheritsTransform", 0)
            cmds.connectAttr(source_transform + ".worldMatrix[0]", output + ".offsetParentMatrix")
            shaders = cmds.listConnections(shape, type="shadingEngine") or ["initialShadingGroup"]
            cmds.sets(output, edit=True, forceElement=shaders[0])
        cmds.addAttr(settings, longName="sourceMesh", attributeType="message")
        cmds.connectAttr(shape + ".message", settings + ".sourceMesh")
        cmds.addAttr(settings, longName="wrinkleSetup", attributeType="bool", defaultValue=True)
        cmds.addAttr(settings, longName="wrinkleControls", dataType="string")
        metadata = [{"controller": f["controller"], "port": f["port"],
                     "regions": list(f["masks"])} for f in control_fields]
        cmds.setAttr(settings + ".wrinkleControls", json.dumps(metadata), type="string")
        if hide_source:
            cmds.hide(source_transform)
        cmds.select(settings)
        return {"group": group, "settings": settings, "graph": graph, "output": output,
                "output_shape": output_shape, "converter": converter, "source_shape": shape,
                "vertices": len(points), "regions": list(REGIONS),
                "compact": bool(compact), "in_place": bool(in_place), "regional_support": regional}
    except Exception:
        # Undo the incomplete trial in one step; never leave a half-built graph.
        cmds.undoInfo(closeChunk=True)
        chunk_open = False
        if cmds.undoInfo(query=True, state=True):
            cmds.undo()
        else:
            if in_place and upstream and cmds.objExists(shape):
                cmds.connectAttr(upstream, shape + '.inMesh', force=True)
                for destination, connection in consumers.items():
                    if cmds.objExists(destination):
                        cmds.connectAttr(connection['original'], destination, force=True)
            for node in (group, converter):
                if node and cmds.objExists(node):
                    cmds.delete(node)
            if primary_nodes:
                cmds.delete([n for n in primary_nodes if cmds.objExists(n)])
        raise
    finally:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)


def _topology(mesh_fn):
    counts, indices = mesh_fn.getVertices()
    return hashlib.sha256(json.dumps([list(counts), list(indices)],
                                    separators=(",", ":")).encode("ascii")).hexdigest()


def _array(graph, attr):
    count = cmds.getAttr(graph + "." + attr, size=True)
    return list(cmds.getAttr("%s.%s[0:%d]" % (graph, attr, count - 1))) if count else []


def _indices(graph, attr):
    if cmds.attributeQuery(attr + 'Encoded', node=graph, exists=True):
        return [v - 1 for v in _array(graph, attr + 'Encoded')]
    return _array(graph, attr)


def export_setups():
    """Snapshot native rest fields and live settings, independently of pose.

    Maps remain vertex based, so exporting a posed face never changes its rest
    compression. Legacy prototypes are recognized by their sourceMesh link.
    """
    records = []
    for settings in cmds.ls("*_Settings", type="transform") or []:
        if not cmds.attributeQuery("sourceMesh", node=settings, exists=True):
            continue
        prefix = settings.rsplit("_Settings", 1)[0]
        graph = prefix + "GraphShape"
        if not cmds.objExists(graph) or cmds.nodeType(graph) != "bifrostGraphShape":
            continue
        source = cmds.connectionInfo(settings + ".sourceMesh", sourceFromDestination=True).split(".")[0]
        shape, path, fn = _mesh_fn(source)
        controls = []
        compact_fields = json.loads(cmds.getAttr(settings + '.wrinkleRegionalFields')) if cmds.attributeQuery(
            'wrinkleRegionalFields', node=settings, exists=True) else None
        metadata = json.loads(cmds.getAttr(settings + ".wrinkleControls") or "[]") if cmds.attributeQuery(
            "wrinkleControls", node=settings, exists=True) else []
        for field in metadata:
            controls.append({"controller": field["controller"],
                             "values": {a: cmds.getAttr(field["controller"] + "." + a)
                                        for a in ("wrinkleDepth", "wrinkleValue")},
                             "masks": compact_fields['masks'][field['port'].removeprefix('Local')] if compact_fields else
                                      {r: [max(0., min(1., v - 2)) for v in _array(
                                          graph, field["port"] + r + "MaskEncoded")] for r in field["regions"]}})
        in_place = bool(cmds.getAttr(settings + '.wrinkleInPlace')) if cmds.attributeQuery(
            'wrinkleInPlace', node=settings, exists=True) else False
        output_transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0] if in_place else prefix + '_Face'
        output_shape = _mesh_fn(output_transform)[0]
        records.append({"version": 1, "prefix": prefix,
                        "source": cmds.listRelatives(shape, parent=True, fullPath=True)[0],
                        "vertices": fn.numVertices, "topology": _topology(fn),
                        "patterns": compact_fields['patterns'] if compact_fields else {r: [v - 2 for v in _array(graph, r + "FlowEncoded")] for r in REGIONS},
                        "rest": compact_fields['rest'] if compact_fields else {"neighbors": [_indices(graph, "Neighbor%d" % i) for i in range(4)],
                                 "lengths": [_array(graph, "RestLength%d" % i) for i in range(4)]},
                        "settings": {a: cmds.getAttr(settings + "." + a) for a in
                                     ("Envelope", "Depth", "CompressionStart", "CompressionRange", "ManualActivation") + REGIONS},
                        "controls": controls,
                        "visible": bool(cmds.getAttr(output_transform + '.visibility')),
                        "in_place": in_place,
                        "compact": cmds.attributeQuery('regionalSupport', node=graph, exists=True)})
        records[-1]['display_settings'] = {a: cmds.getAttr(output_shape + '.' + a) for a in
            ('displaySmoothMesh', 'smoothLevel', 'useSmoothPreviewForRender', 'renderSmoothLevel')}
        if cmds.attributeQuery("wrinklePreset", node=settings, exists=True):
            records[-1]["preset"] = cmds.getAttr(settings + ".wrinklePreset")
    return records


def edward_control_fields(mesh):
    """Partition each region into smooth local controller masks in rest space."""
    shape, path, fn = _mesh_fn(mesh)
    points = fn.getPoints()
    groups = {
        "Forehead": ["C_eyebrowMid_CTL"] + [s + "_eyebrow" + part + "_CTL"
            for s in ("L", "R") for part in ("Main", "In", "Mid", "Out")],
        "Eyes": [s + "_eyelid" + part + "_CTL" for s in ("L", "R") for part in ("Out", "Up", "Down")],
        "Cheeks": ["L_lipCorner_CTL", "R_lipCorner_CTL", "C_upperLip_CTL", "C_lowerLip_CTL",
                   "L_cheek_CTL", "R_cheek_CTL"],
        "Nose": ["C_noseMain_CTL", "C_noseTip_CTL", "L_nose_CTL", "R_nose_CTL"],
        "Chin": ["C_jaw_CTL", "C_lowerLip_CTL"],
    }
    fields = {}
    inverse = path.inclusiveMatrixInverse()
    for region, names in groups.items():
        names = [name for name in names if cmds.objExists(name)]
        centers = [om.MPoint(*cmds.xform(name, query=True, worldSpace=True, translation=True)) * inverse
                   for name in names]
        for name in names:
            fields.setdefault(name, {"controller": name, "masks": {}})["masks"][region] = []
        for point in points:
            distances = [(point.x - p.x) ** 2 + (point.y - p.y) ** 2 for p in centers]
            minimum = min(distances) if distances else 0.
            weights = [math.exp(-(d - minimum) / 8.) for d in distances]
            total = sum(weights)
            for name, weight in zip(names, weights):
                fields[name]["masks"][region].append(weight / total)
    return list(fields.values())


def remove_setup(settings):
    """Remove owned detail while restoring its primary geometry and consumers."""
    prefix = settings.rsplit('_Settings', 1)[0]
    primary = []
    if cmds.attributeQuery('wrinklePrimaryNodes', node=settings, exists=True):
        for index in cmds.getAttr(settings + '.wrinklePrimaryNodes', multiIndices=True) or []:
            plug = cmds.connectionInfo(settings + '.wrinklePrimaryNodes[%d]' % index, sourceFromDestination=True)
            if plug:
                primary.append(plug.split('.')[0])
    if cmds.attributeQuery('wrinkleInPlace', node=settings, exists=True) and cmds.getAttr(settings + '.wrinkleInPlace'):
        source = cmds.connectionInfo(settings + '.sourceMesh', sourceFromDestination=True).split('.')[0]
        upstream = cmds.connectionInfo(prefix + 'GraphShape.AnimatedFace', sourceFromDestination=True)
        if cmds.attributeQuery('wrinklePrimaryBridge', node=settings, exists=True) and cmds.getAttr(settings + '.wrinklePrimaryBridge'):
            upstream = cmds.connectionInfo(upstream.split('.')[0] + '.inMesh', sourceFromDestination=True)
        if not upstream or not cmds.objExists(upstream):
            raise ValueError('The primary wrinkle input is missing; refusing removal.')
        cmds.connectAttr(upstream, source + '.inMesh', force=True)
        consumers = json.loads(cmds.getAttr(settings + '.wrinklePrimaryConsumers') or '{}')
        for destination, connection in consumers.items():
            if cmds.objExists(destination):
                current = cmds.connectionInfo(destination, sourceFromDestination=True)
                if current == connection['replacement']:
                    cmds.connectAttr(connection['original'], destination, force=True)
    in_place = cmds.attributeQuery('wrinkleInPlace', node=settings, exists=True) and cmds.getAttr(settings + '.wrinkleInPlace')
    owned = [prefix + '_GRP', prefix + '_ToMaya'] + primary + ([] if in_place else [prefix + '_Face'])
    cmds.delete([n for n in owned if cmds.objExists(n)])


def import_setups(records, replace_existing=False):
    """Restore setup only after skin/correctives, with strict topology matching."""
    restored = []
    for record in records or []:
        if record.get("version") != 1:
            raise ValueError("Unsupported wrinkle snapshot version.")
        source = record["source"]
        if not cmds.objExists(source):
            matches = cmds.ls(source.rsplit("|", 1)[-1], long=True) or []
            if len(matches) != 1:
                raise ValueError("Cannot resolve wrinkle source: " + source)
            source = matches[0]
        shape, path, fn = _mesh_fn(source)
        if fn.numVertices != record["vertices"] or _topology(fn) != record["topology"]:
            raise ValueError("Wrinkle topology changed; vertex masks cannot be projected safely.")
        prefix = record["prefix"]
        if cmds.objExists(prefix + "_GRP") and not replace_existing:
            continue
        for field in record.get("controls", []):
            if not cmds.objExists(field["controller"]):
                raise ValueError("Missing wrinkle controller: " + field["controller"])
        if cmds.objExists(prefix + "_GRP"):
            remove_setup(prefix + '_Settings')
        if cmds.objExists(prefix + "_ToMaya"):
            cmds.delete(prefix + "_ToMaya")
        setup = build(source, prefix=prefix, patterns=record["patterns"],
                      rest_data=record["rest"], control_fields=record.get("controls"),
                      hide_source=record.get("visible", True) and not record.get('in_place', False),
                      compact=record.get('compact', False), in_place=record.get('in_place', False))
        for attr, value in record["settings"].items():
            cmds.setAttr(setup["settings"] + "." + attr, value)
        if record.get("preset"):
            cmds.addAttr(setup["settings"], longName="wrinklePreset", dataType="string")
            cmds.setAttr(setup["settings"] + ".wrinklePreset", record["preset"], type="string")
        if cmds.getAttr(setup['output'] + '.visibility', settable=True):
            cmds.setAttr(setup["output"] + ".visibility", record.get("visible", True))
        for attr, value in record.get('display_settings', {}).items():
            cmds.setAttr(setup['output_shape'] + '.' + attr, value)
        restored.append(setup)
    return restored


def migrate_regional(settings, in_place=True):
    """Explicit migration preserving rest data, local controls and detail modes."""
    from maya_tools.scripts.tools import rig_performance
    record = next((r for r in export_setups() if r['prefix'] + '_Settings' == settings), None)
    if not record:
        raise ValueError('Choose a valid wrinkle settings node.')
    detail_modes = rig_performance.export_detail_modes()
    old_output = record['source'] if record.get('in_place') else record['prefix'] + '_Face'
    record.update(compact=True, in_place=bool(in_place))
    cmds.undoInfo(openChunk=True, chunkName='Regional wrinkle migration')
    chunk_open = True
    try:
        result = import_setups([record], replace_existing=True)[0]
        for detail in detail_modes:
            for key in ('high', 'low'):
                detail[key] = [result['output'] if node.rsplit('|', 1)[-1] == old_output.rsplit('|', 1)[-1]
                               else node for node in detail[key]]
            old_keys = [p for p in detail['original_values'] if p.rsplit('.', 1)[0].rsplit('|', 1)[-1] == old_output.rsplit('|', 1)[-1]]
            for old in old_keys:
                value = detail['original_values'].pop(old)
                detail['original_values'][result['output'] + '.visibility'] = value
        rig_performance.restore_detail_modes(detail_modes)
        return result
    except Exception:
        cmds.undoInfo(closeChunk=True)
        chunk_open = False
        cmds.undo()
        raise
    finally:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)
