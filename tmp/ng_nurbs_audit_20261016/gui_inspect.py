from pathlib import Path
from PySide6 import QtWidgets
from maya import cmds
result={'tool':cmds.currentCtx(),'windows':[]}
for w in QtWidgets.QApplication.topLevelWidgets():
 if w.isVisible():
  texts=[(type(x).__name__,x.text()) for x in w.findChildren(QtWidgets.QWidget) if x.isVisible() and hasattr(x,'text') and isinstance(x,(QtWidgets.QLabel,QtWidgets.QPushButton))]
  result['windows'].append({'class':type(w).__name__,'object':w.objectName(),'title':w.windowTitle(),'texts':texts[-30:]})
  if isinstance(w,QtWidgets.QDialog):w.grab().save(str(Path(__file__).with_name('gui_dialog.png')))
