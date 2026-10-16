"""Authoring-only surface brush. No frame callbacks or AutoRig imports."""
from pathlib import Path
import uuid

from maya import cmds
from maya.api import OpenMaya as om

from . import core, topology

_controller = None
_commits = {}
CONTEXT_COMMAND = 'ngNurbsSurfaceContext'
COMMIT_COMMAND = 'ngNurbsSurfaceCommit'


def load_plugin():
    path = str(Path(__file__).with_name('brush_plugin.py'))
    if not cmds.pluginInfo(path, query=True, loaded=True):
        cmds.loadPlugin(path, quiet=True)


def active():
    return _controller


def stop():
    global _controller
    controller = _controller
    _controller = None
    if controller:
        controller.cancel()
        if cmds.currentCtx() == 'ngNurbsSurfaceBrush1':
            cmds.setToolTo('selectSuperContext')


def start(controller):
    global _controller
    stop()
    controller.bridge.validate()
    load_plugin()
    if not cmds.contextInfo('ngNurbsSurfaceBrush1', exists=True):
        getattr(cmds, CONTEXT_COMMAND)('ngNurbsSurfaceBrush1')
    _controller = controller
    controller.preview()
    cmds.setToolTo('ngNurbsSurfaceBrush1')


def commit(bridge, layer_id, before, after):
    if before == after:
        return
    load_plugin()
    token = str(uuid.uuid4())
    _commits[token] = (bridge.identity, layer_id, before, after)
    try:
        getattr(cmds, COMMIT_COMMAND)(token)
    finally:
        _commits.pop(token, None)


