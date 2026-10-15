"""Topological transverse columns and isolated ngSkinTools facial layers."""
import collections
import colorsys
import hashlib
import json
import math
import heapq
import uuid


class Topology:
    def __init__(self, points, faces, edges=None):
        self.points = [tuple(point) for point in points]
        self.faces = [tuple(face) for face in faces]
        self.neighbors = [set() for _ in points]
        self.edge_faces = collections.defaultdict(set)
        self.vertex_faces = [set() for _ in points]
        for index, face in enumerate(self.faces):
            for i, vertex in enumerate(face):
                other = face[(i + 1) % len(face)]
                self.neighbors[vertex].add(other)
                self.neighbors[other].add(vertex)
                self.edge_faces[tuple(sorted((vertex, other)))].add(index)
                self.vertex_faces[vertex].add(index)
        self.edges = list(edges) if edges is not None else list(self.edge_faces)
        self.signature = hashlib.sha256(json.dumps([len(points), self.faces]).encode('ascii')).hexdigest()

    def opposite(self, previous, vertex):
        """Continue an edge loop only through an unambiguous quad vertex."""
        if any(len(self.faces[f]) != 4 for f in self.vertex_faces[vertex]):
            return None
        incoming = self.edge_faces[tuple(sorted((previous, vertex)))]
        candidates = [other for other in self.neighbors[vertex] if other != previous
                      and not incoming.intersection(self.edge_faces[tuple(sorted((vertex, other)))])]
        return candidates[0] if len(candidates) == 1 else None

    def order_edges(self, edge_indices):
        graph = collections.defaultdict(set)
        for index in set(edge_indices):
            a, b = self.edges[index]
            graph[a].add(b); graph[b].add(a)
        if len(graph) < 2 or any(len(adjacent) > 2 for adjacent in graph.values()):
            raise ValueError('Select one unbranched edge loop or open edge chain.')
        ends = sorted(vertex for vertex, adjacent in graph.items() if len(adjacent) == 1)
        if len(ends) not in (0, 2):
            raise ValueError('The seed must be one connected loop or chain.')
        start = ends[0] if ends else min(graph)
        ordered, previous, current = [], None, start
        while current not in ordered:
            ordered.append(current)
            choices = sorted(graph[current] - {previous})
            if not choices:
                break
            previous, current = current, choices[0]
        if len(ordered) != len(graph):
            raise ValueError('The selection contains more than one loop or chain.')
        return ordered


def read_mesh(mesh):
    from maya import cmds
    from maya.api import OpenMaya as om
    selection = om.MSelectionList(); selection.add(mesh)
    path = selection.getDagPath(0)
    if path.apiType() != om.MFn.kMesh:
        path.extendToShape()
    fn = om.MFnMesh(path)
    counts, vertices = fn.getVertices()
    faces, offset = [], 0
    for count in counts:
        faces.append(list(vertices[offset:offset + count])); offset += count
    topology = Topology([(p.x, p.y, p.z) for p in fn.getPoints(om.MSpace.kWorld)], faces,
                        [fn.getEdgeVertices(index) for index in range(fn.numEdges)])
    return cmds.listRelatives(path.fullPathName(), parent=True, fullPath=True)[0], topology


def read_skin_bind_mesh(mesh, skin):
    """Use skin input geometry and its bind matrix, independent of control poses."""
    from maya import cmds
    from maya.api import OpenMaya as om
    mesh, topology = read_mesh(mesh)
    selection = om.MSelectionList(); selection.add(skin + '.input[0].inputGeometry')
    data = selection.getPlug(0).asMObject()
    points = om.MFnMesh(data).getPoints(om.MSpace.kObject)
    matrix = om.MMatrix(cmds.getAttr(skin + '.geomMatrix'))
    if len(points) != len(topology.points):
        raise ValueError('The skin input topology does not match its output mesh.')
    topology.points = [(p.x,p.y,p.z) for p in (point * matrix for point in points)]
    return mesh, topology


def joint_bind_positions(skin):
    from maya import cmds
    from maya.api import OpenMaya as om, OpenMayaAnim as oma
    selection = om.MSelectionList(); selection.add(skin)
    fn = oma.MFnSkinCluster(selection.getDependNode(0))
    return {path.fullPathName(): list(om.MMatrix(cmds.getAttr('{}.bindPreMatrix[{}]'.format(
                skin, fn.indexForInfluenceObject(path)))).inverse())[12:15] for path in fn.influenceObjects()}


