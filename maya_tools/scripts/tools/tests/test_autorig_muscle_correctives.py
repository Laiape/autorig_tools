"""Real Maya evaluation and scene roundtrip for automatic muscle correctives."""
import ast
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault('MAYA_SKIP_USERSETUP_PY', '1')
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om


def setup_function(filename):
    path = Path(__file__).resolve().parents[2] / 'biped/autorig' / filename
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'corrective_setup')
    from maya_tools.scripts.utils import correctives
    scope = {'cmds': cmds, 'om': om, 'correctives': correctives}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
    return scope['corrective_setup']


def run():
    maya.standalone.initialize(name='python')
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        cmds.file(new=True, force=True)
        expected = []
        samples = []
        for side in 'LR':
            for limb, filename, axis, parts in (
                    ('arm', 'arm_module.py', 'Y', ('biceps', 'triceps')),
                    ('leg', 'leg_module.py', 'Z', ('thighFront', 'thighBack'))):
                upper = cmds.createNode('joint', name=side + '_' + limb + 'Upper00_JNT')
                lower = cmds.createNode('joint', name=side + '_' + limb + 'Lower00_JNT', parent=upper)
                cmds.setAttr(lower + '.tx', 10)
                base = cmds.createNode('joint', name=side + '_' + limb + 'Upper02_JNT', parent=upper)
                cmds.setAttr(base + '.tx', 5)
                host = cmds.createNode('transform', name=side + '_' + limb + 'UpperMainBendy_CTL')
                setup_function(filename)(SimpleNamespace(side=side, settings_ctl=host))
                joints = [side + '_' + part + 'Corrective_JNT' for part in parts]
                expected += joints
                rest = {j: cmds.getAttr(j + '.translate')[0] for j in joints}
                states = []
                for angle in (-100, 0, 100):
                    cmds.setAttr(lower + '.rotate' + axis, angle)
                    states.append({j: cmds.getAttr(j + '.translate')[0] for j in joints})
                for j in joints:
                    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(states[1][j], rest[j]))
                    assert max(sum((a - b) ** 2 for a, b in zip(state[j], rest[j])) for state in states) > .1, j
                # The two muscles respond to opposite bend directions.
                for state in (states[0], states[2]):
                    moved = [sum((a - b) ** 2 for a, b in zip(state[j], rest[j])) > 1e-6 for j in joints]
                    assert sum(moved) == 1, (limb, side, state)
                cmds.setAttr(lower + '.rotate' + axis, 0)
                samples.append((lower, axis, joints, states))
        assert sorted(cmds.ls('*Corrective_JNT', type='joint')) == sorted(expected)
        assert not cmds.ls('*elbowRing*', '*shoulderUp*', '*hipFlex*')
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'muscle_correctives.ma')
            cmds.file(rename=path); cmds.file(save=True, type='mayaAscii', force=True)
            cmds.file(path, open=True, force=True)
            for lower, axis, joints, states in samples:
                for angle, state in zip((-100, 0, 100), states):
                    cmds.setAttr(lower + '.rotate' + axis, angle)
                    for j in joints:
                        actual = cmds.getAttr(j + '.translate')[0]
                        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(actual, state[j])), j
                cmds.setAttr(lower + '.rotate' + axis, 0)
        print('PASS: eight muscle joints, opposite bend response, neutral and scene roundtrip')
    finally:
        maya.standalone.uninitialize()


if __name__ == '__main__':
    run()
