"""Lightweight scene evaluation contract; no geometry work or frame callbacks."""
import time
from maya import cmds

ATTRIBUTE = 'autorigEvaluationProfile'
PROFILE = 'autorig:scene-evaluation:v1:posing_cpu'
_CALLBACKS = globals().get('_CALLBACKS', [])


def capture():
    available = set(cmds.evaluator(query=True) or [])
    return {
        'mode': cmds.evaluationManager(query=True, mode=True)[0],
        'evaluators': {name: bool(cmds.evaluator(name=name, query=True, enable=True))
                       for name in ('cache', 'deformer') if name in available},
    }


def restore(state):
    """Restore the caller's runtime flags after a failed build or trial."""
    available = set(cmds.evaluator(query=True) or [])
    if 'cache' in available:
        cmds.evaluator(name='cache', enable=False)
    for name, enabled in state['evaluators'].items():
        if name != 'cache' and name in available:
            cmds.evaluator(name=name, enable=enabled)
    cmds.evaluationManager(mode=state['mode'])
    if 'cache' in state['evaluators'] and 'cache' in available:
        cmds.evaluator(name='cache', enable=state['evaluators']['cache'])


def suspend_for_build():
    """Retain lazy DG construction; never fill caches while building nodes."""
    state = capture()
    try:
        for name in state['evaluators']:
            cmds.evaluator(name=name, enable=False)
        cmds.evaluationManager(mode='off')
    except Exception:
        restore(state)
        raise
    return state


def apply():
    """Use the conservative posing profile, once at a workflow boundary."""
    started = time.perf_counter()
    previous = capture()
    try:
        for name, enabled in previous['evaluators'].items():
            if enabled:
                cmds.evaluator(name=name, enable=False)
        if previous['mode'] != 'parallel':
            cmds.evaluationManager(mode='parallel')
        actual = capture()
        if actual['mode'] != 'parallel' or any(actual['evaluators'].values()):
            raise RuntimeError('The conservative scene evaluation profile was not applied.')
    except Exception:
        restore(previous)
        raise
    return dict(actual, profile=PROFILE, seconds=time.perf_counter()-started)


def register(root):
    """Persist intent as data on the owned root, without executable scene code."""
    matches = cmds.ls(root, long=True, type='transform') or []
    if len(matches) != 1:
        raise ValueError('Choose one owned character root for scene evaluation.')
    root = matches[0]
    plug = root + '.' + ATTRIBUTE
    if cmds.attributeQuery(ATTRIBUTE, node=root, exists=True):
        if cmds.getAttr(plug) != PROFILE:
            raise ValueError('The character already has a different evaluation contract.')
    else:
        cmds.addAttr(root, longName=ATTRIBUTE, dataType='string', hidden=True)
        cmds.setAttr(plug, PROFILE, type='string')
        cmds.setAttr(plug, lock=True)
    return plug


def apply_for_scene():
    """Only scenes explicitly marked by this tool opt into automatic setup."""
    from maya_tools.scripts.utils import build_timing
    if build_timing.active() is not None:
        return {'applied': False, 'reason': 'construction_in_progress'}
    roots = cmds.ls('*.' + ATTRIBUTE, objectsOnly=True, long=True, recursive=True) or []
    owned = [root for root in roots if cmds.getAttr(root + '.' + ATTRIBUTE) == PROFILE]
    if not owned:
        return {'applied': False, 'reason': 'no_owned_scene_profile'}
    return dict(apply(), applied=True, roots=owned)


def _after_open(*_):
    try:
        apply_for_scene()
    except Exception as error:
        cmds.warning('[AutoRig evaluation] Scene profile could not be applied: ' + str(error))


def install_callbacks(apply_current=True):
    """Install one after-open hook, safe across repeated UI setup and reload."""
    from maya.api import OpenMaya as om
    if not _CALLBACKS:
        _CALLBACKS.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, _after_open))
    if apply_current:
        return apply_for_scene()
    return {'installed': True}


def remove_callbacks():
    """Explicit teardown for tests and module unloading."""
    from maya.api import OpenMaya as om
    while _CALLBACKS:
        om.MMessage.removeCallback(_CALLBACKS.pop())
