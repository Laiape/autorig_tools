"""Native Qt general rig bindings and portable validation profile workflow."""
import os, sys, tempfile, json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.ui import pose_tester_UI as ui
app = ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
ui.QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf'); app.setFont(ui.QtGui.QFont('Arial',9))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
try:
    root = cmds.createNode('transform', name='Creature')
    ctl = cmds.createNode('transform', name='arbitraryControl', parent=root)
    mesh = cmds.polyCube()[0]; mesh = cmds.parent(mesh, root)[0]
    window = ui.PoseTesterUI(); panel = window.general_rig
    cmds.select(root); panel.load_root()
    cmds.select(ctl); panel.bind_selected()
    assert panel.binding_list.count() == 1
    assert panel._bindings[0]['node'].endswith('|arbitraryControl')
    cmds.select(mesh); window._load_report_meshes()
    with tempfile.TemporaryDirectory() as tmp:
        report = str(Path(tmp)/'general.rigqa.json')
        old = ui.QtWidgets.QFileDialog.getSaveFileName
        ui.QtWidgets.QFileDialog.getSaveFileName = lambda *a, **k: (report, '')
        try: panel.run_profile()
        finally: ui.QtWidgets.QFileDialog.getSaveFileName = old
        assert json.loads(Path(report).read_text())['quality_pass']
    # New tabs work through the same native window.
    panel.capture_pose();assert panel.pose_list.count()==1
    panel.pose_list.setCurrentRow(0);cmds.setAttr(ctl+'.rotateZ',12);panel.apply_pose()
    assert cmds.getAttr(ctl+'.rotateZ')==0
    from maya_tools.scripts.tools import rig_roles
    rig_roles.bind(root,mesh,'body.garment',module='body',kind='mesh')
    body=cmds.polyCube(width=4,height=4,depth=4)[0];body=cmds.parent(body,root)[0]
    rig_roles.bind(root,body,'body.render',module='body',kind='mesh')
    panel.measure_contact();assert not panel._contact_result['pass']
    panel.select_contact_vertices();assert len(cmds.ls(selection=True,flatten=True))==8
    panel.add_contact();assert len(panel.profile()['contacts'])==1
    destination=cmds.createNode('transform',name='FreshCreature')
    new_ctl=cmds.createNode('transform',name='OtherAnimator',parent=destination)
    rig_roles.bind(destination,new_ctl,'body.head',module='neck')
    for role in ('body.garment','body.render'):
        new_mesh=cmds.duplicate(mesh if role=='body.garment' else body)[0]
        new_mesh=cmds.parent(new_mesh,destination)[0]
        rig_roles.bind(destination,new_mesh,role,module='body',kind='mesh')
    cmds.select(destination);panel.load_migration_destination();panel.preview_migration()
    assert json.loads(panel.migration_view.toPlainText())['ready']
    panel.apply_migration();assert json.loads(panel.migration_view.toPlainText())['source_preserved']
    window.show(); app.processEvents()
    panel.refresh_bindings()
    scroll=window.findChild(ui.QtWidgets.QScrollArea);scroll.ensureWidgetVisible(panel);app.processEvents()
    image = Path('C:/GIT/tmp/general_rig_tools.png'); window.grab().save(str(image))
    window.close()
    print('PASS general Test Rig Qt: character root, custom role, profile run and scrollable existing UI')
finally:
    maya.standalone.uninitialize()
