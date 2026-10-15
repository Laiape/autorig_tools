"""Selection-driven NG actions using the active skin's existing facial joints."""
import collections
import copy
import json
import math
import re
import uuid

from maya_tools.scripts.tools import facial_loop_skinning as loops

RIGGERS = (('lips', 'LIPS RIGGER'), ('eyelid', 'EYELID RIGGER'), ('eyebrow', 'EYEBROW RIGGER'))
REGION_NAMES = {'lips': 'Lips', 'eyelid': 'Eyelids', 'eyebrow': 'Eyebrows'}


def influence_role(joint, kind):
    """Recognize production ENV influences, with namespaces and JNT fallback."""
    name = joint.rsplit('|', 1)[-1].rsplit(':', 1)[-1]
    non_rotate = bool(re.search('non_?rot(?:ate)?', name, re.I))
    name = re.sub('non_?rot(?:ate)?', '', name, flags=re.I)
    patterns = {
        'lips': r'([LRC])_(upper|lower)Lip(\d+)_(?:ENV|JNT)',
        'eyelid': r'([LR])_(upper|down|lower)Eyelid(\d+)(?:Skinning)?_(?:ENV|JNT)',
        'eyebrow': r'([LR])_eyebrow(?:Skinning)?(\d+)_(?:ENV|JNT)',
    }
    if kind not in patterns:
        raise ValueError('Unknown facial rigger: ' + str(kind))
    match = re.fullmatch(patterns[kind], name, flags=re.I)
    if not match:
        return None
    groups = match.groups()
    side, part, number = (groups[0].upper(), groups[1].lower(), int(groups[2])) if len(groups) == 3 else (groups[0].upper(), 'brow', int(groups[1]))
    if part == 'down': part = 'lower'
    return dict(joint=joint, side=side, part=part, number=number, non_rotate=non_rotate,
                key=(side, part, number))


def _path(topology, start, end):
    queue = collections.deque([start]); previous = {start: None}
    while queue:
        vertex = queue.popleft()
        if vertex == end:
            result = []
            while vertex is not None:
                result.append(vertex); vertex = previous[vertex]
            return list(reversed(result))
        for other in sorted(topology.neighbors[vertex]):
            if other not in previous:
                previous[other] = vertex; queue.append(other)
    raise ValueError('The selected feature crosses disconnected geometry.')


def _brow_extension(topology, role, roles, column):
    """Let brow00 own the columns up to, and excluding, midEyebrow."""
    if role['number'] != 0:
        return None
    neighbor = next((r for r in roles if r['side'] == role['side'] and r['number'] == 1), None)
    if neighbor is None:
        raise ValueError('Eyebrow00 needs eyebrow01 to determine the inward direction.')
    outward = _path(topology, role['anchor'], neighbor['anchor'])
    previous, current = outward[1], role['anchor']
    inward = []
    while True:
        following = topology.opposite(previous, current)
        if following is None:
            raise ValueError('The eyebrow stops at a pole before midEyebrow; include the desired inward edges in the selection.')
        if abs(topology.points[following][0]) < 1e-4:
            mid = following; break
        if following in inward or abs(topology.points[following][0]) >= abs(topology.points[current][0]):
            raise ValueError('Eyebrow00 cannot find the path toward midEyebrow.')
        inward.append(following); previous, current = current, following
    extended = loops.plan_columns(topology, [mid] + list(reversed(inward)) + outward)
    excluded = set(extended['columns'][0]['vertices'])
    allowed = set(column['vertices'])
    for extra in extended['columns'][1:1+len(inward)]:
        allowed.update(extra['vertices'])
    allowed -= excluded
    reachable, queue = {column['anchor']}, [column['anchor']]
    while queue:
        for other in topology.neighbors[queue.pop()].intersection(allowed) - reachable:
            reachable.add(other); queue.append(other)
    column['vertices'] = sorted(reachable)
    return dict(inner_vertices=inward, mid_vertex=mid, excluded_mid_loop=sorted(excluded))


