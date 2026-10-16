"""NG data proxy and native DG weights, with explicit identity and rollback."""
from contextlib import contextmanager
import json
import math
from uuid import uuid4

from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma

from . import topology

SCHEMA = 1
MARKER = 'ngNurbsBridgeData'


def skin_fn(node):
    return oma.MFnSkinCluster(om.MSelectionList().add(node).getDependNode(0))


def plug(name):
    return om.MSelectionList().add(name).getPlug(0)


def uuid(node):
    return cmds.ls(node, uuid=True)[0]


def node_for(identity):
    nodes = cmds.ls(identity, long=True) or []
    if len(nodes) != 1:
        raise ValueError('A bridge node or influence is missing. Restore it before editing.')
    return nodes[0]


def influences(skin):
    fn = skin_fn(skin)
    return [dict(uuid=uuid(p.fullPathName()), logical=fn.indexForInfluenceObject(p))
            for p in fn.influenceObjects()]


@contextmanager
def transaction(label):
    if not cmds.undoInfo(query=True, state=True):
        raise ValueError('Enable Maya Undo before editing NURBS layers.')
    chunk = label+' ['+str(uuid4())[:8]+']'
    cmds.undoInfo(openChunk=True, chunkName=chunk)
    try:
        yield
    except BaseException:
        cmds.undoInfo(closeChunk=True)
        if cmds.undoInfo(query=True, undoName=True) == chunk:
            cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)


