"""Native custom-leg regression: unreachable controls must not elongate the foot."""
import math
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('MAYA_SKIP_USERSETUP_PY', '1')
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import maya.standalone
from maya import cmds
from test_ik_fk_settings_match import check_module_inverse


def position(node):
    return cmds.xform(node, q=True, ws=True, t=True)


def check_lengths(side):
    ankle, ball, toe = [side + '_leg' + part + 'Skinning_JNT'
                        for part in ('Ankle', 'Ball', 'Toe')]
    for start, end, control in ((ankle, ball, 'ballIk'), (ball, toe, 'toeIk')):
        expected = (cmds.getAttr(side + '_' + control + 'SingleChain_DBT.distance') *
                    cmds.getAttr('C_masterwalk_CTL.globalScale'))
        actual = math.dist(position(start), position(end))
        assert abs(actual - expected) < 2e-4, (side, start, end, actual, expected)


def run():
    maya.standalone.initialize(name='python')
    try:
        cmds.loadPlugin('matrixNodes', quiet=True)
        cmds.loadPlugin('lookdevKit', quiet=True)
        for side, sign in (('L', 1), ('R', -1)):
            rig = check_module_inverse('leg_module_custom.py', side, foot_skinning=True)
            ctl = rig.ik_controllers[0]
            cmds.setAttr(rig.settings_ctl + '.Ik_Fk', 0)
            for c in [rig.root_ik_ctl, *rig.ik_controllers]:
                for channel in ('translate', 'rotate'):
                    for axis in 'XYZ':
                        plug = c + '.' + channel + axis
                        if cmds.getAttr(plug, settable=True):
                            cmds.setAttr(plug, 0)
            for attr in ('upperLengthMult', 'lowerLengthMult'):
                cmds.setAttr(ctl + '.' + attr, 1)
            for mode in ('off', 'serial', 'parallel'):
                cmds.evaluationManager(mode=mode)
                for scale in (1, 2):
                    cmds.setAttr(rig.masterwalk_ctl + '.globalScale', scale)
                    for distance in (0, 3, 30):
                        cmds.setAttr(ctl + '.translateX', sign * distance)
                        for stretch, soft, roll in ((0, 0, 0), (1, 0, 0),
                                                    (0, .5, 0), (0, 0, 30), (0, 0, 70)):
                            for attr, value in (('Stretch', stretch), ('Soft', soft), ('Roll', roll)):
                                cmds.setAttr(ctl + '.' + attr, value)
                            check_lengths(side)
            with tempfile.TemporaryDirectory() as folder:
                path = str(Path(folder) / 'foot_reach.mb')
                cmds.file(rename=path)
                cmds.file(save=True, type='mayaBinary', force=True)
                cmds.file(path, open=True, force=True)
                check_lengths(side)
            assert not (cmds.cycleCheck(all=True, list=True) or [])
            print('PASS foot reach:', side, 'DG/Serial/Parallel, scale, stretch, soft, roll, reopen', flush=True)
    finally:
        maya.standalone.uninitialize()


if __name__ == '__main__':
    run()
