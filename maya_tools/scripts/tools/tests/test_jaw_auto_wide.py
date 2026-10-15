"""Run with mayapy: native forward compensation, independence and safe serialization."""
import json
import os
from pathlib import Path
import tempfile
import time

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from fixtures.jaw_scene import build

GAIN = 'C_jaw_CTL.autoWide'
DEPTH = 'C_jaw_CTL.autoWideDepth'
PARTS = ('upper', 'lower')


def joints(part):
    return [('R_' if i < 12 else 'C_' if i == 12 else 'L_') + part +
            'Lip%02d_JNT' % (i if i < 12 else 0 if i == 12 else 24-i) for i in range(25)]


def positions(part):
    return np.array([cmds.xform(j, q=True, ws=True, t=True) for j in joints(part)])


def snapshot():
    return {part: positions(part) for part in PARTS}


def compensation():
    cmds.setAttr(GAIN, 0)
    before = snapshot()
    cmds.setAttr(GAIN, 1)
    after = snapshot()
    return {part: after[part] - before[part] for part in PARTS}


def inward(side, value):
    ctl = side + '_lipCorner_CTL'
    coefficients = np.array(cmds.getAttr(side + '_lipOutFrac_VPR.input2')[0])
    delta = -value * coefficients / np.dot(coefficients, coefficients)
    cmds.setAttr(ctl + '.translate', *delta)


def check_frames():
    for part in PARTS:
        for j in joints(part):
            matrix = np.array(cmds.xform(j, q=True, ws=True, matrix=True)).reshape(4, 4)
            assert np.isfinite(matrix).all(), j
            assert np.allclose(matrix[:3, :3] @ matrix[:3, :3].T, np.eye(3), atol=1e-5, rtol=0), j
            other = j.replace('_JNT', 'NonRot_JNT')
            assert np.allclose(cmds.xform(j, q=True, ws=True, t=True),
                               cmds.xform(other, q=True, ws=True, t=True), atol=1e-5, rtol=0), j


