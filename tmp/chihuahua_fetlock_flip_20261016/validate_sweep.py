import json, math
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om

base = Path('C:/proyectos/auto-rig/tmp/chihuahua_fetlock_flip_20261016')
report = {'passed': False, 'range_cm': [0, 10], 'step_cm': .05, 'runs': []}
for mode in ('off', 'serial', 'parallel'):
    cmds.evaluationManager(mode=mode)
    for side in ('L', 'R'):
        for limb in ('frontLeg', 'backLeg'):
            prefix = side + '_' + limb
            plug = prefix + 'FetlockIk_CTL.ty'
            joints = cmds.ls(prefix + '*Skinning_JNT', type='joint')
            nodes = [j + '.worldMatrix[0]' for j in joints]
            nodes += [prefix + part + 'Aim_AMX.outputMatrix' for part in ('Fetlock', 'Pastern')]
            previous = None
            maxima = {n: [0., 0.] for n in nodes}
            original = cmds.getAttr(plug)
            try:
                for step in list(range(201)) + list(range(199, -1, -1)):
                    height = step * .05
                    cmds.setAttr(plug, height)
                    values = {n: om.MTransformationMatrix(om.MMatrix(cmds.getAttr(n))).rotation(asQuaternion=True) for n in nodes}
                    if previous:
                        for n, q in values.items():
                            a = previous[n]
                            dot = abs(q.x*a.x + q.y*a.y + q.z*a.z + q.w*a.w)
                            angle = math.degrees(2 * math.acos(min(1., dot)))
                            if angle > maxima[n][0]: maxima[n] = [angle, height]
                    previous = values
                assert max(v[0] for v in maxima.values()) < 5., (prefix, mode, maxima)
            finally:
                cmds.setAttr(plug, original)
            report['runs'].append({'mode': mode, 'limb': prefix, 'samples': 401, 'max_angle_degrees': max(v[0] for v in maxima.values()), 'per_node': maxima})
cmds.evaluationManager(mode='off')
report['cycles'] = cmds.cycleCheck(all=True, list=True) or []
assert not report['cycles'], report['cycles']
report['passed'] = True
(base / 'validated_sweep.json').write_text(json.dumps(report, indent=2))
result = {'passed': True, 'runs': len(report['runs']), 'samples': sum(r['samples'] for r in report['runs']), 'max_angle_degrees': max(r['max_angle_degrees'] for r in report['runs']), 'cycles': report['cycles']}
