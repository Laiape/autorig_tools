"""Character-scoped semantic bindings, stored on native Maya nodes.

Names are discovery hints only. Once bound, message links and role keys survive
renaming, namespaces and native scene save/reopen. No runtime callbacks.
"""
import json
import re
from maya import cmds
from maya_tools.scripts.tools import pose_blendshapes as _poses

PREFIX = 'artRig'
FIELDS = ('role', 'side', 'module', 'index', 'kind')
KINDS = ('control', 'joint', 'mesh', 'landmark', 'reference')
SIDES = ('C', 'L', 'R')
KNOWN = {
    'shoulderFk': ('arm.upper.fk', 'arm'), 'elbowFk': ('arm.lower.fk', 'arm'),
    'wristFk': ('arm.hand.fk', 'arm'), 'armSettings': ('arm.settings', 'arm'),
    'hipFk': ('leg.upper.fk', 'leg'), 'kneeFk': ('leg.lower.fk', 'leg'),
    'ankleFk': ('leg.foot.fk', 'leg'), 'legSettings': ('leg.settings', 'leg'),
    'jaw': ('face.jaw', 'face'), 'lipCorner': ('face.lip.corner', 'face'),
    'eyebrowIn': ('face.brow.inner', 'face'), 'eyeDirect': ('face.eye', 'face'),
    'head': ('body.head', 'neck'), 'neck': ('body.neck', 'neck'),
}


def path(node):
    nodes = cmds.ls(node, long=True) or []
    if len(nodes) != 1:
        raise ValueError('Choose one unambiguous scene node: ' + str(node))
    return nodes[0]


def _attr(field):
    return PREFIX + field[0].upper() + field[1:]


def key(binding):
    return '/'.join(str(binding[f]) for f in ('module', 'side', 'role', 'index', 'kind'))


def _validate(binding):
    if binding['side'] not in SIDES or binding['kind'] not in KINDS:
        raise ValueError('Use C/L/R and a supported binding kind.')
    if type(binding['index']) is not int or binding['index'] < 0:
        raise ValueError('Binding index must be a nonnegative integer.')
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', binding[f]) for f in ('role', 'module')):
        raise ValueError('Use ASCII role/module identifiers without slashes.')


def root_for(node):
    node = path(node)
    if cmds.attributeQuery(_attr('root'), node=node, exists=True):
        roots = cmds.listConnections(node + '.' + _attr('root'), source=True, destination=False) or []
        if len(roots) == 1:
            return path(roots[0])
    parts = node.split('|')
    for end in range(len(parts), 1, -1):
        candidate = '|'.join(parts[:end])
        if cmds.attributeQuery(_attr('schema'), node=candidate, exists=True):
            return candidate
    return '|' + parts[1] if node.startswith('|') else None


def bindings(root):
    root = path(root)
    if cmds.attributeQuery(_attr('members'),node=root,exists=True):
        nodes=[path(n) for n in cmds.listConnections(root+'.'+_attr('members'),source=True,destination=False) or []]
    else:
        nodes = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True) or [])
    result = []
    for node in nodes:
        if not (node==root or node.startswith(root+'|')):
            continue
        if not all(cmds.attributeQuery(_attr(f), node=node, exists=True) for f in FIELDS):
            continue
        owner = cmds.listConnections(node + '.' + _attr('root'), source=True, destination=False) or []
        if len(owner) != 1 or path(owner[0]) != root:
            continue
        item = {f: cmds.getAttr(node + '.' + _attr(f)) for f in FIELDS}
        item.update(node=node, key=key(item), aliases=json.loads(cmds.getAttr(node + '.' + _attr('aliases')) or '[]'))
        result.append(item)
    return sorted(result, key=lambda r: (r['key'], r['node']))


@_poses.undoable
def bind(root, node, role, side='C', module='custom', index=0, kind='control', aliases=None):
    root, node = path(root), path(node)
    item = dict(role=role, side=side, module=module, index=index, kind=kind)
    _validate(item)
    if not (node == root or node.startswith(root + '|')):
        raise ValueError('The binding must belong to this character hierarchy.')
    if kind == 'joint' and cmds.nodeType(node) != 'joint':
        raise ValueError('Joint bindings require joints.')
    if kind == 'mesh' and not cmds.listRelatives(node, shapes=True, type='mesh', noIntermediate=True):
        raise ValueError('Mesh bindings require a polygon transform.')
    if any(b['key'] == key(item) and b['node'] != node for b in bindings(root)):
        raise ValueError('Duplicate semantic binding: ' + key(item))
    cmds.undoInfo(openChunk=True, chunkName='Bind rig role')
    try:
        if not cmds.attributeQuery(_attr('members'),node=root,exists=True):
            previous=bindings(root)
            cmds.addAttr(root,longName=_attr('members'),attributeType='message',multi=True)
            for position,old in enumerate(previous):
                cmds.connectAttr(old['node']+'.message',root+'.'+_attr('members')+'[%d]'%position)
        if not cmds.attributeQuery(_attr('schema'), node=root, exists=True):
            cmds.addAttr(root, longName=_attr('schema'), attributeType='long', defaultValue=1)
        for field, value in item.items():
            attr = _attr(field)
            if not cmds.attributeQuery(attr, node=node, exists=True):
                cmds.addAttr(node, longName=attr, **({'attributeType': 'long'} if field == 'index' else {'dataType': 'string'}))
            if field == 'index':
                cmds.setAttr(node + '.' + attr, value)
            else:
                cmds.setAttr(node + '.' + attr, value, type='string')
        for field, data_type in (('root', 'message'), ('aliases', 'string')):
            if not cmds.attributeQuery(_attr(field), node=node, exists=True):
                cmds.addAttr(node, longName=_attr(field), **({'attributeType': data_type} if data_type == 'message' else {'dataType': data_type}))
        if not cmds.isConnected(root + '.message', node + '.' + _attr('root')):
            cmds.connectAttr(root + '.message', node + '.' + _attr('root'), force=True)
        members=[path(n) for n in cmds.listConnections(root+'.'+_attr('members'),source=True,destination=False) or []]
        if node not in members:
            position=max(cmds.getAttr(root+'.'+_attr('members'),multiIndices=True) or [-1])+1
            cmds.connectAttr(node+'.message',root+'.'+_attr('members')+'[%d]'%position)
        cmds.setAttr(node + '.' + _attr('aliases'), json.dumps(list(aliases or [])), type='string')
    finally:
        cmds.undoInfo(closeChunk=True)
    return key(item)