try:
    started = time.perf_counter()
    obj = build()
    build_seconds = time.perf_counter() - started
    assert cmds.getAttr(GAIN) == 1 and cmds.getAttr(DEPTH) == .2
    assert cmds.getAttr(GAIN, keyable=True) and not cmds.getAttr(GAIN, lock=True)
    assert cmds.ls('C_jaw_NURB', type='transform') and not cmds.objExists('C_jawStatic_NURB')
    neutral = snapshot()
    # Jaw-only poses and outward movement must not activate a compression response.
    for angle in (0, 10, 20, 30):
        cmds.setAttr('C_jaw_CTL.rx', angle)
        for amount in (0, -.25):
            for side in ('L', 'R'):
                inward(side, amount)
            assert all(np.max(np.abs(v)) < 1e-7 for v in compensation().values())
    for side in ('L', 'R'):
        inward(side, 0)

    # Continuous activation, saturation and a smooth bilateral intersection.
    probe = 'C_lipAutoWideOutputupper12_CMX.inputTranslateZ'
    for boundary in (0, 1):
        values = []
        epsilon = .001
        for value in (boundary - epsilon, boundary, boundary + epsilon):
            for side in ('L', 'R'):
                inward(side, value)
            values.append(cmds.getAttr(probe))
        a, b, c = values
        assert abs((c-b)/epsilon - (b-a)/epsilon) < .01, (boundary, values)
    inward('R', .25)
    values = []
    for value in (.249, .25, .251):
        inward('L', value)
        values.append(cmds.getAttr(probe))
    a, b, c = values
    assert abs((c-b)/.001 - (b-a)/.001) < .01, values
    for side in ('L', 'R'):
        inward(side, 0)

    # A unilateral squeeze cannot push the center or the other half forwards.
    for side in ('L', 'R'):
        inward(side, .25)
        delta = compensation()
        own = slice(13, 24) if side == 'L' else slice(1, 12)
        other = slice(0, 13) if side == 'L' else slice(12, 25)
        for part in PARTS:
            assert np.max(delta[part][own, 2]) > .001, (side, part)
            assert np.max(np.abs(delta[part][other])) < 1e-7, (side, part)
            assert np.max(np.abs(delta[part][[0, 24]])) < 1e-7
        inward(side, 0)

    # Bilateral compression has its largest compensation at the center.
    minimum_spacing = float('inf')
    sweep = []
    cmds.setAttr('C_jaw_CTL.rx', 0)
    for value in np.linspace(0, .25, 26):
        for side in ('L', 'R'):
            inward(side, float(value))
        delta = compensation()
        assert np.allclose(delta['upper'], delta['lower'], atol=1e-6, rtol=0)
        for part in PARTS:
            z = delta[part][:, 2]
            assert np.all(np.diff(z[:13]) >= -1e-6) and np.all(np.diff(z[12:]) <= 1e-6)
            assert z.min() >= -1e-7
            p = positions(part)
            assert np.all(np.diff(p[:, 0]) > 0), (value, part, p[:, 0])
            minimum_spacing = min(minimum_spacing, float(np.linalg.norm(np.diff(p, axis=0), axis=1).min()))
        sweep.append(delta['upper'][12, 2])
    assert np.all(np.diff(sweep) >= -1e-7) and sweep[-1] > .01, sweep
    for value, expected in zip(np.linspace(.25, 0, 26), reversed(sweep)):
        for side in ('L', 'R'):
            inward(side, float(value))
        assert abs(compensation()['upper'][12, 2] - expected) < 1e-7

    # A half-intensity setting gives half the correction without shifting X/Y.
    for side in ('L', 'R'):
        cmds.setAttr(side + '_lipCorner_CTL.autoNarrow', 1)
    full = snapshot()
    cmds.setAttr(GAIN, 0)
    off = snapshot()
    cmds.setAttr(GAIN, .5)
    half = snapshot()
    for part in PARTS:
        assert np.allclose(half[part], .5 * (full[part] + off[part]), atol=1e-6, rtol=0)
    cmds.setAttr(GAIN, 1)
    for side in ('L', 'R'):
        cmds.setAttr(side + '_lipCorner_CTL.autoNarrow', 0)

    # Secondary compression is local to its lip and side, including mirrored axes.
    for part, other in (('upper', 'lower'), ('lower', 'upper')):
        for side in ('L', 'R'):
            ctl = side + '_' + part + 'Lip02_CTL'
            coefficients = np.array(cmds.getAttr(ctl[:-4] + 'AutoWideIn_VPR.input2')[0])
            rest = positions(other)
            cmds.setAttr(ctl + '.translate', *(coefficients * .2 / np.dot(coefficients, coefficients)))
            delta = compensation()
            own = slice(13, 24) if side == 'L' else slice(1, 12)
            assert np.max(delta[part][own, 2]) > .001, (part, side)
            assert np.allclose(positions(other), rest, atol=1e-6, rtol=0)
            assert np.max(np.abs(delta[other])) < 1e-7
            assert np.linalg.norm(positions(part)[12] - neutral[part][12]) < 1e-5
            cmds.setAttr(ctl + '.translate', 0, 0, 0)

    # Active correction composes with primary offsets, U, roll and sticky closure.
    for side in ('L', 'R'):
        cmds.setAttr(side + '_lipCorner_CTL.autoNarrow', 1)
    for angle in (0, 20, 30):
        cmds.setAttr('C_jaw_CTL.rx', angle)
        cmds.setAttr('C_jaw_CTL.stickyLips', 0)
        for part in PARTS:
            cmds.setAttr('C_' + part + 'Lip_CTL.Roll', 0)
        for part, other in (('upper', 'lower'), ('lower', 'upper')):
            rest = positions(other)
            for value in (-1, 1):
                cmds.setAttr('C_' + part + 'Lip_CTL.ty', value)
                assert np.allclose(positions(other), rest, atol=1e-6, rtol=0), (angle, part, value)
            cmds.setAttr('C_' + part + 'Lip_CTL.ty', 0)
        for roll in (-20, 20):
            cmds.setAttr('C_upperLip_CTL.Roll', roll)
            cmds.setAttr('C_lowerLip_CTL.Roll', roll)
            for sticky in (0, .5, 1):
                cmds.setAttr('C_jaw_CTL.stickyLips', sticky)
                check_frames()
                if sticky == 1:
                    assert np.allclose(positions('upper'), positions('lower'), atol=1e-5, rtol=0)
    cmds.setAttr('C_jaw_CTL.stickyLips', 0)
    for part in PARTS:
        cmds.setAttr('C_' + part + 'Lip_CTL.Roll', 0)
    before = snapshot()
    cmds.setAttr('C_mainMouth_CTL.translate', 1, .5, -.3)
    cmds.setAttr('C_mainMouth_CTL.rotate', 9, -14, 7)
    transform = np.array(cmds.getAttr('C_mainMouthDelta_MMX.matrixSum')).reshape(4, 4)
    for part in PARTS:
        expected = np.c_[before[part], np.ones(25)] @ transform
        assert np.allclose(positions(part), expected[:, :3], atol=1e-5, rtol=0)
    cmds.setAttr('C_mainMouth_CTL.translate', 0, 0, 0)
    cmds.setAttr('C_mainMouth_CTL.rotate', 0, 0, 0)

    # The corrective and all its input drivers must remain acyclic in DG/EM.
    cycles = cmds.cycleCheck(all=True, list=True) or []
    assert not cycles, cycles
    serial = snapshot()
    for mode in ('serial', 'parallel'):
        cmds.evaluationManager(mode=mode)
        cmds.dgdirty(allPlugs=True)
        assert all(np.allclose(positions(p), serial[p], atol=1e-5, rtol=0) for p in PARTS), mode
    cmds.evaluationManager(mode='off')
    with tempfile.TemporaryDirectory(prefix='jaw_wide_') as folder:
        path = Path(folder) / 'auto_wide.mb'
        cmds.file(rename=str(path))
        cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(new=True, force=True)
        cmds.file(str(path), open=True, force=True)
        assert all(np.allclose(positions(p), serial[p], atol=1e-6, rtol=0) for p in PARTS)
    print('PASS Auto Wide: smooth forward profile, unilateral/fine independence, gain, sticky, EM and reopen')
    print(json.dumps({'fixture_build_seconds': build_seconds, 'maximum_tested_center_push': sweep[-1],
                      'minimum_tested_joint_spacing': minimum_spacing, 'cycles': len(cycles)}), flush=True)
finally:
    maya.standalone.uninitialize()
