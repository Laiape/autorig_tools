import json,os,runpy,sys,traceback
from pathlib import Path
Path(__file__).with_name('portable_gui_stage.txt').write_text('Python bootstrap entered')
from maya import cmds,OpenMayaUI as legacy_ui
cmds.loadPlugin('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/plug-ins/2026/ngSkinTools2.mll',quiet=True)
from PySide6 import QtWidgets,QtCore,QtTest
from shiboken6 import wrapInstance
folder=Path(__file__).resolve().parent
def stage(text):
 (folder/'portable_gui_stage.txt').write_text(text)
 (folder/'portable_gui_stage_pid.json').write_text(json.dumps({'pid':os.getpid(),'stage':text,'restart':os.environ.get('NG_NURBS_PORTABLE_RESTART')}))
stage('bootstrap started')
def dump_dialogs():
 records=[]
 for widget in QtWidgets.QApplication.topLevelWidgets():
  if widget.isVisible() and isinstance(widget,QtWidgets.QDialog):
   records.append({'title':widget.windowTitle(),'object':widget.objectName(),
    'texts':[x.text() for x in widget.findChildren(QtWidgets.QWidget) if isinstance(x,(QtWidgets.QLabel,QtWidgets.QPushButton)) and x.isVisible()]})
 (folder/'portable_gui_dialogs.json').write_text(json.dumps(records,indent=2))
_timer=QtCore.QTimer(QtWidgets.QApplication.instance())
_timer.timeout.connect(dump_dialogs);_timer.start(2000)
sys.path[:]=[p for p in sys.path if 'auto-rig' not in p.lower() or 'gui_portable_preferences' in p]
sys.path.insert(0,'C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts')
result={'pid':os.getpid()}
import faulthandler
faulthandler.dump_traceback_later(12,file=(folder/'portable_hang_stack.log').open('w'))
result['modules']=cmds.moduleInfo(listModules=True)
result['maya_directory']=cmds.internalVar(userAppDir=True)
result['skip_user_setup']=os.environ.get('MAYA_SKIP_USERSETUP_PY')
result['scripts_path']=[p for p in sys.path if 'ngNurbsBridge' in p]
result['safe_mode']={n:cmds.optionVar(query=n) if cmds.optionVar(exists=n) else None for n in ['SafeModeExecUserSetupScript','SafeModeUserSetupHashOption']}
import __main__
result['startup_defined']=hasattr(__main__,'_ng_nurbs_startup')
result['pending_deferred']=cmds.evalDeferred(list=True)
try:
 restart=os.environ.get('NG_NURBS_PORTABLE_RESTART')=='1'
 from ngSkinTools2.ui import mainwindow
 stage('mainwindow imported')
 if restart:
  QtTest.QTest.qWait(250)
  result['startup_hook']=bool(getattr(mainwindow.build_ui,'_ng_nurbs_original',None))
  assert result['startup_hook'],'Maya startup did not attach NG automatically.'
  import ngSkinTools2
  ngSkinTools2.open_ui()
 else:
  installer=runpy.run_path('C:/proyectos/auto-rig/autorig_tools/dist/install_ng_nurbs_bridge.py')
  stage('drop installer')
  installer['onMayaDroppedPythonFile']()
 stage('NG open')
 QtWidgets.QApplication.processEvents();QtTest.QTest.qWait(150)
 widget=wrapInstance(int(legacy_ui.MQtUtil.findControl(mainwindow.DOCK_NAME)),QtWidgets.QWidget)
 tabs=widget.findChild(QtWidgets.QTabWidget,'ngNurbsStandaloneTabs')
 assert tabs is not None
 result['tabs']=[tabs.tabText(i) for i in range(tabs.count())]
 result['no_autorig_imports']=not any(n=='maya_tools' or n.startswith('maya_tools.') for n in sys.modules)
 assert result['no_autorig_imports']
 from ng_nurbs_bridge import core,brush
 result['package']=sys.modules['ng_nurbs_bridge'].__file__
 scene=folder/'gui_portable_preferences/portable_scene.ma'
 if restart:
  cmds.file(str(scene),open=True,force=True,executeScriptNodes=False)
  cmds.select('portableSurface')
 else:
  surface=cmds.nurbsPlane(name='portableSurface',patchesU=2,patchesV=3,ch=False)[0]
  js=[cmds.createNode('joint') for _ in range(2)]
  cmds.setAttr(js[1]+'.tx',2)
  cmds.skinCluster(js,surface,tsb=True)
  cmds.select(surface)
 tabs.setCurrentIndex(1)
 panel=tabs.widget(1).nurbs_panel
 panel.load_selection();panel.create_bridge()
 stage('bridge created')
 if not restart:
  panel.value.setValue(.6);panel.intensity.setValue(1)
  panel.flood()
  stage('flood complete')
 result['layers']=panel.layer_tree.topLevelItemCount()
 if not restart:
  panel.start_paint();result['paint_context']=cmds.currentCtx()
  assert brush.active() is not None
  panel.deactivate()
 else:
  result['native_weights_after_reopen']=core.sparse_weights(panel.bridge.skin)['0']
  result['secure_plugin_prompt_preserved']=True
 if not restart:
  installer['onMayaDroppedPythonFile']()
  QtWidgets.QApplication.processEvents()
  assert len(widget.findChildren(QtWidgets.QTabWidget,'ngNurbsStandaloneTabs'))==1
  result['repeat_drop_single_tab']=True
  cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii')
 widget.grab().save(str(folder/('portable_restart.png' if restart else 'portable_install.png')))
 result['success']=True
except BaseException:
 result['traceback']=traceback.format_exc()
filename='portable_gui_restart.json' if os.environ.get('NG_NURBS_PORTABLE_RESTART')=='1' else 'portable_gui_install.json'
(folder/filename).write_text(json.dumps(result,indent=2))
stage('complete')
if result.get('success'):faulthandler.cancel_dump_traceback_later()
if os.environ.get('NG_NURBS_PORTABLE_RESTART')=='1' and not result.get('success') and not globals().get('NG_IDLE_RETRY'):
 _retry_path=__file__
 QtCore.QTimer.singleShot(1500,lambda:runpy.run_path(_retry_path,init_globals={'NG_IDLE_RETRY':True}))