def plan_columns(topology, seed, rows=None, allowed=None):
    seed = list(seed)
    if len(set(seed)) != len(seed) or len(seed) < 2:
        raise ValueError('The seed must contain at least two distinct vertices.')
    if rows is not None and rows < 0:
        raise ValueError('Rows must be zero or greater.')
    closed = seed[0] in topology.neighbors[seed[-1]] and len(seed) > 2
    for a, b in zip(seed, seed[1:]):
        if b not in topology.neighbors[a]:
            raise ValueError('Seed vertices must follow consecutive mesh edges.')
    seed_set = set(seed)
    warnings, columns = [], []
    for i, anchor in enumerate(seed):
        along = set()
        if i > 0: along.add(seed[i - 1])
        if i < len(seed) - 1: along.add(seed[i + 1])
        if closed:
            along.update((seed[i - 1], seed[(i + 1) % len(seed)]))
        elif len(along) == 1:
            continuation = topology.opposite(next(iter(along)), anchor)
            if continuation is not None: along.add(continuation)
        starts = sorted(topology.neighbors[anchor] - along)
        if len(starts) > 2:
            warnings.append('Pole at seed vertex {}: column stops at its anchor.'.format(anchor))
            starts = []
        paths = []
        for first in starts:
            path, previous, current = [anchor], anchor, first
            while rows is None or len(path) <= rows:
                if current in path or (rows is not None and current in seed_set) or (allowed is not None and current not in allowed):
                    break
                path.append(current)
                following = topology.opposite(previous, current)
                if following is None:
                    if rows is None or len(path) <= rows:
                        warnings.append('Column {} stops at boundary/pole vertex {}.'.format(anchor, current))
                    break
                previous, current = current, following
            paths.append(path)
        columns.append({'anchor': anchor, 'paths': paths})
    # Keep the full traces. Weight ownership at intersections is resolved
    # within the feature layer, rather than by creating layers per joint.
    owners = collections.defaultdict(set)
    for index, column in enumerate(columns):
        for path in column['paths']:
            for vertex in path[1:]: owners[vertex].add(index)
    conflicts = {vertex for vertex, indices in owners.items() if len(indices) > 1}
    for column in columns:
        distances = {column['anchor']: 0}
        for path in column['paths']:
            if rows is not None:
                stop = next((i for i, vertex in enumerate(path) if vertex in conflicts), len(path))
                del path[stop:]
            distances.update({vertex: i for i, vertex in enumerate(path)})
        column['vertices'] = sorted(distances)
        column['rows'] = distances
    if conflicts:
        warnings.append('{} crossing vertices: closest seed along the traced loops owns each intersection.'.format(len(conflicts)))
    return {'seed': seed, 'closed': closed, 'columns': columns, 'rows': rows,
            'vertex_count': len(topology.points), 'topology_hash': topology.signature,
            'warnings': sorted(set(warnings)), 'crossing_vertices': sorted(conflicts),
            'affected': sorted({v for column in columns for v in column['vertices']})}


def from_selection(mesh, rows=None, allowed=None):
    from maya import cmds
    mesh, topology = read_mesh(mesh)
    selected = cmds.ls(selection=True, flatten=True, long=True) or []
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    edges = [int(item.rsplit('[', 1)[1][:-1]) for item in selected
             if '.e[' in item and item.split('.e[')[0] in [mesh] + shapes]
    if not edges:
        raise ValueError('Select one edge loop on the loaded mesh.')
    plan = plan_columns(topology, topology.order_edges(edges), rows, allowed)
    plan['mesh'] = mesh
    return plan


def create_joints(plan, prefix):
    from maya import cmds
    mesh, topology = read_mesh(plan['mesh'])
    if topology.signature != plan['topology_hash']:
        raise ValueError('Mesh topology changed. Preview the seed again.')
    base, number = prefix, 2
    while cmds.objExists(prefix + '_loopJoints_GRP'):
        prefix = '{}_{}'.format(base,number); number += 1
    group = cmds.createNode('transform', name=prefix + '_loopJoints_GRP')
    joints = []
    for index, vertex in enumerate(plan['seed']):
        joint = cmds.createNode('joint', name='{}_{:02d}_JNT'.format(prefix, index), parent=group)
        cmds.xform(joint, worldSpace=True, translation=topology.points[vertex])
        cmds.setAttr(joint + '.radius', .08)
        cmds.addAttr(joint, longName='loopSeedVertex', attributeType='long', defaultValue=vertex)
        joints.append(joint)
    return group, joints


