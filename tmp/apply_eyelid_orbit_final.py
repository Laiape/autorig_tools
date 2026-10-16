from importlib import reload
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import eyelid_corners,eyelid_rotation,eyelid_contact
from maya_tools.scripts.biped.autorig import eyelid_module
for module in (eyelid_corners,eyelid_rotation,eyelid_contact,eyelid_module):reload(module)
scene=cmds.file(q=True,sn=True)
modified=cmds.file(q=True,modified=True)
selection=cmds.ls(sl=True,long=True)
backup='C:/proyectos/auto-rig/recovery/eyelids_before_orbit_final_20261016_v001.mb'
if Path(backup).exists():raise RuntimeError('Backup already exists')
try:
    cmds.file(rename=backup);cmds.file(save=True,type='mayaBinary',force=True)
finally:
    cmds.file(rename=scene);cmds.file(modified=modified)
    cmds.select(selection,r=True) if selection else cmds.select(clear=True)
mode=cmds.evaluationManager(q=True,mode=True)[0]
cmds.evaluationManager(mode='off')
try:
    changed=eyelid_contact.upgrade(['L_eyeDirect_CTL','R_eyeDirect_CTL'])
finally:
    cmds.evaluationManager(mode=mode)
cmds.refresh(force=True)
result={'changed':changed,'backup':backup,'pose':{side+label:cmds.getAttr(side+'_eyelid'+label+'_CTL.rotate') for side in ('L','R') for label in ('Up','Down')},'scene':cmds.file(q=True,sn=True)}
