"""Temporal deformation demand and original artist state survive failed trials."""
import os
from pathlib import Path
import sys
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import rig_benchmark as rb, pose_blendshapes as poses

try:
    control = cmds.createNode('transform', name='Test_CTL')
    curve = cmds.createNode('animCurveTL', name='OriginalCurve')
    cmds.connectAttr('time1.outTime', curve + '.input')
    cmds.setKeyframe(curve, time=1, value=2)
    cmds.connectAttr(curve + '.output', control + '.translateX')
    plug = control + '.translateX'
    original = cmds.connectionInfo(plug, sourceFromDestination=True)
    initial = {plug: cmds.getAttr(plug)}
    frame_before = cmds.currentTime(query=True)
    cases = [{'values': {plug: v}} for v in (0, 10, 0)]
    before = set(cmds.ls(type='animCurveTL'))
    try:
        with rb.evaluation_session(), poses._temporary_values(initial), rb.temporal_workload(cases, (1, 21)):
            cmds.currentTime(1); assert abs(cmds.getAttr(plug)) < 1e-6
            cmds.currentTime(11); assert abs(cmds.getAttr(plug) - 10) < 1e-6
            cmds.currentTime(21); assert abs(cmds.getAttr(plug)) < 1e-6
            raise RuntimeError('Deliberate trial failure')
    except RuntimeError:
        pass
    assert cmds.connectionInfo(plug, sourceFromDestination=True) == original
    assert set(cmds.ls(type='animCurveTL')) == before
    assert cmds.currentTime(query=True) == frame_before
    metric = rb.statistics_ms(list(range(1, 21)))
    assert metric['median_ms'] == 10.5 and metric['p95_ms'] == 19
    try:
        with rb.temporal_workload([cases[0], cases[0]], (1, 21)):
            raise AssertionError('Static workload accepted')
    except ValueError:
        pass
    print('PASS temporal protocol: actual time demand, original curves, failure cleanup, nearest-rank p95 and static guard', flush=True)
finally:
    maya.standalone.uninitialize()