def create_joint_pairs(plan, prefix):
    from maya import cmds
    group, rotate = create_joints(plan, prefix)
    non_rotate = []
    for joint in rotate:
        name = joint.rsplit('|', 1)[-1].replace('_JNT', 'NonRot_JNT')
        other = cmds.createNode('joint', name=name, parent=group)
        cmds.xform(other, worldSpace=True, translation=cmds.xform(joint, query=True, worldSpace=True, translation=True))
        cmds.setAttr(other + '.radius', .06)
        vertex = cmds.getAttr(joint + '.loopSeedVertex')
        cmds.addAttr(other, longName='loopSeedVertex', attributeType='long', defaultValue=vertex)
        non_rotate.append(other)
    return group, rotate, non_rotate


def match_joints(topology, seed, joints, tolerance=.05, positions=None, anchors=None):
    from maya import cmds
    if len(joints) != len(seed):
        raise ValueError('Load one joint per seed vertex ({} joints required).'.format(len(seed)))
    mapping = {}
    for joint in joints:
        if cmds.nodeType(joint) != 'joint':
            raise ValueError('Influences must be joints: ' + joint)
        full_name = cmds.ls(joint, long=True)[0]
        if anchors is not None and full_name in anchors:
            anchor = anchors[full_name]
            if anchor not in seed:
                raise ValueError('Stored joint anchor is outside the selected seed.')
            position = topology.points[anchor]
        else:
            position = positions[full_name] if positions is not None else cmds.xform(joint, query=True, worldSpace=True, translation=True)
        distance, anchor = min((math.dist(position, topology.points[v]), v) for v in seed)
        if distance > tolerance:
            raise ValueError('{} is {:.4f} units away from the seed; tolerance is {}.'.format(joint, distance, tolerance))
        if anchor in mapping:
            raise ValueError('Two joints map to vertex {}. Move the duplicate anchor.'.format(anchor))
        mapping[anchor] = joint
    return mapping


def column_distribution(topology, columns):
    """Hard loop ownership; coincident corner anchors share their entire loop."""
    candidates = collections.defaultdict(list)
    anchor_counts = collections.Counter(c['anchor'] for c in columns)
    for index, column in enumerate(columns):
        vertices = set(column['vertices'])
        distances = {column['anchor']: 0.0}
        queue = [(0.0, column['anchor'])]
        while queue:
            distance, vertex = heapq.heappop(queue)
            if distance > distances[vertex]: continue
            for other in topology.neighbors[vertex].intersection(vertices):
                value = distance + math.dist(topology.points[vertex], topology.points[other])
                if value < distances.get(other, float('inf')):
                    distances[other] = value; heapq.heappush(queue, (value, other))
        for vertex in vertices:
            if vertex not in distances:
                raise ValueError('Disconnected transverse column at seed {}.'.format(column['anchor']))
            candidates[vertex].append((distances[vertex], index))
    result = [{} for _ in columns]
    for vertex, choices in candidates.items():
        # A shared upper/lower corner must remain 50/50 even where another
        # complete loop crosses the commissure loop.
        corners = [c for c in choices if anchor_counts[columns[c[1]]['anchor']] > 1]
        choices = corners or choices
        best = min(distance for distance, _ in choices)
        selected = [index for distance,index in choices if abs(distance-best) < 1e-7]
        for index in selected: result[index][vertex] = 1.0 / len(selected)
    return result


def symmetry_map(points, tolerance=1e-4):
    buckets = collections.defaultdict(list)
    for vertex, point in enumerate(points):
        buckets[tuple(round(c/tolerance) for c in point)].append(vertex)
    result = []
    for point in points:
        reflected = (-point[0], point[1], point[2])
        cell = tuple(round(c/tolerance) for c in reflected)
        choices = [v for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1)
                   for v in buckets.get((cell[0]+x,cell[1]+y,cell[2]+z),())]
        distance, vertex = min(((math.dist(points[v],reflected),v) for v in choices),default=(float('inf'),-1))
        result.append(vertex if distance <= tolerance else -1)
    return result


