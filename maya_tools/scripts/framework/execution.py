"""Read-only preflight, explicit outcomes and a local operation journal."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import time
import traceback
import uuid
import weakref

from maya import cmds
from maya_tools.scripts.framework import context, registry


class Cancelled(Exception):
    """An action explicitly cancelled before completing."""


@dataclass
class Preflight:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ready(self):
        return not self.errors


def plugin_available(name):
    try:
        if cmds.pluginInfo(name, query=True, registered=True):
            return True
    except RuntimeError:
        pass
    suffix = '.mll' if os.name == 'nt' else '.bundle' if sys_platform() == 'darwin' else '.so'
    return any((Path(folder) / (name + suffix)).is_file()
               for folder in os.environ.get('MAYA_PLUG_IN_PATH', '').split(os.pathsep) if folder)


def sys_platform():
    import sys
    return sys.platform


def latest_input(asset_path, category, suffixes, strict=False):
    candidates = [path for path in (asset_path / category).glob('*') if path.is_file()
                  and (strict or path.suffix.lower() in suffixes)]
    # Match the legacy loader, which uses the most recently modified file.
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def preflight(tool_id, active=None):
    tool = registry.BY_ID[tool_id]
    active = active or context.service().snapshot()
    result = Preflight()
    if tool.unavailable:
        result.errors.append(tool.unavailable)
    if tool.replaces_scene and context.sculpt_active():
        result.errors.append('Finish the live sculpt before replacing the scene.')
    selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
    transforms = []
    for value in selected:
        try:
            transforms.append(context.transform(value))
        except ValueError:
            pass
    selected_meshes = list(dict.fromkeys(value for value in transforms if context.is_mesh(value)))
    selected_joints = [value for value in transforms if cmds.nodeType(value) == 'joint']
    for requirement in tool.requirements:
        if requirement == 'asset' and not active.asset_path:
            result.errors.append('Choose the active asset in Character context.')
        elif requirement == 'root' and not active.root:
            result.errors.append('Load the active character from selection.')
        elif requirement == 'mesh' and not (active.mesh or selected_meshes):
            result.errors.append('Choose an active polygon mesh or select one in Maya.')
        elif requirement == 'skin' and not context.skins(active.mesh or (selected_meshes[0] if len(selected_meshes) == 1 else '')):
            result.errors.append('The target mesh needs a skinCluster.')
        elif requirement == 'two_meshes' and len(selected_meshes) != 2:
            result.errors.append('Select exactly two meshes: source first, then destination.')
        elif requirement == 'proxy' and (len(selected_meshes) != 2 or len(selected_joints) != 1):
            result.errors.append('Select proxy, high-resolution mesh and one skeleton root, in that order.')
        elif requirement == 'mesh_joints' and (len(selected_meshes) != 1 or not selected_joints):
            result.errors.append('Select one mesh and its corrective joints.')
        elif requirement == 'guide' and (len(transforms) != 1 or not (
                cmds.nodeType(transforms[0]) == 'joint' or cmds.listRelatives(transforms[0], shapes=True, type='locator'))):
            result.errors.append('Select one root guide joint or locator.')
        elif requirement == 'scene_guides' and not cmds.objExists('C_guides_GRP'):
            result.errors.append('Import or create the C_guides_GRP guide setup first.')
        elif requirement == 'controllers' and not cmds.ls('*_CTL', '*:*_CTL', type='transform'):
            result.errors.append('The scene has no rig controllers to export or mirror.')
        elif requirement == 'rig' and active.root and not any(
                node.rsplit(':', 1)[-1].endswith('_CTL') for node in
                cmds.listRelatives(active.root, allDescendents=True, fullPath=True, type='transform') or []):
            result.errors.append('The active character has no rig controls. Build or choose a rig first.')
        elif requirement.startswith('plugin:') and not plugin_available(requirement.split(':', 1)[1]):
            result.errors.append('Install the required Maya plug-in: ' + requirement.split(':', 1)[1])
        elif requirement == 'build_inputs' and active.asset_path:
            for category, suffixes in (('models', ('.ma', '.mb')), ('guides', ('.guides',)), ('build', ('.build', '.json'))):
                path = latest_input(active.asset_path, category, suffixes, strict=True)
                if path is None:
                    result.errors.append('The active asset has no saved ' + category + ' input.')
                elif path.suffix.lower() not in suffixes:
                    result.errors.append('The newest ' + category + ' input has an unsupported type: ' + path.name)
                elif category != 'models':
                    try:
                        data = json.loads(path.read_text(encoding='utf-8'))
                        if not isinstance(data, (dict, list)) or not data:
                            raise ValueError('empty input')
                    except (OSError, ValueError):
                        result.errors.append('Invalid saved ' + category + ' input: ' + path.name)
        elif requirement == 'saved_skin' and active.asset_path:
            if latest_input(active.asset_path, 'skin_clusters', ('.skc',)) is None:
                result.errors.append('The active asset has no saved .skc file.')
    if tool.kind != 'editor' and active.root:
        outside = [value for value in transforms if not context.belongs(value, active.root)]
        if outside and not tool.replaces_scene:
            result.errors.append('Selection is outside the active character. Clear the shared context for a cross-character action.')
    if tool.kind == 'editor' and not active.root:
        result.warnings.append('No shared character loaded; this editor will use its own selection controls.')
    return result


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.rows = []
        self.listeners = []
        self.io_error = ''
        try:
            for line in self.path.read_text(encoding='utf-8').splitlines()[-200:]:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and 'status' in item:
                        self.rows.append(item)
                except ValueError:
                    pass
        except OSError:
            pass

    def subscribe(self, callback):
        reference = weakref.WeakMethod(callback)
        self.listeners.append(reference)
        return reference

    def unsubscribe(self, reference):
        if reference in self.listeners:
            self.listeners.remove(reference)

    def append(self, row):
        self.rows = (self.rows + [row])[-200:]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=True) + '\n')
            self.io_error = ''
        except OSError as exc:
            self.io_error = str(exc)
        for reference in list(self.listeners):
            callback = reference()
            if callback is None:
                self.unsubscribe(reference)
            else:
                try:
                    callback()
                except RuntimeError:
                    self.unsubscribe(reference)


if '_JOURNAL' not in globals():
    _JOURNAL = None
if '_RUNNING' not in globals():
    _RUNNING = False


def journal():
    global _JOURNAL
    if _JOURNAL is None:
        _JOURNAL = Journal(Path(cmds.internalVar(userAppDir=True)) / 'autorig' / 'framework' / 'operations.jsonl')
    return _JOURNAL


def _files(value):
    if isinstance(value, (str, Path)):
        try:
            return [str(value)] if Path(value).is_file() else []
        except OSError:
            return []
    if isinstance(value, (tuple, list)):
        return list(dict.fromkeys(path for item in value for path in _files(item)))
    if isinstance(value, dict):
        return list(dict.fromkeys(path for key in ('path', 'files', 'output', 'report') for path in _files(value.get(key))))
    return []


def run(tool_id, confirm=None, dispatch=None):
    """Only explicit results imply completion; opening an editor is not QA."""
    global _RUNNING
    tool = registry.BY_ID[tool_id]
    owns_run = False
    active = context.service().snapshot()
    start = time.perf_counter()
    row = dict(id=str(uuid.uuid4()), tool_id=tool_id, tool=tool.label,
               timestamp=datetime.now(timezone.utc).isoformat(), scene=cmds.file(query=True, sceneName=True),
               context=active.summary(), status='blocked', message='', warnings=[], files=[], traceback='')
    try:
        if _RUNNING:
            row['message'] = 'Another framework action is still running.'
            return row
        check = preflight(tool_id, active)
        row['warnings'] = check.warnings
        if not check.ready:
            row['message'] = ' '.join(check.errors)
            return row
        _RUNNING = True
        owns_run = True
        if tool.replaces_scene and (confirm is None or not confirm(tool)):
            raise Cancelled('Build cancelled. Current scene preserved.')
        # Preflight does not mutate selection, scene or plug-in loading.
        value = dispatch() if dispatch else registry.invoke(tool_id)
        if value is False:
            raise Cancelled('Tool cancelled.')
        if tool.kind == 'editor':
            row.update(status='opened', message='Opened: ' + tool.label)
        elif value is None:
            row.update(status='returned', message='Returned: {}. Check the tool output for its result.'.format(tool.label))
        else:
            row.update(status='completed', message='Completed: ' + tool.label)
        row['files'] = _files(value)
    except Cancelled as exc:
        row.update(status='cancelled', message=str(exc))
    except Exception as exc:
        row.update(status='failed', message=str(exc), traceback=traceback.format_exc())
    finally:
        if owns_run:
            _RUNNING = False
        row['duration_ms'] = round((time.perf_counter() - start) * 1000, 2)
        journal().append(row)
    return row
