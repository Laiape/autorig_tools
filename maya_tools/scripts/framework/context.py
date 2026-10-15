"""Explicit character context, resolved by UUID rather than mutable DAG names."""
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import weakref

from maya import cmds

ASSETS = Path(__file__).resolve().parents[2] / 'assets'


def node(uuid):
    matches = cmds.ls(uuid, long=True) or [] if uuid else []
    return matches[0] if len(matches) == 1 else ''


def identity(path):
    matches = cmds.ls(path, uuid=True) or [] if path else []
    if len(matches) != 1:
        raise ValueError('Choose one unambiguous scene node.')
    return matches[0]


def transform(value):
    matches = cmds.ls(value.split('.')[0], long=True) or []
    if len(matches) != 1:
        raise ValueError('Choose one unambiguous scene node.')
    value = matches[0]
    if cmds.nodeType(value) in ('mesh', 'nurbsCurve', 'locator'):
        value = (cmds.listRelatives(value, parent=True, fullPath=True) or [''])[0]
    if cmds.nodeType(value) not in ('transform', 'joint'):
        raise ValueError('Choose a character root, mesh or controller.')
    return value


def is_mesh(value):
    return bool(value and cmds.objExists(value) and
                cmds.listRelatives(value, shapes=True, noIntermediate=True, type='mesh'))


def belongs(value, root):
    return bool(value and root and (value == root or value.startswith(root + '|')))


def character_root(value):
    """Use the existing rig_roles message/schema contract without importing UI."""
    value = transform(value)
    if cmds.attributeQuery('artRigRoot', node=value, exists=True):
        roots = cmds.listConnections(value + '.artRigRoot', source=True, destination=False) or []
        if len(roots) == 1:
            root = transform(roots[0])
            if not belongs(value, root):
                raise ValueError('The stored rig role root does not own this selection.')
            return root
    parts = value.split('|')
    for end in range(len(parts), 1, -1):
        ancestor = '|'.join(parts[:end])
        if cmds.attributeQuery('artRigSchema', node=ancestor, exists=True):
            return ancestor
    return '|' + parts[1]


def assets():
    return sorted(p.name for p in ASSETS.iterdir() if p.is_dir()) if ASSETS.is_dir() else []


def asset_for(root):
    names = {name.casefold(): name for name in assets()}
    return next((names[part.rsplit(':', 1)[-1].casefold()] for part in reversed(root.split('|'))
                 if part.rsplit(':', 1)[-1].casefold() in names), '')


def meshes(root):
    if not root or not cmds.objExists(root):
        return []
    shapes = cmds.listRelatives(root, allDescendents=True, fullPath=True, type='mesh') or []
    result = {cmds.listRelatives(shape, parent=True, fullPath=True)[0] for shape in shapes
              if not cmds.getAttr(shape + '.intermediateObject')}
    if is_mesh(root):
        result.add(root)
    return sorted(result)


def skins(mesh):
    return cmds.ls(cmds.listHistory(mesh, pruneDagObjects=True) or [], type='skinCluster') or [] if mesh else []


def sculpt_active():
    for name in ('maya_tools.scripts.tools.pose_blendshapes', 'tools.pose_blendshapes'):
        module = sys.modules.get(name)
        if module and module.edit_session():
            return True
    return False


@dataclass(frozen=True)
class CharacterContext:
    root_uuid: str = ''
    mesh_uuid: str = ''
    skin_uuid: str = ''
    asset: str = ''

    @property
    def root(self):
        return node(self.root_uuid)

    @property
    def mesh(self):
        mesh = node(self.mesh_uuid)
        return mesh if belongs(mesh, self.root) else ''

    @property
    def skin(self):
        skin = node(self.skin_uuid)
        return skin if skin in skins(self.mesh) else ''

    @property
    def namespace(self):
        leaf = self.root.rsplit('|', 1)[-1]
        return leaf.rsplit(':', 1)[0] if ':' in leaf else ''

    @property
    def asset_path(self):
        return ASSETS / self.asset if self.asset in assets() else None

    @property
    def key(self):
        return 'root:' + self.root_uuid if self.root else 'asset:' + str(self.asset_path) if self.asset_path else ''

    def summary(self):
        return dict(asdict(self), root=self.root, mesh=self.mesh, skin=self.skin, namespace=self.namespace)


