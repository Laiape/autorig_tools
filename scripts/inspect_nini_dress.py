"""Inspect Nini's latest saved rig without touching the interactive Maya scene."""
import json
import os
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
root=Path(__file__).resolve().parents[1]
source=root/'maya_tools/assets/Nini/review/loop_rigger/Nini_ManualLoops_v001.ma'
cmds.file(str(source),open=True,force=True)
result={'source':str(source),'meshes':[],'drivers':{},'controls':{}}
for shape in cmds.ls(type='mesh',long=True):
    if cmds.getAttr(shape+'.intermediateObject'): continue
    transform=cmds.listRelatives(shape,parent=True,fullPath=True)[0]
    history=cmds.listHistory(shape) or []
    selection=om.MSelectionList(); selection.add(shape)
    fn=om.MFnMesh(selection.getDagPath(0))
    item={'transform':transform,'vertices':fn.numVertices,'polygons':fn.numPolygons,
          'bounds':cmds.exactWorldBoundingBox(transform),
          'skin':[node for node in history if cmds.nodeType(node)=='skinCluster'],
          'visible':cmds.getAttr(transform+'.visibility'),
          'materials':cmds.listConnections(shape,type='shadingEngine') or []}
    result['meshes'].append(item)
for name in ('C_localHip_CTL','C_masterwalk_CTL','C_localHip_ENV',
             'L_legUpper00_ENV','L_legLower00_ENV','L_legAnkle_ENV',
             'R_legUpper00_ENV','R_legLower00_ENV','R_legAnkle_ENV'):
    if cmds.objExists(name): result['drivers'][name]={'matrix':cmds.getAttr(name+'.worldMatrix[0]')}
for name in ('L_ankleIk_CTL','R_ankleIk_CTL','L_legSettings_CTL','R_legSettings_CTL'):
    if cmds.objExists(name): result['controls'][name]={'matrix':cmds.xform(name,q=True,ws=True,m=True),
            'attributes':cmds.listAttr(name,keyable=True)}
directory=root/'maya_tools/assets/Nini/experiments/dress_keepout'; directory.mkdir(parents=True,exist_ok=True)
(directory/'source_inspection.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('NINI_DRESS_INSPECTION='+json.dumps(result),flush=True)
maya.standalone.uninitialize()