def mirror_distribution(topology, assignments, weights):
    """Copy the positive X (L) result to R, using explicit L_/R_ names."""
    mirrors = symmetry_map(topology.points)
    lookup = {c['joint'].rsplit('|',1)[-1]:i for i,c in enumerate(assignments)}
    partners = []
    for column in assignments:
        label = column['joint'].rsplit('|',1)[-1]
        namespace, separator, short = label.rpartition(':')
        partner = ('R_' + short[2:]) if short.startswith('L_') else (('L_' + short[2:]) if short.startswith('R_') else short)
        partner = namespace + separator + partner
        if partner not in lookup: raise ValueError('Missing mirror influence: ' + partner)
        partners.append(lookup[partner])
    result = [{} for _ in assignments]
    for index, values in enumerate(weights):
        for vertex, value in values.items():
            if topology.points[vertex][0] < -1e-5: continue
            other = mirrors[vertex]
            if other < 0: raise ValueError('No symmetric vertex for {}.'.format(vertex))
            if other == vertex:
                result[index][vertex] = result[index].get(vertex,0) + value*.5
                target = result[partners[index]]
                target[vertex] = target.get(vertex,0) + value*.5
            else:
                result[index][vertex] = value
                result[partners[index]][other] = value
    return result


def override_coverage(topology, assignments, weights, overrides, mirror=False):
    """Assign explicit extra coverage to an anchor without adding NG layers.

    Coincident upper/lower anchors split equally. Mirroring affects only the
    requested vertices, so existing hand-painted weights elsewhere survive.
    """
    result = [dict(values) for values in weights]
    mirrors = symmetry_map(topology.points) if mirror else None
    paints = {}
    for entry in overrides:
        anchor = entry['anchor']
        targets = [i for i,c in enumerate(assignments) if c['anchor'] == anchor]
        if not targets: raise ValueError('Coverage anchor has no joint: {}'.format(anchor))
        reflected = [i for i,c in enumerate(assignments) if mirror and c['anchor'] == mirrors[anchor]]
        if mirror and not reflected: raise ValueError('Coverage anchor has no mirrored joint.')
        for vertex in entry['vertices']:
            if not 0 <= vertex < len(topology.points): raise ValueError('Invalid coverage vertex.')
            if mirror and topology.points[vertex][0] < -1e-5: continue
            if mirror and mirrors[vertex] < 0: raise ValueError('Missing mirrored coverage vertex.')
            if mirror and mirrors[vertex] == vertex:
                combined = targets + reflected
                paints[vertex] = {i:combined.count(i)/len(combined) for i in set(combined)}
            else:
                paints[vertex] = {i:1.0/len(targets) for i in targets}
                if mirror: paints[mirrors[vertex]] = {i:1.0/len(reflected) for i in reflected}
    for vertex, targets in paints.items():
        for values in result: values.pop(vertex,None)
        for index,value in targets.items(): result[index][vertex] = value
    return result


