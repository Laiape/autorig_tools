import json
from pathlib import Path
from maya import cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets
from shiboken6 import wrapInstance
before=json.loads(Path('C:/proyectos/auto-rig/tmp/flower_20261016/rabbit_smooth/before.json').read_text())
cmds.currentTime(before['frame'])
cmds.select(before['selection'],replace=True)
if cmds.contextInfo(before['context'],exists=True):
    cmds.setToolTo(before['context'])
cmds.file(save=True,type='mayaBinary',force=True)
window=wrapInstance(int(omui.MQtUtil.mainWindow()),QtWidgets.QWidget)
window.raise_();window.activateWindow()
result={'scene':cmds.file(query=True,sceneName=True),'frame':cmds.currentTime(query=True),'curl':cmds.getAttr('C_flowerHead_CTL.petalCurl')}
