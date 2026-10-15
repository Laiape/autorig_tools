"""Versioned work profiles and explicitly reviewed workflow steps."""
import json
from maya import cmds

OPTION = 'AutoRigToolFrameworkStateV2'
PROFILES = {'All tools': 'all', 'Rigging': 'RIGGING', 'Deformers': 'DEFORMERS', 'Review': 'ANIMATION'}
STEPS = (
    ('model', 'Model Check', 'model_checker', 'Inspect geometry and record the modeling review.'),
    ('guides', 'Guides', 'guides_import', 'Create or import guides; inspect placement and export them.'),
    ('build', 'Build', 'create_rig', 'Check saved asset inputs, then build in a fresh scene.'),
    ('skin', 'Skin', 'skinning', 'Choose the mesh and skinCluster; author and review weights.'),
    ('correctives', 'Correctives', 'pose_blendshapes', 'Capture poses, sculpt targets and review deformation.'),
    ('validate', 'Validate', 'pose_tester', 'Run the relevant Test Rig checks and inspect their actual reports.'),
    ('package', 'Rig Package', 'packages', 'Freeze inputs and run package validation before delivery.'),
)


def read():
    try:
        data = json.loads(cmds.optionVar(query=OPTION)) if cmds.optionVar(exists=OPTION) else {}
        if not isinstance(data, dict):
            return {}
        return data if data.get('version', 2) == 2 else {}
    except (ValueError, TypeError):
        return {}


def write(data):
    data = dict(data, version=2)
    cmds.optionVar(stringValue=(OPTION, json.dumps(data)))


def save_profile(name, view):
    if name not in PROFILES:
        raise ValueError('Unknown work profile.')
    data = read()
    profiles = data.get('profiles', {})
    if not isinstance(profiles, dict):
        profiles = {}
    profiles[name] = view
    data.update(profiles=profiles, active_profile=name)
    write(data)


def profile(name):
    profiles = read().get('profiles', {})
    value = profiles.get(name, {}) if isinstance(profiles, dict) else {}
    if not isinstance(value, dict):
        value = {}
    result = dict(scope=PROFILES.get(name, 'all'), query='', tab=0, selected='', expanded=None, editors={})
    result.update({key: value[key] for key in result if key in value})
    return result


def workflow(key):
    workflows = read().get('workflows', {})
    value = workflows.get(key, {}) if isinstance(workflows, dict) else {}
    if not isinstance(value, dict):
        return {}
    result = {}
    for step, entry in value.items():
        if step in {item[0] for item in STEPS} and isinstance(entry, dict):
            status = entry.get('status')
            note = entry.get('note', '')
            if status in ('pending', 'in_progress', 'reviewed', 'skipped') and isinstance(note, str):
                result[step] = {'status': status, 'note': note}
    return result


def set_step(key, step, status, note=''):
    if not key:
        raise ValueError('Load an active character or asset first.')
    if step not in {item[0] for item in STEPS} or status not in ('in_progress', 'reviewed', 'skipped', 'pending'):
        raise ValueError('Unknown workflow step or state.')
    if status == 'skipped' and not note.strip():
        raise ValueError('Explain why this workflow step is skipped.')
    data = read()
    workflows = data.get('workflows', {})
    if not isinstance(workflows, dict):
        workflows = {}
    steps = dict(workflow(key))
    steps[step] = {'status': status, 'note': note.strip()}
    workflows[key] = steps
    data['workflows'] = workflows
    write(data)
