import datetime,json
from pathlib import Path
from maya import cmds,OpenMayaUI
from shiboken6 import wrapInstance
from PySide6.QtWidgets import QWidget

root=Path('C:/proyectos/auto-rig')
report=json.loads((root/'autorig_tools/maya_tools/assets/Nini/review/dress_keepout/rest_compensation_v005.json').read_text())
assert report['passed']
result={'previous_scene':cmds.file(q=True,sceneName=True)}
if cmds.file(q=True,modified=True):
    backup=root/'recovery'/('Before_Nini_Dress_Rest_Fix_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.ma')
    cmds.file(str(backup),exportAll=True,type='mayaAscii',preserveReferences=True,force=False)
    result['recovery']=str(backup)
cmds.file(report['scene'],open=True,force=True)
cmds.evaluationManager(mode='parallel');cmds.currentTime(1)
panel=next((p for p in cmds.getPanel(type='modelPanel') if cmds.modelPanel(p,q=True,camera=True)=='persp'),'modelPanel4')
cmds.lookThru(panel,'persp')
cmds.modelEditor(panel,e=True,displayAppearance='smoothShaded',wireframeOnShaded=False,grid=False,
                 displayLights='default',polymeshes=True,nurbsCurves=True,joints=False,locators=False)
cmds.select(clear=True);cmds.refresh(force=True)
capture=root/'tmp/Nini_dress_v005_neutral.png'
result['image']=cmds.playblast(frame=1,format='image',compression='png',completeFilename=str(capture),
                              widthHeight=(1000,1000),percent=100,viewer=False,showOrnaments=False,
                              offScreen=True,editorPanelName=panel)
cmds.select('C_dressSettings_CTL',replace=True)
window=wrapInstance(int(OpenMayaUI.MQtUtil.mainWindow()),QWidget)
window.showNormal();window.raise_();window.activateWindow()
result.update(scene=cmds.file(q=True,sceneName=True),selection=cmds.ls(selection=True),
              joints=len(cmds.ls('NiniDress_*',type='joint')))
