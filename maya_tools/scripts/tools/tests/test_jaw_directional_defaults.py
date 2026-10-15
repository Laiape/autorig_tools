"""Native signed corner corrections: default-on gains, neutral rest and C1 gates."""
import json
import os

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
import numpy as np
from fixtures.jaw_scene import build


def matrices():
    return np.array([cmds.xform(n, q=True, ws=True, matrix=True) for n in NODES])


def fractions(value):
    for side in ('L', 'R'):
        scale = cmds.getAttr(side + '_lipSignedX_MUL.input[1]')
        cmds.setAttr(side + '_lipCorner_CTL.tx', value / scale)


def fields():
    return np.array([cmds.getAttr(side + '_lipNarrow_MUL.output') for side in ('L', 'R')] +
                    [cmds.getAttr(side + '_upperLipAutoWideAmount_MUL.output') for side in ('L', 'R')])


try:
    build()
    NODES = sorted(cmds.ls('*Lip*_JNT', type='joint') +
                   cmds.ls('*Lip*_GRP', '*lipCorner_GRP', '*lipCorner_OFF', type='transform'))
    assert NODES
    for side in ('L', 'R'):
        for attr in ('autoNarrow', 'autoWide'):
            assert cmds.getAttr(side + '_lipCorner_CTL.' + attr) == 1
            assert cmds.attributeQuery(attr, node=side + '_lipCorner_CTL', listDefault=True) == [1.]
    rest_error = 0.
    for angle in (0, 20, 30):
        cmds.setAttr('C_jaw_CTL.rx', angle)
        neutral = matrices()
        for gain in (0, .5, 1):
            for side in ('L', 'R'):
                for attr in ('autoNarrow', 'autoWide'):
                    cmds.setAttr(side + '_lipCorner_CTL.' + attr, gain)
            error = float(np.abs(matrices() - neutral).max())
            rest_error = max(rest_error, error)
            assert error < 1e-7, (angle, gain, error)
        assert np.all(fields() == 0)
        for side in ('L', 'R'):
            for axis in ('ty', 'tz'):
                for value in (-1, 1):
                    cmds.setAttr(side + '_lipCorner_CTL.' + axis, value)
                    assert np.all(fields() == 0), (angle, side, axis, value)
                cmds.setAttr(side + '_lipCorner_CTL.' + axis, 0)
        for fraction in (-.25, .25):
            fractions(fraction)
            narrow_l, narrow_r, wide_l, wide_r = fields()
            if fraction > 0:
                assert narrow_l > 0 and narrow_r > 0
                assert wide_l == wide_r == 0
            else:
                assert narrow_l == narrow_r == 0
                assert wide_l > 0 and wide_r > 0
            assert np.isfinite(matrices()).all()
        fractions(0)
    # Corrective value and derivative are continuous at neutral and saturation.
    epsilon = .001
    slope_errors = []
    for boundary in (-1, 0, 1):
        samples = []
        for fraction in (boundary-epsilon, boundary, boundary+epsilon):
            fractions(fraction)
            samples.append(fields())
        error = float(np.abs((samples[2]-samples[1])/epsilon -
                             (samples[1]-samples[0])/epsilon).max())
        slope_errors.append(error)
        assert error < .004, (boundary, error)
    sweep = []
    for fraction in np.linspace(-1, 1, 81):
        fractions(float(fraction))
        sweep.append(fields())
    sweep = np.array(sweep)
    assert np.all(np.diff(sweep[:, :2], axis=0) >= -1e-7)
    assert np.all(np.diff(sweep[:, 2:], axis=0) <= 1e-7)
    for fraction, expected in zip(np.linspace(1, -1, 81), reversed(sweep)):
        fractions(float(fraction))
        assert np.allclose(fields(), expected, atol=1e-7, rtol=0)
    fractions(0)
    print('PASS signed defaults: unchanged rest, Narrow X+, Wide X-, zero Y/Z activation, smooth gates and retracing')
    print(json.dumps({'neutral_gain_matrix_error': rest_error,
                      'boundary_slope_errors': slope_errors, 'sweep_samples': len(sweep)}), flush=True)
finally:
    maya.standalone.uninitialize()
