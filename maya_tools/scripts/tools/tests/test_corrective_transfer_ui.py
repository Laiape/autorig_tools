"""Real Qt transfer dialog and selected-vertex mask authoring."""
import os,sys
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1');os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.ui import pose_blendshapes_UI as ui
app=ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
qt_gui=__import__(ui.QtCore.__name__.rsplit('.',1)[0]+'.QtGui',fromlist=['QFont'])
qt_gui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf');app.setFont(qt_gui.QFont('Arial',9))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    from maya_tools.scripts.tools import pose_blendshapes as poses
    root=cmds.createNode('transform',name='Character')
    source=cmds.polyPlane(subdivisionsX=1,subdivisionsY=1)[0]
    target=cmds.polyPlane(subdivisionsX=2,subdivisionsY=2)[0]
    for m in (source,target):cmds.parent(m,root)
    ctl=cmds.createNode('transform',name='L_test_CTL',parent=root)
    cmds.select(source);window=ui.PoseBlendshapesUI();window.create_blendshape()
    bs=window.current_blendshape();cmds.setAttr(ctl+'.rotateZ',45)
    index,_=poses.add_target(source,bs,ctl)
    cmds.move(0,.2,0,source+'.vtx[*]',relative=True,objectSpace=True);poses.finish_edit()
    window.refresh_targets(index)
    dialog=ui.TransferDialog(window);cmds.select(target);dialog.load_mesh()
    assert dialog.mesh.text().endswith(target)
    dialog.mask.setChecked(True);cmds.select(target+'.vtx[4]');dialog.transfer()
    assert dialog.status.text().startswith('Created'),dialog.status.text()
    dest_bs=poses.blendshapes(target)[0];record=poses.pose_record(dest_bs,0)
    import json
    assert json.loads(cmds.getAttr(record+'.transferData'))['affected_vertices']==1
    folder=Path('C:/GIT/tmp/research_edward_validation')
    dialog.show();app.processEvents();dialog.grab().save(str(folder/'transfer_editor.png'))
    dialog.close();window.close()
    print('PASS transfer Qt: destination loading, transfer, selected-vertex mask and result feedback')
finally:maya.standalone.uninitialize()
