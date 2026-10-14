"""Run with mayapy: U correction independence and a smooth, monotone response.

Exercise production math with matrix inputs; no rig modules or asset cache.
"""
import ast
import os
from pathlib import Path

os.environ.setdefault('MAYA_SKIP_USERSETUP_PY', '1')
import maya.standalone
from maya import cmds


def run():
    maya.standalone.initialize(name='python')
    try:
        source = Path(__file__).resolve().parents[2] / 'biped/autorig/jaw_module_nurbs.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name == '_round_raised_lip_frames')
        scope = {'cmds': cmds}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
        cmds.file(new=True, force=True)
        cmds.evaluationManager(mode='off')
        drags = {side: cmds.createNode('composeMatrix', name=side + '_corner') for side in ('L', 'R')}
        # composeMatrix's inputTranslate is a compound vector with x/y children.
        drag_plugs = {side: node + '.inputTranslate' for side, node in drags.items()}
        frames, inputs = {}, {}
        for part in ('upper', 'lower'):
            nodes = [cmds.createNode('composeMatrix', name=part + str(i)) for i in range(25)]
            inputs[part] = nodes
            for i, node in enumerate(nodes):
                cmds.setAttr(node + '.inputTranslate', (i - 12) * 5 / 12, 1 if part == 'upper' else -1, 0)
            frames[part] = [node + '.outputMatrix' for node in nodes]
        # The production corner plugs end in x/y, unlike composeMatrix children.
        vectors = {}
        for side, node in drags.items():
            vector = cmds.createNode('plusMinusAverage', name=side + '_drag')
            cmds.connectAttr(drag_plugs[side], vector + '.input3D[0]')
            vectors[side] = vector + '.output3D'
        output, _ = scope['_round_raised_lip_frames']('testU', frames, vectors, 5)

        def y_positions(part):
            return [cmds.getAttr(plug)[13] for plug in output[part]]

        # Raised, widened corners formerly coupled the two primary controls.
        for side in drags:
            cmds.setAttr(drags[side] + '.inputTranslate', 2 if side == 'L' else -2, 2, 0)
        for part, other in (('upper', 'lower'), ('lower', 'upper')):
            baseline = y_positions(other)
            own_before = y_positions(part)[8]
            rest_y = cmds.getAttr(inputs[part][8] + '.inputTranslateY')
            for value in (-3, 3):
                cmds.setAttr(inputs[part][8] + '.inputTranslateY', value)
                assert y_positions(other) == baseline
                assert abs(y_positions(part)[8] - own_before - (value - rest_y)) < 1e-8
            cmds.setAttr(inputs[part][8] + '.inputTranslateY', 1 if part == 'upper' else -1)
        for node in drags.values():
            cmds.setAttr(node + '.inputTranslate', 0, 0, 0)

        # Include the ordinary corner falloff, then verify the combined motion.
        for part in inputs:
            for i, node in enumerate(inputs[part]):
                side = 'R' if i <= 12 else 'L'
                t = min(i, 24 - i) / 12
                weight = 1 - t * t * (3 - 2 * t)
                scale = cmds.createNode('multiplyDivide')
                cmds.connectAttr(drags[side] + '.inputTranslateY', scale + '.input1X')
                cmds.setAttr(scale + '.input2X', weight)
                cmds.connectAttr(scale + '.outputX', node + '.inputTranslateY', force=True)
        for side in drags:
            for x in (-1, 0, 7):
                cmds.setAttr(drags[side] + '.inputTranslateX', x if side == 'L' else -x)
                previous = None
                samples = []
                for step in range(401):
                    cmds.setAttr(drags[side] + '.inputTranslateY', -1 + step * .01)
                    current = y_positions('upper')
                    if previous is not None:
                        assert all(b >= a - 1e-8 for a, b in zip(previous, current)), (side, x, step)
                    previous = current
                    samples.append(current)
                for step in reversed(range(401)):
                    cmds.setAttr(drags[side] + '.inputTranslateY', -1 + step * .01)
                    assert y_positions('upper') == samples[step]
                for boundary in (0, .6):
                    epsilon = 1e-4
                    values = []
                    for y in (boundary - epsilon, boundary, boundary + epsilon):
                        cmds.setAttr(drags[side] + '.inputTranslateY', y)
                        values.append(y_positions('upper'))
                    assert max(abs((c-b)/epsilon - (b-a)/epsilon)
                               for a, b, c in zip(*values)) < .001
                cmds.setAttr(drags[side] + '.inputTranslate', 0, 0, 0)
        print('PASS: independent lips, monotone raise/lower, continuous slopes and identical retrace')
    finally:
        maya.standalone.uninitialize()


if __name__ == '__main__':
    run()
