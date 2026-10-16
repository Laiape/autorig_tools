from PySide6 import QtCore
from maya import cmds
QtCore.QTimer.singleShot(200, lambda: cmds.quit(force=True))
result={'closing_disposable_gui':True}
