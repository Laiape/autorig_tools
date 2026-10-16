from pathlib import Path
from importlib import reload
from maya import cmds
from maya_tools.scripts.tools import eyelid_corners,eyelid_rotation,eyelid_contact
from maya_tools.scripts.biped.autorig import eyelid_module
for module in (eyelid_corners,eyelid_rotation,eyelid_contact,eyelid_module):reload(module)
scene=cmds.file(q=True,sn=True);modified=cmds.file(q=True,modified=True)
selection=cmds.ls(sl=True,long=True);mode=cmds.evaluationManager(q=True,mode=True)[0]
backup='C:/proyectos/auto-rig/recovery/eyelids_before_control_falloff_20261016_v001.mb'
if Path(backup).exists():raise RuntimeError('Backup already exists')
pose={ctl+'.'+channel:cmds.getAttr(ctl+'.'+channel) for ctl in cmds.ls('*_eyelid*CTL') for channel in ('tx','ty','tz','rx','ry','rz')}
cmds.file(backup,exportAll=True,type='mayaBinary',preserveReferences=True,force=True)
cmds.evaluationManager(mode='off')
try:
    changed=eyelid_contact.upgrade(['L_eyeDirect_CTL','R_eyeDirect_CTL'])
finally:
    cmds.evaluationManager(mode=mode)
    cmds.select(selection,r=True) if selection else cmds.select(clear=True)
assert cmds.file(q=True,sn=True)==scene
assert all(abs(cmds.getAttr(plug)-value)<1e-8 for plug,value in pose.items())
cmds.refresh(force=True)
result={'changed':changed,'backup':backup,'pose_preserved':True,'scene':scene,'version':eyelid_corners.VERSION}
