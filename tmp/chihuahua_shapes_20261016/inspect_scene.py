import json, sys, os
from pathlib import Path
import maya.cmds as cmds
from maya_tools.scripts.utils import curve_tool, rig_manager
controls = cmds.ls('*_CTL', type='transform', long=True) or []
result = {'pid': os.getpid(), 'scene': cmds.file(q=True, sn=True), 'modified': cmds.file(q=True, modified=True), 'runtime': curve_tool.__file__, 'asset': rig_manager.get_character_name_from_build(), 'controls': {}, 'selection': cmds.ls(sl=True, long=True), 'panels': cmds.getPanel(type='modelPanel')}
for n in controls:
    shapes = cmds.listRelatives(n, shapes=True, noIntermediate=True, type='nurbsCurve', fullPath=True) or []
    result['controls'][n.rsplit('|',1)[-1]] = {'matrix': cmds.xform(n,q=True,ws=True,m=True), 'shapes': [{'name':s,'cvs':cmds.xform(s+'.cv[*]',q=True,ws=True,t=True)} for s in shapes]}