def prepare(kind, skin, selection=None, tolerance=.05):
    """Validate everything before changing NG, influences or the Maya selection.

    A feature contour generates the transverse columns at its joint anchors.
    A single transverse loop is assigned literally and can update that joint
    incrementally. Coincident lip00 upper/lower anchors are paired automatically.
    """
    from maya import cmds
    if kind not in REGION_NAMES:
        raise ValueError('Unknown facial rigger: ' + str(kind))
    if not skin or not cmds.objExists(skin) or cmds.nodeType(skin) != 'skinCluster':
        raise ValueError('Choose the skinCluster above NG first.')
    geometry = cmds.skinCluster(skin, query=True, geometry=True) or []
    if len(geometry) != 1:
        raise ValueError('The active skinCluster must deform one polygon mesh.')
    mesh, topology = loops.read_skin_bind_mesh(geometry[0], skin)
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    selected = cmds.ls(selection if selection is not None else cmds.ls(sl=True), long=True, flatten=True) or []
    components = [s for s in selected if '.e[' in s]
    if not components:
        raise ValueError('Select one edge loop or connected edge chain on the active skinCluster mesh.')
    if any(s.split('.e[')[0] not in [mesh] + shapes for s in components):
        raise ValueError('The selected edges belong to a different mesh than the active skinCluster.')
    edges = [int(s.rsplit('[', 1)[1][:-1]) for s in components]
    seed = topology.order_edges(edges)
    influences = cmds.ls(cmds.skinCluster(skin, q=True, influence=True), long=True) or []
    roles = [role for joint in influences if (role := influence_role(joint, kind)) is not None]
    if not roles:
        raise ValueError('The active skinCluster has no {} facial influences.'.format(kind))
    ordinary = [r for r in roles if not r['non_rotate']]
    non_rotate = {r['key']: r for r in roles if r['non_rotate']}
    positions = loops.joint_bind_positions(skin)
    candidates = {r['joint']: [positions[r['joint']], cmds.xform(r['joint'],q=True,ws=True,translation=True)] for r in roles}
    for role in ordinary:
        distance, anchor = min((math.dist(p, topology.points[v]), v) for p in candidates[role['joint']] for v in range(len(topology.points)))
        selected_distance, selected_anchor = min((math.dist(p, topology.points[v]), v) for p in candidates[role['joint']] for v in seed)
        snap_tolerance = tolerance
        if kind == 'eyebrow':
            # Production brow joints lie on a smoothed curve, slightly inside
            # the polygon contour. Snap within the local edge spacing only.
            snap_tolerance = max(tolerance, .75*max(math.dist(topology.points[selected_anchor],topology.points[v])
                                                   for v in topology.neighbors[selected_anchor]))
        if selected_distance <= snap_tolerance:
            distance, anchor = selected_distance, selected_anchor
        role.update(anchor=anchor, anchor_distance=distance, snap_tolerance=snap_tolerance)
    matched = [r for r in ordinary if r['anchor'] in seed and r['anchor_distance'] <= r['snap_tolerance']]
    if not matched:
        raise ValueError('This loop contains no {} joint anchors. Select its feature contour or a transverse loop through a joint, with the rig in neutral.'.format(kind))
    if len({r['key'] for r in ordinary}) != len(ordinary):
        raise ValueError('The active skinCluster contains ambiguous duplicate facial joint names.')
    if kind == 'eyebrow' and len({(r['side'],r['anchor']) for r in matched}) != len(matched):
        raise ValueError('Two eyebrow joints project onto the same selected vertex. Select a denser brow contour.')
    # Detect the selected direction at the anchors. A transverse eyelid loop
    # can cross both upper and lower rows, so anchor count alone is ambiguous.
    selected_pairs = {tuple(sorted(topology.edges[e])) for e in edges}
    contour_votes = []
    for role in matched:
        neighbors = [r for r in ordinary if r['side'] == role['side'] and r['part'] == role['part']
                     and abs(r['number']-role['number']) == 1]
        if neighbors:
            directions = [tuple(b-a for a,b in zip(positions[role['joint']], positions[r['joint']])) for r in neighbors]
            selected_directions = [tuple(b-a for a,b in zip(topology.points[role['anchor']], topology.points[v]))
                                   for v in topology.neighbors[role['anchor']]
                                   if tuple(sorted((role['anchor'],v))) in selected_pairs]
            def aligned(a,b):
                lengths = math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
                return lengths>1e-12 and abs(sum(x*y for x,y in zip(a,b)))/lengths >= .7
            contour_votes.append(any(aligned(a,b) for a in directions for b in selected_directions))
    direct = not contour_votes or sum(contour_votes) < len(contour_votes)*.5
    closed = len(seed)>2 and seed[0] in topology.neighbors[seed[-1]]
    if kind == 'lips' and closed:
        corners = [r for r in matched if r['side'] != 'C' and r['number'] == 0]
        interior = collections.Counter(r['part'] for r in matched if r['number']>0)
        # A full commissure loop can follow one lip row on its inward leg.
        # A mouth contour contains the interior anchors of both rows.
        if corners and min(interior['upper'], interior['lower']) <= 1:
            direct = True
            matched = corners
    contour = None if direct else loops.plan_columns(topology, seed)
    columns = {} if contour is None else {c['anchor']: c for c in contour['columns']}
    mirror = any(r['side'] == 'L' for r in matched)
    mirrored_vertices = loops.symmetry_map(topology.points) if mirror else None
    by_key = {r['key']: r for r in ordinary}
    sections, extensions = [], []
    matched_keys = {r['key'] for r in matched}
    for role in matched:
        column = dict(anchor=role['anchor'], vertices=sorted(seed), paths=[seed], rows={}) if direct else copy.deepcopy(columns[role['anchor']])
        if kind == 'eyebrow' and not direct:
            extension = _brow_extension(topology, role, ordinary, column)
            if extension: extensions.append(extension)
        plan = dict(mesh=mesh, seed=[role['anchor']], columns=[column], affected=column['vertices'],
                    vertex_count=len(topology.points), topology_hash=topology.signature,
                    warnings=contour['warnings'] if contour else [], selection_mode='transverse' if direct else 'contour',
                    selected_edges=edges, rigger=kind, space='skin_bind', joint_anchors={role['joint']:role['anchor']})
        if kind == 'lips':
            partner = non_rotate.get(role['key'])
            if partner is None:
                raise ValueError('Missing Non Rotate influence for ' + role['joint'])
            if min(math.dist(p,topology.points[role['anchor']]) for p in candidates[partner['joint']]) > tolerance:
                raise ValueError('Non Rotate does not share the Rotate anchor: ' + partner['joint'])
            plan['joint_anchors'][partner['joint']] = role['anchor']
            nr = [partner['joint']]
        else:
            nr = []
        sections.append(dict(plan=plan, joints=[role['joint']], non_rotate_joints=nr))
        if role['side'] == 'L' and ('R', role['part'], role['number']) not in matched_keys:
            other = by_key.get(('R', role['part'], role['number']))
            if other is None:
                raise ValueError('Missing R mirror influence for ' + role['joint'])
            mirrored = copy.deepcopy(plan)
            vertices = {v for v in column['vertices']} | {role['anchor']}
            if any(mirrored_vertices[v] < 0 for v in vertices):
                raise ValueError('The mesh has no exact X mirror for the selected loop.')
            reflected_anchor = mirrored_vertices[role['anchor']]
            if min(math.dist(p,topology.points[reflected_anchor]) for p in candidates[other['joint']]) > role['snap_tolerance']:
                raise ValueError('The mirrored R joint does not match the reflected L anchor. Return the rig to neutral.')
            reflected_column = dict(anchor=reflected_anchor, vertices=sorted(mirrored_vertices[v] for v in column['vertices']),
                                    paths=[[mirrored_vertices[v] for v in p] for p in column['paths']], rows={})
            mirrored.update(seed=[reflected_anchor], columns=[reflected_column], affected=reflected_column['vertices'],
                            joint_anchors={other['joint']:reflected_anchor})
            if kind == 'lips':
                other_nr = non_rotate.get(other['key'])
                if other_nr is None: raise ValueError('Missing mirrored Non Rotate influence for ' + other['joint'])
                if min(math.dist(p,topology.points[reflected_anchor]) for p in candidates[other_nr['joint']]) > tolerance:
                    raise ValueError('Mirrored Non Rotate does not share the Rotate anchor: ' + other_nr['joint'])
                mirrored['joint_anchors'][other_nr['joint']] = reflected_anchor
                nr = [other_nr['joint']]
            sections.append(dict(plan=mirrored, joints=[other['joint']], non_rotate_joints=nr))
    return dict(kind=kind, skin=skin, mesh=mesh, sections=sections, mirror=mirror,
                mode='transverse' if direct else 'contour', selected_components=components,
                matched_joints=len(matched), brow_extensions=extensions)