class ContextService:
    def __init__(self):
        self.value = CharacterContext()
        self._listeners = []
        self._summary = None

    def subscribe(self, callback):
        reference = weakref.WeakMethod(callback) if getattr(callback, '__self__', None) else weakref.ref(callback)
        self._listeners.append(reference)
        return reference

    def unsubscribe(self, reference):
        if reference in self._listeners:
            self._listeners.remove(reference)

    def snapshot(self):
        current = self.value
        root = current.root
        mesh = current.mesh if root else ''
        skin = current.skin if mesh else ''
        return CharacterContext(current.root_uuid if root else '', current.mesh_uuid if mesh else '',
                                current.skin_uuid if skin else '', current.asset)

    def refresh(self):
        current = self.snapshot()
        if current != self.value or current.summary() != self._summary:
            self._set(current, force=True)
        return current

    def _set(self, candidate, force=False):
        previous = self.snapshot()
        if candidate != previous and not force and sculpt_active():
            raise ValueError('Finish the live sculpt before changing the active character or mesh.')
        self.value = candidate
        self._summary = candidate.summary()
        if candidate.asset and (not cmds.optionVar(exists='currentAssetRigName') or
                                cmds.optionVar(query='currentAssetRigName') != candidate.asset):
            cmds.optionVar(stringValue=('currentAssetRigName', candidate.asset))
        for reference in list(self._listeners):
            callback = reference()
            if callback is None:
                self.unsubscribe(reference)
            else:
                try:
                    callback(candidate)
                except RuntimeError:
                    self.unsubscribe(reference)  # Qt can already have destroyed the editor.
        return candidate

    def clear(self):
        return self._set(CharacterContext())

    def reset(self):
        return self._set(CharacterContext(), force=True)

    def set_asset(self, asset):
        if asset and asset not in assets():
            raise ValueError('Choose an asset from this checkout.')
        current = self.snapshot()
        if current.asset and current.asset != asset:
            current = CharacterContext()
        return self._set(CharacterContext(current.root_uuid, current.mesh_uuid, current.skin_uuid, asset))

    def set_root(self, root):
        root = transform(root)
        current = self.snapshot()
        candidates = meshes(root)
        mesh = current.mesh if current.root == root else candidates[0] if len(candidates) == 1 else ''
        candidates = skins(mesh)
        skin = current.skin if current.mesh == mesh else candidates[0] if len(candidates) == 1 else ''
        return self._set(CharacterContext(identity(root), identity(mesh) if mesh else '', identity(skin) if skin else '',
                                           asset_for(root) or (current.asset if current.root == root else '')))

    def capture_selection(self):
        selection = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        values = []
        for selected in selection:
            if cmds.nodeType(selected) == 'skinCluster':
                values.extend(cmds.skinCluster(selected, query=True, geometry=True) or [])
            else:
                values.append(selected)
        values = list(dict.fromkeys(transform(value) for value in values))
        if not values:
            raise ValueError('Select a character root, mesh or controller.')
        roots = {character_root(value) for value in values}
        if len(roots) != 1:
            raise ValueError('Selection contains multiple characters. Choose one character.')
        root = roots.pop()
        selected_meshes = [value for value in values if is_mesh(value)]
        if len(selected_meshes) > 1:
            raise ValueError('Choose one active mesh; multi-mesh actions keep their separate selection.')
        current = self.snapshot()
        mesh = selected_meshes[0] if selected_meshes else current.mesh if current.root == root else ''
        if not mesh:
            candidates = meshes(root)
            mesh = candidates[0] if len(candidates) == 1 else ''
        candidates = skins(mesh)
        explicit = [value for value in selection if value in candidates]
        skin = explicit[0] if len(explicit) == 1 else current.skin if current.mesh == mesh else ''
        if not skin and len(candidates) == 1:
            skin = candidates[0]
        return self._set(CharacterContext(identity(root), identity(mesh) if mesh else '',
            identity(skin) if skin else '', asset_for(root) or (current.asset if current.root == root else '')))

    def set_mesh(self, mesh):
        current = self.snapshot()
        mesh = transform(mesh) if mesh else ''
        if mesh and (not is_mesh(mesh) or not belongs(mesh, current.root)):
            raise ValueError('The mesh must belong to the active character.')
        candidates = skins(mesh)
        skin = candidates[0] if len(candidates) == 1 else ''
        return self._set(CharacterContext(current.root_uuid, identity(mesh) if mesh else '',
                                          identity(skin) if skin else '', current.asset))

    def set_skin(self, skin):
        current = self.snapshot()
        if skin and skin not in skins(current.mesh):
            raise ValueError('The skinCluster must deform the active mesh.')
        return self._set(CharacterContext(current.root_uuid, current.mesh_uuid,
                                          identity(skin) if skin else '', current.asset))


if '_SERVICE' not in globals():
    _SERVICE = ContextService()


def service():
    return _SERVICE
