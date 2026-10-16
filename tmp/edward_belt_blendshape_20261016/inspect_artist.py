import os, sys
from maya import cmds
assert os.getpid() == 23404, 'Unexpected Maya session'
wraps = {}
for node in cmds.ls(type='proximityWrap') or []:
    wraps[node] = {'geometry': cmds.deformer(node, q=True, geometry=True),
                   'drivers': cmds.listConnections(node+'.drivers', s=True, d=False, p=True) or []}
result = {'pid': os.getpid(), 'scene': cmds.file(q=True, sn=True),
          'modified': cmds.file(q=True, modified=True), 'selection': cmds.ls(sl=True, long=True),
          'frame': cmds.currentTime(q=True), 'evaluation': cmds.evaluationManager(q=True,mode=True),
          'wraps': wraps, 'sys_path': sys.path,
          'belts': cmds.ls('*cintur*', long=True),
          'python_port': cmds.commandPort('127.0.0.1:7002',q=True)}
