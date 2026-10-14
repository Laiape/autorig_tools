"""Real Maya role resolution across different rigs, rename, namespace and reopen."""
import os, sys, tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_roles as r
    cmds.undoInfo(state=True)
    roots = [cmds.createNode('transform', name=n) for n in ('Biped', 'Quadruped')]
    a = cmds.createNode('transform', name='L_shoulderFk_CTL', parent=roots[0])
    b = cmds.createNode('transform', name='frontLeftBend', parent=roots[1])
    assert len(r.discover(roots[0])['added']) == 1
    identity = r.bind(roots[1], b, 'arm.upper.fk', 'L', 'arm')
    assert r.counterpart(a, roots[1]) == r.path(b)
    a = cmds.rename(a, 'arbitraryAnimatorName')
    assert r.resolve(roots[0], binding_key=identity) == r.path(a)
    snapshot = r.snapshot(roots[0])
    cmds.namespace(add='shotA')
    a = cmds.rename(a, 'shotA:UpperBend')
    assert r.alias_node(roots[0], 'L_shoulderFk_CTL') == r.path(a)
    other = cmds.createNode('transform', parent=roots[0])
    try:
        r.bind(roots[0], other, 'arm.upper.fk', 'L', 'arm')
        raise AssertionError('Duplicate role allowed')
    except ValueError:
        pass
    try:
        r.bind(roots[0], b, 'body.head')
        raise AssertionError('Cross-character binding allowed')
    except ValueError:
        pass
    assert r.restore(roots[1], snapshot, {identity: b}) == 1
    r.bind(roots[0], other, 'body.head', module='neck')
    assert r.resolve(roots[0], 'body.head', module='neck') == r.path(other)
    cmds.undo()
    assert not any(x['node'] == r.path(other) for x in r.bindings(roots[0]))
    with tempfile.TemporaryDirectory() as tmp:
        scene = str(Path(tmp) / 'roles.ma')
        cmds.file(rename=scene); cmds.file(save=True, type='mayaAscii')
        cmds.file(scene, open=True, force=True)
        assert r.resolve(roots[0], binding_key=identity) == r.path(a)
        assert r.root_for(a) == r.path(roots[0])
    print('PASS rig roles: different naming, character scope, namespace, rename, explicit transfer, duplicate guard, undo and reopen')
finally:
    maya.standalone.uninitialize()
