import json,os,sys
from pathlib import Path
from maya import cmds
root=Path('C:/proyectos/auto-rig/autorig_tools')
sys.path.insert(0,str(root))
sys.path.insert(0,str(root/'maya_tools/scripts'))
ng=Path('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents')
sys.path.insert(0,str(ng/'scripts'))
cmds.loadPlugin(str(ng/'plug-ins/2026/ngSkinTools2.mll'),quiet=True)
cmds.commandPort(name='127.0.0.1:7442',sourceType='python',echoOutput=True)
cmds.commandPort(name='127.0.0.1:7443',sourceType='python',echoOutput=True)
from ngSkinTools2.ui.options import config
config.checkForUpdatesAtStartup.set(False)
Path(__file__).with_name('gui_ready.json').write_text(json.dumps({'pid':os.getpid(),'port':7442,'batch':cmds.about(batch=True)}))
from PySide6 import QtCore,QtWidgets
def dump_dialogs():
 records=[]
 for widget in QtWidgets.QApplication.topLevelWidgets():
  if widget.isVisible() and isinstance(widget,QtWidgets.QDialog):
   records.append({'class':type(widget).__name__,'object':widget.objectName(),'title':widget.windowTitle(),
    'texts':[x.text() for x in widget.findChildren(QtWidgets.QWidget) if isinstance(x,(QtWidgets.QLabel,QtWidgets.QPushButton)) and x.isVisible()]})
 Path(__file__).with_name('gui_dialogs.json').write_text(json.dumps(records,indent=2))
_dialog_timer=QtCore.QTimer(QtWidgets.QApplication.instance())
_dialog_timer.timeout.connect(dump_dialogs)
_dialog_timer.start(2000)
