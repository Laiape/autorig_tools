"""Real Qt/Bifrost: source loading, vertex regions, preview and undo."""
import os,sys
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1');os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path[:0]=[str(Path(__file__).resolve().parents[4]),str(Path(__file__).resolve().parents[2])]
from maya_tools.scripts.ui import wrinkle_regions_UI as ui
app=ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
qt_gui=__import__(ui.QtWidgets.__name__.rsplit('.',1)[0]+'.QtGui',fromlist=['QFont'])
qt_gui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf');app.setFont(qt_gui.QFont('Arial',9))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import wrinkle_presets
    cmds.undoInfo(state=True)
    mesh=cmds.polyPlane(width=8,height=8,subdivisionsX=6,subdivisionsY=6)[0]
    cmds.select(mesh);window=ui.WrinkleRegionsUI();window.load_mesh();window.create()
    settings=window.current_settings();window.plane.setCurrentText('XZ')
    cmds.select(mesh+'.vtx[0:20]');window.assign_region()
    record=wrinkle_presets.setup_record(settings)
    pattern=record['patterns']['Forehead']
    assert any(abs(v)>1e-3 for v in pattern)
    window.preview.setChecked(True);assert cmds.getAttr(settings+'.ManualActivation')==1
    window.clear_region();assert all(abs(v)<1e-6 for v in wrinkle_presets.setup_record(settings)['patterns']['Forehead'])
    cmds.undo();assert any(abs(v)>1e-3 for v in wrinkle_presets.setup_record(settings)['patterns']['Forehead'])
    window.show();app.processEvents();window.grab().save('C:/GIT/tmp/research_edward_validation/wrinkle_editor.png')
    window.close();print('PASS wrinkle Qt: create, vertex region, plane/spacing, manual preview, clear/undo and setup feedback',flush=True)
finally:maya.standalone.uninitialize()