def apply(kind, skin, selection=None, tolerance=.05):
    """One undoable update. Newly created facial masks are always black."""
    from maya import cmds
    prepared = prepare(kind, skin, selection, tolerance)
    original_selection = cmds.ls(sl=True, long=True) or []
    chunk = 'NGFacialRigger_' + uuid.uuid4().hex
    failed = False
    cmds.undoInfo(openChunk=True, chunkName=chunk)
    try:
        sections = prepared['sections']
        first = sections[0]
        group, metadata = loops.create_ng_region(first['plan'], first['joints'], skin, REGION_NAMES[kind],
            non_rotate_joints=first['non_rotate_joints'], additional_regions=sections[1:],
            mirror=prepared['mirror'], tolerance=tolerance, initial_mask='black')
        record = json.loads(cmds.getAttr(metadata + '.loopRegionData'))
        return dict(kind=kind, skin=skin, mesh=prepared['mesh'], layer=group.name, layer_id=group.id,
                    mode=prepared['mode'], assignments=len(record['assignments']), vertices=len(record['affected']),
                    metadata=metadata, mirrored=prepared['mirror'], brow_extensions=prepared['brow_extensions'])
    except Exception:
        failed = True
        raise
    finally:
        cmds.select(original_selection, replace=True, noExpand=True) if original_selection else cmds.select(clear=True)
        cmds.undoInfo(closeChunk=True)
        if failed and cmds.undoInfo(q=True, state=True) and cmds.undoInfo(q=True, undoName=True) == chunk:
            cmds.undo()
