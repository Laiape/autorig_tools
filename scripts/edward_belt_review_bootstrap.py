"""Open one requested artist review window in its own Maya process."""
import json
import os
from pathlib import Path
import sys
import traceback
settings_path=Path(os.environ['EDWARD_BELT_REVIEW_SETTINGS'])
settings=json.loads(settings_path.read_text())
assert os.getpid()==settings['pid']
ROOT=Path(settings['root']);FOLDER=Path(settings['folder'])
sys.path[:0]=[str(ROOT/'autorig_tools'),str(ROOT/'autorig_tools/maya_tools/scripts')]
from maya import cmds,mel
try:
    for plugin in ('matrixNodes','quatNodes','lookdevKit','deformerEvaluator','bifrostGraph'):
        try:cmds.loadPlugin(plugin,quiet=True)
        except Exception:pass
    cmds.evaluationManager(mode='off');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
    cmds.file(settings['scene'],open=True,force=True,prompt=False,executeScriptNodes=False)
    cmds.evaluationManager(mode='parallel')
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4',e=True,displayAppearance='smoothShaded',displayTextures=False,
                     rendererName='vp2Renderer',shadows=False,grid=False,wireframeOnShaded=False)
    cmds.select(settings['meshes'],r=True)
    cmds.viewFit('persp',fitFactor=.8,animate=False)
    cmds.select('Edward_BeltBlendshape_Review',r=True)
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
    from maya import OpenMayaUI
    window=wrapInstance(int(OpenMayaUI.MQtUtil.mainWindow()),QtWidgets.QWidget)
    bounds=QtWidgets.QApplication.primaryScreen().availableGeometry()
    width=max(800,bounds.width()//2)
    window.showNormal();window.resize(width,bounds.height())
    window.move(bounds.x()+settings['index']*(bounds.width()//2),bounds.y())
    window.setWindowTitle('Edward belts - '+settings['label']+' comparison - EXPERIMENTAL')
    cmds.commandPort(name='127.0.0.1:'+str(settings['port']),sourceType='python',echoOutput=False)
    result={'success':True,'pid':os.getpid(),'scene':cmds.file(q=True,sn=True),
            'selector':cmds.getAttr('Edward_BeltBlendshape_Review.beltVariant'),
            'selection':cmds.ls(sl=True),'evaluation':cmds.evaluationManager(q=True,mode=True),
            'visible_meshes':settings['meshes'],'joints':len(cmds.ls(type='joint'))}
    cmds.file(modified=False)
except BaseException:
    result={'success':False,'pid':os.getpid(),'traceback':traceback.format_exc()}
(FOLDER/('artist_window_'+settings['label']+'_ready.json')).write_text(json.dumps(result,indent=2))