def create_ng_region(plan, joints, skin, name, non_rotate_joints=None, tolerance=.05,
                     additional_regions=None, mirror=False, initial_mask='coverage'):
    from maya import cmds
    from ngSkinTools2 import api
    from ngSkinTools2.api import target_info
    if initial_mask not in ('coverage', 'black'):
        raise ValueError('Initial mask must be coverage or black.')
    mesh, topology = (read_skin_bind_mesh(plan['mesh'], skin) if plan.get('space') == 'skin_bind' else read_mesh(plan['mesh']))
    if topology.signature != plan['topology_hash']:
        raise ValueError('Mesh topology changed. Preview the seed again.')
    geometry = cmds.skinCluster(skin, query=True, geometry=True) or []
    if not any(cmds.listRelatives(shape, parent=True, fullPath=True) == [mesh] for shape in geometry):
        raise ValueError('The selected skinCluster does not deform the seed mesh.')
    sections = [dict(plan=plan, joints=list(joints), non_rotate_joints=list(non_rotate_joints or []))]
    sections.extend(additional_regions or [])
    def canonical(section):
        return dict(section, joints=[cmds.ls(j,long=True)[0] for j in section['joints']],
                    non_rotate_joints=[cmds.ls(j,long=True)[0] for j in section.get('non_rotate_joints',[])])
    sections = [canonical(s) for s in sections]
    bind_positions = joint_bind_positions(skin) if plan.get('space') == 'skin_bind' else None
    previous, metadata = None, None
    for node in cmds.ls('*.loopRegionData', objectsOnly=True, recursive=True) or []:
        data = json.loads(cmds.getAttr(node + '.loopRegionData'))
        if data.get('schema') == 2 and data['skin'] == skin and data['layer_name'] == name:
            previous, metadata = data, node
            replacing = {joint for section in sections for joint in section['joints']}
            stored = [canonical(s) for s in data['sections']]
            kept = []
            for section in stored:
                overlap = replacing.intersection(section['joints'])
                if not overlap:
                    kept.append(section); continue
                if len(overlap) == len(section['joints']):
                    continue
                old_plan = section['plan']
                old_anchors = old_plan.get('joint_anchors') or {c['joint']:c['anchor'] for c in data['assignments']}
                old_anchors.update({c['non_rotate_joint']:c['anchor'] for c in data['assignments'] if c.get('non_rotate_joint')})
                mapping = match_joints(topology, old_plan['seed'], section['joints'], tolerance, positions=bind_positions, anchors=old_anchors)
                nr_mapping = (match_joints(topology, old_plan['seed'], section['non_rotate_joints'], tolerance,
                                           positions=bind_positions, anchors=old_anchors) if section.get('non_rotate_joints') else {})
                columns = [c for c in old_plan['columns'] if mapping[c['anchor']] not in replacing]
                anchors = [c['anchor'] for c in columns]
                kept_plan = dict(old_plan, seed=anchors, columns=columns, joint_anchors=old_anchors,
                                 affected=sorted({v for c in columns for v in c['vertices']}))
                kept_plan['coverage_overrides'] = [o for o in old_plan.get('coverage_overrides',[]) if o['anchor'] in anchors]
                kept.append(dict(section, plan=kept_plan, joints=[mapping[a] for a in anchors],
                                 non_rotate_joints=[nr_mapping[a] for a in anchors] if nr_mapping else []))
            sections = kept + sections
            break
    paired = bool(non_rotate_joints)
    assignments, all_joints = [], []
    for section in sections:
        current = section['plan']
        if current['topology_hash'] != topology.signature:
            raise ValueError('A stored section has stale topology. Preview the region again.')
        mapping = match_joints(topology, current['seed'], section['joints'], tolerance, positions=bind_positions, anchors=current.get('joint_anchors'))
        nr = section.get('non_rotate_joints') or []
        if bool(nr) != paired: raise ValueError('All sections of a region must use the same joint mode.')
        nr_mapping = match_joints(topology, current['seed'], nr, tolerance, positions=bind_positions, anchors=current.get('joint_anchors')) if nr else {}
        for column in current['columns']:
            assignments.append(dict(column, joint=mapping[column['anchor']], non_rotate_joint=nr_mapping.get(column['anchor'])))
        all_joints.extend(section['joints'] + nr)
    if len(set(cmds.ls(all_joints, long=True))) != len(all_joints):
        raise ValueError('Rotate and Non Rotate must use distinct joints.')
    chunk = 'FacialLoopSkinning_' + uuid.uuid4().hex
    failed = False
    cmds.undoInfo(openChunk=True, chunkName=chunk)
    try:
        api.plugin.load_plugin()
        for joint in all_joints:
            influences = cmds.skinCluster(skin, query=True, influence=True) or []
            if joint not in influences and (cmds.ls(joint, long=True) or [joint])[0] not in (cmds.ls(influences, long=True) or []):
                cmds.skinCluster(skin, edit=True, addInfluence=joint, weight=0, lockWeights=False)
        layers = api.init_layers(skin)
        if not layers.list(): layers.add('Base weights')
        if previous:
            group = resolve_layer(skin, previous)
            weight_layers = [resolve_layer(skin, r) for r in previous['weight_layers']]
        else:
            if any(layer.name == name for layer in layers.list()):
                raise ValueError('An unrelated NG layer already uses this region name: ' + name)
            group = layers.add(name, force_empty=True)
            # NG child index 0 is the bottom of the native tree.
            weight_layers = ([layers.add('Rotate', force_empty=True, parent=group),
                              layers.add('Non Rotate', force_empty=True, parent=group)] if paired else [group])
            if paired:
                weight_layers[0].index = 1
                weight_layers[1].index = 0
                if initial_mask == 'black':
                    group.set_weights(api.NamedPaintTarget.MASK, [0.0] * plan['vertex_count'])
        indices = {(info.path or info.name): info.logicalIndex for info in target_info.list_influences(skin)}
        weights = column_distribution(topology, assignments)
        if mirror: weights = mirror_distribution(topology, assignments, weights)
        overrides = [entry for section in sections for entry in section['plan'].get('coverage_overrides',[])]
        if overrides: weights = override_coverage(topology,assignments,weights,overrides,mirror=mirror)
        affected = sorted({v for values in weights for v in values})
        children = []
        with api.suspend_updates(skin):
            for number, layer in enumerate(weight_layers):
                if previous:
                    # Avoid NG rescaling intermediate replacements above 1.0.
                    zeros = [0.0] * plan['vertex_count']
                    for index in list(layer.get_used_influences()): layer.set_weights(index,zeros)
                for column, values in zip(assignments, weights):
                    target = column['non_rotate_joint'] if paired and number == 1 else column['joint']
                    full_joint = cmds.ls(target, long=True)[0]
                    index = indices.get(full_joint, indices.get(target))
                    if index is None: raise ValueError('NG could not resolve influence: ' + target)
                    array = [0.0] * plan['vertex_count']
                    for vertex,value in values.items(): array[vertex] = value
                    layer.set_weights(index, array)
                mask = [0.0] * plan['vertex_count']
                if initial_mask == 'coverage':
                    for vertex in affected: mask[vertex] = 1.0
                if previous:
                    old_mask = layer.get_weights(api.NamedPaintTarget.MASK)
                    for vertex in previous['affected']:
                        if old_mask: mask[vertex] = old_mask[vertex]
                layer.set_weights(api.NamedPaintTarget.MASK, mask)
                children.append({'layer_id':layer.id, 'layer_name':layer.name,
                                 'parent_name':group.name if paired else None,
                                 'kind':('rotate' if number == 0 else 'non_rotate') if paired else 'ordinary',
                                 'joints':[c['non_rotate_joint'] if paired and number == 1 else c['joint'] for c in assignments]})
        group.set_current()
        if not metadata:
            metadata = cmds.createNode('network', name=name.replace(' ', '_') + '_loopRegion')
            cmds.addAttr(metadata, longName='loopRegionData', dataType='string')
            for source, attr in ((mesh, 'mesh'), (skin, 'skinCluster')):
                cmds.addAttr(metadata, longName=attr, attributeType='message')
                cmds.connectAttr(source + '.message', metadata + '.' + attr)
        for column, values in zip(assignments, weights): column['weights'] = values
        record = dict(plan, schema=2, skin=skin, sections=sections, assignments=assignments, affected=affected,
                      joints={str(c['anchor']):c['joint'] for c in assignments},
                      layer_id=group.id, layer_name=group.name, weight_layers=children, mirrored=mirror)
        cmds.setAttr(metadata + '.loopRegionData', json.dumps(record), type='string')
        return group, metadata
    except Exception:
        failed = True
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
        if failed and cmds.undoInfo(query=True, state=True) and cmds.undoInfo(query=True, undoName=True) == chunk:
            cmds.undo()


