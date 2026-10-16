import importlib
from maya_tools.scripts.framework import registry
from maya_tools.scripts.utils import curve_tool, ui_utils, ui_theme
from ui import auto_rig_UI
from tools import curve_library
import maya.cmds as cmds
from PySide6 import QtWidgets
importlib.reload(ui_theme)
importlib.reload(ui_utils)
importlib.reload(registry)
importlib.reload(curve_tool)
importlib.reload(auto_rig_UI)
importlib.reload(curve_library)
auto_rig_UI.create_custom_menu()
selection = cmds.ls(selection=True, long=True) or []
modified = cmds.file(query=True, modified=True)
nodes = set(cmds.ls(long=True))
window = registry.invoke('controllers_text')
window.text_input.setText('Auto Rig')
window.text_name.setText('textControllerUITest_CTL')
window.text_height.setValue(2.0)
window.create_text_button.click()
created = cmds.ls(selection=True)[0]
assert created == 'textControllerUITest_CTL', created
assert cmds.listRelatives(created, shapes=True, type='nurbsCurve')
cmds.undo()
assert set(cmds.ls(long=True)) == nodes
if selection:
    cmds.select(selection, replace=True)
else:
    cmds.select(clear=True)
cmds.file(modified=modified)
window.text_input.setText('F')
window.text_name.setText('C_text_CTL')
window.text_height.setValue(1.0)
window.text_input.setFocus()
window.text_input.selectAll()
QtWidgets.QApplication.processEvents()
image_path = 'C:/proyectos/auto-rig/tmp/text_controller_20261016/library.png'
window.grab().save(image_path)
menus = cmds.lsUI(menuItems=True, long=True) or []
entries = []
for item in menus:
    try:
        if cmds.menuItem(item, query=True, label=True) == 'Create Text Controller':
            entries.append(item)
    except RuntimeError:
        pass
assert entries, 'Missing menu entry'
result = {'ui_create_undo': 'passed', 'menu_entries': entries, 'scene_preserved': True,
          'image': image_path, 'window_size': [window.width(), window.height()]}