def resolve(root, role=None, side='C', module=None, index=0, kind='control', binding_key=None):
    matches = [b for b in bindings(root) if (b['key'] == binding_key if binding_key else
        b['role'] == role and b['side'] == side and b['index'] == index and b['kind'] == kind
        and (module is None or b['module'] == module))]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous rig role: ' + str(binding_key or (role, side, module, index, kind)))
    return matches[0]['node']


def alias_node(root, alias):
    matches = [b['node'] for b in bindings(root) if alias in b['aliases']]
    if len(matches) > 1:
        raise ValueError('Ambiguous legacy role alias: ' + alias)
    return matches[0] if matches else None


def counterpart(node, destination_root=None, side=None):
    source_root = root_for(node)
    source = next((b for b in bindings(source_root) if b['node'] == path(node)), None)
    if source is None:
        return None
    return resolve(destination_root or source_root, source['role'], side or source['side'],
                   source['module'], source['index'], source['kind'])


def discover(root):
    """Conservative adapter for existing repository controls; never guesses unknown rigs."""
    root = path(root)
    existing = {b['node'] for b in bindings(root)}
    added, unknown = [], []
    for node in cmds.listRelatives(root, allDescendents=True, fullPath=True, type='transform') or []:
        leaf = node.rsplit('|', 1)[-1].split(':')[-1]
        match = re.fullmatch(r'([CLR])_(\w+)_CTL', leaf)
        if not match or node in existing:
            continue
        side, stem = match.groups()
        if stem not in KNOWN:
            unknown.append(node)
            continue
        role, module = KNOWN[stem]
        added.append(bind(root, node, role, side, module, aliases=[leaf]))
    return {'added': added, 'unbound_controls': unknown}


def snapshot(root):
    return {'format': 'autorig-role-bindings', 'version': 1,
            'bindings': [{**{f: b[f] for f in FIELDS}, 'key': b['key'], 'aliases': b['aliases'],
                          'node_hint': b['node'].rsplit('|', 1)[-1].split(':')[-1]} for b in bindings(root)]}


@_poses.undoable
def restore(root, snapshot, node_map=None):
    """Preflight every binding before changes; an explicit map handles different naming."""
    if snapshot.get('format') != 'autorig-role-bindings' or snapshot.get('version') != 1:
        raise ValueError('Unsupported role binding snapshot.')
    root = path(root)
    current = {b['key']: b['node'] for b in bindings(root)}
    descendants = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True) or [])
    plan, seen = [], set()
    for item in snapshot['bindings']:
        _validate(item)
        identity = key(item)
        if item.get('key') != identity or identity in seen:
            raise ValueError('Invalid or duplicate role snapshot key.')
        seen.add(identity)
        node = (node_map or {}).get(identity) or current.get(identity)
        if not node:
            matches = [n for n in descendants if n.rsplit('|', 1)[-1].split(':')[-1] == item['node_hint']]
            if len(matches) != 1:
                raise ValueError('Provide a destination node map for: ' + identity)
            node = matches[0]
        node = path(node)
        if not (node == root or node.startswith(root + '|')) or any(n == node for n, _ in plan):
            raise ValueError('A role snapshot node is outside the rig or mapped twice.')
        if item['kind']=='joint' and cmds.nodeType(node)!='joint':
            raise ValueError('Joint bindings require joints.')
        if item['kind']=='mesh' and not cmds.listRelatives(node,shapes=True,noIntermediate=True,type='mesh'):
            raise ValueError('Mesh bindings require polygon transforms.')
        if identity in current and current[identity]!=node:
            raise ValueError('A destination semantic binding already belongs to another node.')
        plan.append((node, item))
    cmds.undoInfo(openChunk=True, chunkName='Restore rig roles')
    try:
        for node, item in plan:
            bind(root, node, **{f: item[f] for f in FIELDS}, aliases=item['aliases'])
    finally:
        cmds.undoInfo(closeChunk=True)
    return len(plan)