def resolve_layer(skin, record):
    """NG renumbers IDs when loading a saved hierarchy; names survive it."""
    from ngSkinTools2.api import Layers
    name = record.get('layer_name') or record['joints'][0].rsplit('|', 1)[-1].removesuffix('_JNT')
    matches = [layer for layer in Layers(skin).list() if layer.name == name
               and (not record.get('parent_name') or (layer.parent and layer.parent.name == record['parent_name']))]
    if len(matches) != 1:
        raise ValueError('The NG review layer was renamed or is ambiguous: ' + name)
    return matches[0]


def preview_columns(plan, prefix='ARLoopPreview'):
    from maya import cmds
    _, topology = read_mesh(plan['mesh'])
    group = cmds.createNode('transform', name=prefix + '_GRP')
    for i, column in enumerate(plan['columns']):
        paths = column['paths']
        vertices = list(reversed(paths[0])) + paths[1][1:] if len(paths) == 2 else (paths[0] if paths else [])
        if len(vertices) < 2: continue
        curve = cmds.curve(degree=1, point=[topology.points[v] for v in vertices], name=prefix + '_{:02d}_CRV'.format(i))
        cmds.parent(curve, group)
        shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        cmds.setAttr(shape + '.overrideEnabled', True)
        cmds.setAttr(shape + '.overrideRGBColors', True)
        cmds.setAttr(shape + '.overrideColorRGB', *colorsys.hsv_to_rgb((i * .618034) % 1, .7, 1))
        cmds.setAttr(shape + '.lineWidth', 2)
    return group
