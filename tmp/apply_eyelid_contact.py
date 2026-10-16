from importlib import reload
import numpy as np
from maya import cmds
from maya_tools.scripts.tools import eyelid_contact
from maya_tools.scripts.biped.autorig import eyelid_module
reload(eyelid_contact)
reload(eyelid_module)
if cmds.file(q=True, sn=True) != 'C:/Users/LaiaPeris/Documents/maya/projects/default/scenes/CHAR_Edward_v001.ma':
    raise RuntimeError('Artist scene changed since inspection')
joints = sorted(cmds.ls('*Eyelid*Skinning_JNT', type='joint'))
before = np.array([cmds.getAttr(joint+'.worldMatrix[0]') for joint in joints])
upgraded = eyelid_contact.upgrade(['L_eyeDirect_CTL', 'R_eyeDirect_CTL'])
after = np.array([cmds.getAttr(joint+'.worldMatrix[0]') for joint in joints])
error = float(np.max(abs(before-after)))
if error > 1e-4:
    cmds.undo()
    raise RuntimeError('Current pose changed during upgrade: %s'%error)
result = {'upgraded': upgraded, 'current_joint_matrix_max_error': error,
          'selection': cmds.ls(sl=True), 'scene': cmds.file(q=True,sn=True),
          'saved': False}
