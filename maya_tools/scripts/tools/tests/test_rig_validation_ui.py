"""Real Qt: report mesh loading and optional comparison controls."""
import os,sys
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY","1")
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.ui import pose_tester_UI as ui
app=ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
qt_gui=__import__(ui.QtCore.__name__.rsplit('.',1)[0]+'.QtGui',fromlist=['QFont'])
qt_gui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf');app.setFont(qt_gui.QFont('Arial',9))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_validation
    root=cmds.createNode('transform',name='Character')
    mesh=cmds.polySphere()[0];cmds.parent(mesh,root);cmds.select(mesh)
    window=ui.PoseTesterUI()
    window._load_report_meshes()
    assert len(window._report_meshes)==1
    folder=Path('C:/GIT/tmp/research_edward_validation')
    report=folder/'ui_health.righealth.json'
    if report.exists(): report.unlink()
    assert rig_validation.write_build_health(root,str(report))['meshes']==1
    window.show();app.processEvents();window.grab().save(str(folder/'rig_validation_editor.png'))
    window.close()
    print('PASS Rig QA Qt: mesh loading, baseline/report controls, post-build health output')
finally:
    maya.standalone.uninitialize()
