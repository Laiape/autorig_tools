"""Inspect native Bifrost array operators in an isolated trial session."""
import os
from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles as bw

if os.getpid() != TRIAL_ARGUMENTS['expected_pid']:
    raise RuntimeError('This script requires its explicitly selected trial process.')
cmds.file(new=True, force=True)
cmds.loadPlugin('bifrostGraph', quiet=True)
graph = cmds.createNode('bifrostGraphShape', name='ArrayTrialGraphShape')
builder = bw._Graph(graph)
result = {}
for kind in ('set_in_array', 'get_from_array'):
    try:
        node = builder.node('Core::Array', kind, kind)
        result[kind] = cmds.vnnNode(graph, node, listPorts=True)
    except Exception as exc:
        result[kind] = {'error': str(exc)}
result['gpu'] = cmds.ogs(query=True, deviceInformation=True)
result['viewports'] = {p: [cmds.control(p, query=True, width=True),
                         cmds.control(p, query=True, height=True)]
                       for p in cmds.getPanel(type='modelPanel')}
