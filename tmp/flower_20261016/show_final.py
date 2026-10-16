from maya import cmds
from maya_tools.scripts.utils import scene_evaluation
from maya_tools.scripts.ui import auto_rig_UI
from maya_tools.scripts.framework import registry
from importlib import reload
reload(registry)
auto_rig_UI.create_custom_menu()
scene_evaluation.apply()
cmds.optionVar(stringValue=('currentAssetRigName', 'flower'))
cmds.currentTime(1)
cmds.select(clear=True)
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets
from shiboken6 import wrapInstance
window = wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)
if window.isMinimized():
    window.showNormal()
window.raise_()
window.activateWindow()
result = {'scene': cmds.file(query=True, sceneName=True), 'frame': cmds.currentTime(query=True),
          'skins': len(cmds.ls(type='skinCluster')), 'petal_roots': len(cmds.ls('C_petal*00_CTL')),
          'animation_curves': cmds.ls(type='animCurve'), 'evaluation': scene_evaluation.capture(),
          'maya_window_visible': window.isVisible(), 'flower_tools': [t.label for t in registry.search('flower')]}
