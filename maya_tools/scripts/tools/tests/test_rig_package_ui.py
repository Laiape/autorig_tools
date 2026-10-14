"""Real Qt package verification and validation controls."""
import os,sys
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1';os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.ui import rig_package_UI as ui
app=ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
qt_gui=__import__(ui.QtWidgets.__name__.rsplit('.',1)[0]+'.QtGui',fromlist=['QFont'])
qt_gui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf');app.setFont(qt_gui.QFont('Arial',9))
import maya.standalone
maya.standalone.initialize(name='python')
try:
    window=ui.RigPackageUI()
    assert len(window.findChildren(ui.QtWidgets.QPushButton))==5
    window.show();app.processEvents()
    window.grab().save('C:/GIT/tmp/rig_package_ui.png');window.close()
    print('PASS package Qt controls and isolated validation action')
finally:maya.standalone.uninitialize()