class Controller:
    def __init__(self, bridge, layer_id, target, mode='Replace', radius=1.0,
                 intensity=0.25, value=1.0, changed=None):
        self.bridge, self.layer_id, self.target = bridge, layer_id, target
        self.mode, self.radius = mode, radius
        self.intensity, self.value = intensity, value
        self.changed = changed or (lambda: None)
        self.before = None
        self.last_hit = None
        self.display = None
        self.original_locks = None
        self.error = ''
        self.dabs = 0
        self._last_position = None

    def layer(self):
        from ngSkinTools2 import api
        return api.Layer.load(self.bridge.proxy_skin, self.layer_id)

    def values(self):
        count = self.bridge.data['topology']['nu']*self.bridge.data['topology']['nv']
        values = self.layer().get_weights(self.target)
        if not values:
            values = [1.0 if self.target == 'mask' else 0.0]*count
        if len(values) != count:
            raise ValueError('NG layer vertex count no longer matches the NURBS CV map.')
        return values

    def begin(self):
        if self.before is not None:
            return
        self.bridge.validate()
        if not cmds.undoInfo(query=True, state=True):
            raise ValueError('Enable Maya Undo before painting NURBS layers.')
        layer = self.layer()
        self.original_locks = list(layer.locked_influences)
        locked = set(self.original_locks)
        for inf in self.bridge.data['proxy_influences']:
            node = core.node_for(inf['uuid'])
            if cmds.attributeQuery('liw', node=node, exists=True) and cmds.getAttr(node+'.liw'):
                locked.add(inf['logical'])
        if self.target in locked:
            self.original_locks = None
            raise ValueError('This influence is locked.')
        self.before = core.layer_snapshot(self.bridge, self.layer_id)
        with core.no_undo():
            layer.locked_influences = sorted(locked)
        self._last_position = None

    def _restore_locks(self):
        if self.original_locks is not None:
            with core.no_undo():
                self.layer().locked_influences = self.original_locks
            self.original_locks = None

    def finish(self):
        if self.before is None:
            return
        try:
            self.bridge.validate()
            after = core.layer_snapshot(self.bridge, self.layer_id)
            before = self.before
            self._restore_locks()
            commit(self.bridge, self.layer_id, before, after)
            self.before = None
        except BaseException:
            self.cancel()
            raise
        self.changed()

    def cancel(self):
        if self.before is not None:
            before, self.before = self.before, None
            try:
                core.apply_snapshot(self.bridge, self.layer_id, before)
            finally:
                self._restore_locks()

    def apply(self, coverage, inverted=False, smooth=False):
        """One NG write per dab; its normalizer respects the layer locks."""
        if self.before is None:
            self.begin()
        data = self.bridge.validate(check_links=False)
        values = self.values()
        original = list(values)
        mode = 'Smooth' if smooth else self.mode
        graph = topology.neighbors(data['topology'], data['active'])
        for index, falloff in coverage.items():
            alpha = min(1.0, max(0.0, self.intensity*falloff))
            if mode == 'Replace':
                wanted = 1.0-self.value if inverted else self.value
            elif mode == 'Add':
                wanted = values[index] + (-self.value if inverted else self.value)
            elif mode == 'Scale':
                wanted = values[index]*(max(0.0, 1.0-self.value) if inverted else 1.0+self.value)
            else:
                adjacent = graph[index]
                mean = sum(original[i] for i in adjacent)/len(adjacent) if adjacent else original[index]
                wanted = mean if mode == 'Smooth' else 2*original[index]-mean
            values[index] = max(0.0, min(1.0, original[index]+alpha*(wanted-original[index])))
        for i in range(len(values)):
            canonical = topology.canonical(i, data['topology'])
            if canonical in coverage:
                values[i] = values[canonical]
        from ngSkinTools2 import api
        layer = self.layer()
        if isinstance(self.target, int):
            ids = [i['logical'] for i in data['proxy_influences']]
            channels = {i: layer.get_weights(i) or [0.0]*len(values) for i in ids}
            source_channels = {i: list(v) for i, v in channels.items()}
            locked = set(layer.locked_influences)
            for index in coverage:
                old_total = sum(channels[i][index] for i in ids)
                fixed = sum(channels[i][index] for i in locked)
                wanted = min(values[index], max(0.0, 1.0-fixed))
                others = [i for i in ids if i != self.target and i not in locked]
                other_sum = sum(channels[i][index] for i in others)
                remainder = max(0.0, min(1.0, max(old_total, fixed+wanted))-fixed-wanted)
                if other_sum > 0:
                    for i in others:
                        channels[i][index] *= remainder/other_sum
                elif remainder > 0:
                    adjacent = graph[index]
                    nearby = {i: sum(source_channels[i][n] for n in adjacent) for i in others}
                    nearby_sum = sum(nearby.values())
                    if nearby_sum > 0:
                        for i in others:
                            channels[i][index] = remainder*nearby[i]/nearby_sum
                    elif old_total >= 1-1e-8:
                        # No existing local alternative can receive the remainder.
                        wanted += remainder
                channels[self.target][index] = wanted
            for index in range(len(values)):
                canonical = topology.canonical(index, data['topology'])
                if canonical in coverage:
                    for i in ids:
                        channels[i][index] = channels[i][canonical]
            with core.no_undo(), api.suspend_updates(self.bridge.proxy_skin):
                for i in ids:
                    if i not in locked:
                        layer.set_weights(i, channels[i], undo_enabled=False)
        else:
            with core.no_undo():
                layer.set_weights(self.target, values, undo_enabled=False)
        self.dabs += 1

    def dab(self, origin, direction, inverted=False, smooth=False):
        hit = topology.ray_hit(self.bridge.shape, origin, direction)
        if not hit:
            self.last_hit = None
            return False
        self.last_hit = hit
        # Scene-unit stroke spacing makes event frequency less influential.
        if self._last_position is not None and (hit[0]-self._last_position).length() < self.radius*0.08:
            return False
        data = self.bridge.data
        coverage = topology.footprint(self.bridge.shape, data['topology'], data['active'], hit[1], self.radius)
        if coverage:
            self.apply(coverage, inverted=inverted, smooth=smooth)
            self._last_position = om.MPoint(hit[0])
            self.preview()
            return True
        return False

    def flood(self, iterations=1):
        try:
            self.begin()
            for _ in range(iterations):
                self.apply({i: 1.0 for i in self.bridge.data['active']})
            self.finish()
            self.preview()
        except BaseException:
            self.cancel()
            raise

    def preview(self):
        data = self.bridge.data
        self.display = topology.surface_samples(self.bridge.shape, data['topology'], self.values())

    def draw(self, manager):
        from maya.api import OpenMayaRender as render
        if not self.display:
            return
        points, values, triangles = self.display
        colors = om.MColorArray([om.MColor((v, v, v, 0.72)) for v in values])
        manager.beginDrawable()
        manager.setDepthPriority(5)
        manager.mesh(render.MUIDrawManager.kTriangles, om.MPointArray(points),
                     color=colors, index=om.MUintArray(triangles))
        if self.last_hit:
            fn = om.MFnNurbsSurface(topology.dag(self.bridge.shape))
            uv = self.last_hit[1]
            normal = fn.normal(uv[0], uv[1], om.MSpace.kWorld)
            manager.setColor(om.MColor((1.0, 0.65, 0.2, 1.0)))
            manager.circle(self.last_hit[0], normal, self.radius, False)
        manager.endDrawable()
