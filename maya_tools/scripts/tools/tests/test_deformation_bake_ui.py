"""Real Qt: bake, held-out validation and heat map through the production UI."""
import os,sys
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1');os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path[:0]=[str(Path(__file__).resolve().parents[4]),str(Path(__file__).resolve().parents[2])]
from maya_tools.scripts.ui import proximity_bake_UI as ui
app=ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
qt_gui=__import__(ui.QtWidgets.__name__.rsplit('.',1)[0]+'.QtGui',fromlist=['QFont'])
qt_gui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf');app.setFont(qt_gui.QFont('Arial',9))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    cmds.undoInfo(state=True)
    a=cmds.joint(name='root');b=cmds.joint(name='tip',position=(0,2,0))
    mesh=cmds.polyPlane(subdivisionsX=2,subdivisionsY=2)[0]
    cmds.skinCluster([a,b],mesh,toSelectedBones=True)
    cmds.setKeyframe(b,attribute='rotateZ',time=0,value=0)
    cmds.setKeyframe(b,attribute='rotateZ',time=2,value=30)
    cmds.currentTime(0);cmds.select(mesh)
    window=ui.DeformationBakeUI();window.start.setValue(0);window.end.setValue(2);window.bind.setValue(0)
    window.influences.setValue(2);window.bake()
    assert window.status.text().startswith('Baked'),window.status.text()
    assert len(window.result['validation_frames'])==2
    assert cmds.objExists(mesh)
    window.show();app.processEvents()
    window.grab().save('C:/GIT/tmp/research_edward_validation/bake_editor.png')
    window.close()
    print('PASS deformation bake Qt: sampling options, bake, independent validation, heat map and feedback')
finally:maya.standalone.uninitialize()
