from datetime import datetime
from pathlib import Path
from maya import cmds

root = Path('C:/proyectos/auto-rig')
scene = root / 'autorig_tools/maya_tools/assets/Nini/scenes/Nini_dress_chains_v004.ma'
result = {'previous_scene': cmds.file(q=True, sceneName=True)}
if cmds.file(q=True, modified=True):
    backup = root / 'recovery' / ('Before_Open_Nini_Dress_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.ma')
    backup.parent.mkdir(parents=True, exist_ok=True)
    cmds.file(str(backup), exportAll=True, type='mayaAscii', preserveReferences=True, force=False)
    result['recovery'] = str(backup)
cmds.file(str(scene), open=True, force=True)
assert cmds.objExists('C_dressSettings_CTL'), 'Dress settings control missing'
joints = cmds.ls('NiniDress_*', type='joint')
assert len(joints) == 72, 'Unexpected dress joint count: %s' % len(joints)
cmds.currentTime(1)
cmds.select('C_dressSettings_CTL', replace=True)
for panel in cmds.getPanel(type='modelPanel'):
    cmds.modelEditor(panel, edit=True, nurbsCurves=True, polymeshes=True)
cmds.refresh(force=True)
try:
    from maya import OpenMayaUI
    from shiboken6 import wrapInstance
    from PySide6.QtWidgets import QWidget
    window = wrapInstance(int(OpenMayaUI.MQtUtil.mainWindow()), QWidget)
    window.showNormal()
    window.raise_()
    window.activateWindow()
except ImportError:
    pass
result.update(scene=cmds.file(q=True, sceneName=True), dress_joints=len(joints), selected=cmds.ls(selection=True))