@contextmanager
def no_undo():
    enabled = cmds.undoInfo(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    try:
        yield
    finally:
        cmds.undoInfo(stateWithoutFlush=enabled)


def sparse_weights(skin):
    rows = plug(skin+'.weightList')
    result = {}
    for r in range(rows.numElements()):
        row = rows.elementByPhysicalIndex(r)
        weights = row.child(0)
        result[str(row.logicalIndex())] = {
            str(weights.elementByPhysicalIndex(i).logicalIndex()): weights.elementByPhysicalIndex(i).asDouble()
            for i in range(weights.numElements())}
    return result


def membership(shape, skin):
    fn = skin_fn(skin)
    index = fn.indexForOutputShape(topology.dag(shape).node())
    component = fn.getComponentAtIndex(index)
    iterator = om.MItGeometry(topology.dag(shape), component)
    result = []
    while not iterator.isDone():
        result.append(iterator.index())
        iterator.next()
    del iterator
    return sorted(result)


def skins_for(surface):
    return list(dict.fromkeys(cmds.ls(cmds.listHistory(surface, pruneDagObjects=True) or [],
                                   type='skinCluster') or []))


def bridges():
    return [Bridge(n) for n in (cmds.ls('*.ngNurbsBridgeData', objectsOnly=True) or [])
            if cmds.nodeType(n) == 'network']


def find(surface=None, skin=None):
    identity = uuid(topology.surface_shape(surface)) if surface else None
    skin_id = uuid(skin) if skin else None
    for bridge in bridges():
        data = bridge.data
        if (identity is None or data['surface_uuid'] == identity) and (
                skin_id is None or data['skin_uuid'] == skin_id):
            return bridge
    return None


def _message(meta, attribute, node):
    cmds.addAttr(meta, longName=attribute, attributeType='message')
    cmds.connectAttr(node+'.message', meta+'.'+attribute)


def create(surface, skin=None):
    from ngSkinTools2 import api
    from ngSkinTools2.api import plugin
    plugin.load_plugin()
    shape = topology.surface_shape(surface)
    existing = find(shape)
    if existing:
        existing.validate()
        return existing
    skins = skins_for(shape)
    if len(skins) != 1 or (skin and skin != skins[0]):
        raise ValueError('This version requires one skinCluster on the NURBS surface.')
    skin = skins[0]
    if cmds.referenceQuery(shape, isNodeReferenced=True) or cmds.referenceQuery(skin, isNodeReferenced=True):
        raise ValueError('Use a local surface and skinCluster; referenced editing is not supported.')
    if cmds.lockNode(skin, query=True, lock=True)[0] or plug(skin+'.weightList').isLocked:
        raise ValueError('The NURBS skin or weights are locked.')
    if cmds.listConnections(skin+'.weightList', source=True, destination=False, plugs=True):
        raise ValueError('The NURBS weights already have incoming connections.')
    if api.get_layers_enabled(skin):
        raise ValueError('Remove unsupported NG layer data from the NURBS skin before creating its bridge.')
    fn = om.MFnNurbsSurface(topology.dag(shape))
    if fn.isTrimmedSurface:
        raise ValueError('Trimmed surfaces are not supported by this version. Use an untrimmed source.')
    geometry_index = skin_fn(skin).indexForOutputShape(topology.dag(shape).node())
    rest = om.MFnNurbsSurface(skin_fn(skin).inputShapeAtIndex(geometry_index))
    spec = topology.signature_fn(rest)
    active = membership(shape, skin)
    if not active or any(topology.canonical(i, spec) != i for i in active):
        raise ValueError('The surface has unsupported CV deformer membership.')
    source_infs = influences(skin)
    if not source_infs:
        raise ValueError('The NURBS skin has no DAG influences.')
    snapshot = sparse_weights(skin)
    for row in active:
        if any(not math.isfinite(v) or v < 0 or v > 1 for v in snapshot.get(str(row), {}).values()):
            raise ValueError('CV weights must be finite values between zero and one (CV %s).' % row)
        if abs(sum(snapshot.get(str(row), {}).values())-1.0) > 1e-8:
            raise ValueError('CV weights must sum to one before creating the bridge (CV %s).' % row)
        rowplug = plug(skin+'.weightList[%s].weights' % row)
        if rowplug.isLocked or any(rowplug.elementByPhysicalIndex(i).isLocked for i in range(rowplug.numElements())):
            raise ValueError('A CV weight is locked. Unlock it before attaching.')
    count = spec['nu']*spec['nv']
    positions = rest.cvPositions(om.MSpace.kObject)
    if len(positions) != count:
        raise ValueError('Skin input and output CV counts differ.')
    blend = plug(skin+'.blendWeights')
    old_blend = {str(blend.elementByPhysicalIndex(i).logicalIndex()): blend.elementByPhysicalIndex(i).asDouble()
                 for i in range(blend.numElements())}
    if cmds.listConnections(skin+'.blendWeights', source=True, destination=False, plugs=True):
        raise ValueError('Driven DQ blend weights are not supported.')
    selection = cmds.ls(selection=True, long=True) or []
    auxiliary_before = set(cmds.ls(type=['dagPose', 'objectSet'], uuid=True) or [])
    with transaction('Create NURBS skin layers'):
        group = cmds.createNode('transform', name='ngNurbsBridge_GRP#')
        cmds.setAttr(group+'.visibility', False)
        cmds.setAttr(group+'.hiddenInOutliner', True)
        proxy = cmds.polyPlane(name='ngNurbsCVProxy#', subdivisionsX=spec['nv']-1,
                               subdivisionsY=spec['nu']-1, constructionHistory=False)[0]
        proxy = cmds.parent(proxy, group)[0]
        for index, point in enumerate(positions):
            cmds.xform(proxy+'.vtx[%s]' % index, objectSpace=True, translation=(point.x, point.y, point.z))
        paths = [node_for(i['uuid']) for i in source_infs]
        proxy_skin = cmds.skinCluster(paths, proxy, toSelectedBones=True, normalizeWeights=1,
                                      obeyMaxInfluences=False, maximumInfluences=len(paths),
                                      skinMethod=cmds.getAttr(skin+'.skinningMethod'))[0]
        proxy_shape = cmds.listRelatives(proxy, shapes=True, noIntermediate=True, fullPath=True)[0]
        if om.MFnMesh(topology.dag(proxy_shape)).numVertices != count:
            raise ValueError('Proxy creation did not preserve the raw CV vertex count.')
        proxy_infs = influences(proxy_skin)
        dest_by_uuid = {i['uuid']: i['logical'] for i in source_infs}
        raw = []
        for index in range(count):
            row = snapshot.get(str(topology.canonical(index, spec)), {})
            raw.extend(row.get(str(dest_by_uuid[i['uuid']]), 0.0) for i in proxy_infs)
            if not row:
                raw[-len(proxy_infs)] = 1.0
        component_fn = om.MFnSingleIndexedComponent()
        component = component_fn.create(om.MFn.kMeshVertComponent)
        component_fn.addElements(list(range(count)))
        skin_fn(proxy_skin).setWeights(topology.dag(proxy_shape), component,
                                      om.MIntArray(range(len(proxy_infs))), om.MDoubleArray(raw), False)
        skin_fn(proxy_skin).setBlendWeights(topology.dag(proxy_shape), component,
            om.MDoubleArray([old_blend.get(str(topology.canonical(i, spec)), 0.0) for i in range(count)]))
        layers = api.init_layers(proxy_skin)
        layers.add('Base weights')
        # Bulk API initialization also needs undoable values for CREATE redo.
        for index in range(count):
            for physical, inf in enumerate(proxy_infs):
                cmds.setAttr(proxy_skin+'.weightList[%s].weights[%s]' % (index, inf['logical']),
                             raw[index*len(proxy_infs)+physical])
        meta = cmds.createNode('network', name='ngNurbsBridge#')
        cmds.addAttr(meta, longName=MARKER, dataType='string')
        data = dict(schema=SCHEMA, surface_uuid=uuid(shape), skin_uuid=uuid(skin),
                    proxy_uuid=uuid(proxy_shape), proxy_skin_uuid=uuid(proxy_skin),
                    group_uuid=uuid(group), topology=spec, active=active,
                    source_influences=source_infs, proxy_influences=proxy_infs,
                    original_weights=snapshot, original_blend=old_blend,
                    skin_method=cmds.getAttr(skin+'.skinningMethod'), links=[])
        data['auxiliary_uuids'] = sorted(set(cmds.ls(type=['dagPose', 'objectSet'], uuid=True) or [])-auxiliary_before)
        for label, node in (('surface', shape), ('skin', skin), ('proxySkin', proxy_skin),
                            ('proxy', proxy_shape), ('owner', group), ('layers', layers.data_node)):
            _message(meta, label, node)
        for index in active:
            for inf in proxy_infs:
                target_logical = dest_by_uuid[inf['uuid']]
                cmds.connectAttr(proxy_skin+'.weightList[%s].weights[%s]' % (index, inf['logical']),
                                 skin+'.weightList[%s].weights[%s]' % (index, target_logical))
                data['links'].append([index, inf['logical'], target_logical])
            if data['skin_method'] == 2:
                if blend.isLocked or plug(skin+'.blendWeights[%s]' % index).isLocked:
                    raise ValueError('A DQ blend weight is locked.')
                cmds.connectAttr(proxy_skin+'.blendWeights[%s]' % index,
                                 skin+'.blendWeights[%s]' % index)
        cmds.setAttr(meta+'.'+MARKER, json.dumps(data, separators=(',', ':')), type='string')
        bridge = Bridge(meta)
        bridge.validate()
        observed = sparse_weights(skin)
        error = max(abs(observed[str(r)].get(str(i['logical']), 0)-snapshot[str(r)].get(str(i['logical']), 0))
                    for r in active for i in source_infs)
        if error > 1e-8:
            raise ValueError('NG initialization changed source weights by %.9g.' % error)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    return bridge


class Bridge:
    def __init__(self, metadata):
        self.identity = uuid(metadata)

    @property
    def node(self):
        return node_for(self.identity)

    @property
    def data(self):
        return json.loads(cmds.getAttr(self.node+'.'+MARKER))

    @property
    def shape(self):
        return node_for(self.data['surface_uuid'])

    @property
    def skin(self):
        return node_for(self.data['skin_uuid'])

    @property
    def proxy_skin(self):
        return node_for(self.data['proxy_skin_uuid'])

    def layers(self):
        from ngSkinTools2 import api
        return api.Layers(self.proxy_skin)

    def validate(self, check_links=True):
        data = self.data
        if data['schema'] != SCHEMA:
            raise ValueError('Unsupported NURBS bridge schema.')
        index = skin_fn(self.skin).indexForOutputShape(topology.dag(self.shape).node())
        authoring = topology.signature_fn(om.MFnNurbsSurface(skin_fn(self.skin).inputShapeAtIndex(index)))
        visible = topology.signature(self.shape)
        expected = data['topology']
        # An independently weighted closed seam can open under deformation.
        geometry_matches = all(visible[k] == value for k, value in expected.items() if k not in ('fu', 'fv'))
        periodic_matches = all(expected[k] != 3 or visible[k] == 3 for k in ('fu', 'fv'))
        if authoring != expected or not geometry_matches or not periodic_matches:
            raise ValueError('NURBS topology changed. Undo the topology edit before painting or detaching.')
        if influences(self.skin) != data['source_influences'] or influences(self.proxy_skin) != data['proxy_influences']:
            raise ValueError('Skin influences changed. Undo the influence edit before painting or detaching.')
        if cmds.getAttr(self.skin+'.skinningMethod') != data['skin_method']:
            raise ValueError('Skin method changed. Restore it before editing this bridge.')
        if check_links:
            for row, source, target in data['links']:
                if not cmds.isConnected(self.proxy_skin+'.weightList[%s].weights[%s]' % (row, source),
                                        self.skin+'.weightList[%s].weights[%s]' % (row, target)):
                    raise ValueError('A bridge weight connection was changed. Undo that edit before continuing.')
            if data['skin_method'] == 2:
                for row in data['active']:
                    if not cmds.isConnected(self.proxy_skin+'.blendWeights[%s]' % row,
                                            self.skin+'.blendWeights[%s]' % row):
                        raise ValueError('A bridge DQ connection was changed. Undo that edit before continuing.')
        return data

    def detach(self, restore=False):
        from . import brush
        brush.stop()
        data = self.validate()
        skin, proxy = self.skin, self.proxy_skin
        weights = data['original_weights'] if restore else sparse_weights(skin)
        blends = data['original_blend'] if restore else {
            str(i): plug(skin+'.blendWeights[%s]' % i).asDouble() for i in data['active']}
        with transaction('Restore original NURBS skin' if restore else 'Bake NURBS skin layers'):
            for row, source, target in data['links']:
                cmds.disconnectAttr(proxy+'.weightList[%s].weights[%s]' % (row, source),
                                    skin+'.weightList[%s].weights[%s]' % (row, target))
            if data['skin_method'] == 2:
                for i in data['active']:
                    cmds.disconnectAttr(proxy+'.blendWeights[%s]' % i, skin+'.blendWeights[%s]' % i)
            for row in data['active']:
                attribute = skin+'.weightList[%s].weights' % row
                wanted = weights.get(str(row), {})
                for index in cmds.getAttr(attribute, multiIndices=True) or []:
                    if str(index) not in wanted:
                        cmds.removeMultiInstance(attribute+'[%s]' % index, b=True)
                for index, value in wanted.items():
                    cmds.setAttr(attribute+'[%s]' % index, value)
                if restore and str(row) not in data['original_weights']:
                    cmds.removeMultiInstance(skin+'.weightList[%s]' % row, b=True)
            if data['skin_method'] == 2:
                for i in data['active']:
                    attribute = skin+'.blendWeights[%s]' % i
                    if str(i) in blends:
                        cmds.setAttr(attribute, blends[str(i)])
                    else:
                        cmds.removeMultiInstance(attribute, b=True)
            owned = [node_for(data['group_uuid']), proxy, self.node]
            layer_data = self.layers().data_node
            if layer_data:
                owned.append(layer_data)
            owned.extend(node_for(i) for i in data.get('auxiliary_uuids', []) if cmds.ls(i))
            cmds.delete(list(dict.fromkeys(owned)))


def layer_snapshot(bridge, layer_id):
    from ngSkinTools2 import api
    layer = api.Layer.load(bridge.proxy_skin, layer_id)
    targets = [i['logical'] for i in bridge.data['proxy_influences']] + ['mask', 'dq']
    return {str(i): layer.get_weights(i) for i in targets}


def apply_snapshot(bridge, layer_id, state):
    from ngSkinTools2 import api
    layer = api.Layer.load(bridge.proxy_skin, layer_id)
    with no_undo(), api.suspend_updates(bridge.proxy_skin):
        locked = layer.locked_influences
        layer.locked_influences = []
        try:
            for target, values in state.items():
                layer.set_weights(int(target) if target not in ('mask', 'dq') else target,
                                  values, undo_enabled=False)
        finally:
            layer.locked_influences = locked
