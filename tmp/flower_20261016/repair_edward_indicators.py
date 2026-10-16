import hashlib
import json
from pathlib import Path
import struct
from importlib import reload
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import module_nurbs

reload(module_nurbs)
original=cmds.file(query=True,sceneName=True)
if not cmds.objExists('Edward') or 'Edward' not in original:
    raise RuntimeError('The active scene is not Edward; preserve the current artist scene.')
frame=cmds.currentTime(query=True)
selection=cmds.ls(selection=True,long=True)
folder=Path('C:/proyectos/auto-rig/recovery')
index=1
while (folder/('Edward_before_indicator_restore_20261016_v%03d.mb'%index)).exists():
    index+=1
backup=folder/('Edward_before_indicator_restore_20261016_v%03d.mb'%index)
cmds.file(rename=str(backup));cmds.file(save=True,type='mayaBinary',force=True)
cmds.file(rename=original)

def geometry():
    output={}
    for shape in cmds.ls('Edward',dag=True,type='mesh',noIntermediate=True,long=True) or []:
        selected=om.MSelectionList();selected.add(shape);fn=om.MFnMesh(selected.getDagPath(0))
        values=[v for p in fn.getPoints(om.MSpace.kWorld) for v in (p.x,p.y,p.z)]
        output[shape]=hashlib.sha256(struct.pack('<%sd'%len(values),*values)).hexdigest()
    return output

def joints():
    result={}
    for joint in cmds.ls('Edward',dag=True,type='joint',long=True):
        selected=om.MSelectionList();selected.add(joint)
        result[joint]=list(selected.getDagPath(0).inclusiveMatrix())
    return result

def endpoints():
    result={}
    for pattern in ('*Pv_CRV','*eyeAim_CRV'):
        for curve in cmds.ls(pattern,type='transform',long=True) or []:
            selected=om.MSelectionList();selected.add(curve);path=selected.getDagPath(0);path.extendToShape()
            result[curve.rsplit('|',1)[-1]]=[(p.x,p.y,p.z) for p in om.MFnNurbsCurve(path).cvPositions(om.MSpace.kWorld)]
    return result

before_meshes=geometry()
before_joints=joints()
before_lines=endpoints()
result=module_nurbs.restore_animator_indicators('Edward')
assert len(result['restored'])==6,result
assert not result['skipped'],result
assert endpoints()==before_lines,'Indicator endpoints moved'
assert geometry()==before_meshes,'Rig deformation changed'
assert joints()==before_joints,'Joint transforms changed'
assert cmds.getAttr('modules_GRP.visibility')==0
assert cmds.currentTime(query=True)==frame
assert cmds.ls(selection=True,long=True)==selection
visible=[]
for curve in result['restored']:
    selected=om.MSelectionList();selected.add(curve)
    if selected.getDagPath(0).isVisible():
        visible.append(curve)
from maya_tools.scripts.framework import registry
reload(registry)
from maya_tools.scripts.ui import auto_rig_UI
auto_rig_UI.create_custom_menu()
asset=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/Edward')
(asset/'scenes').mkdir(exist_ok=True)
index=1
while (asset/('scenes/Edward_indicator_lines_v%03d.mb'%index)).exists():
    index+=1
scene=asset/('scenes/Edward_indicator_lines_v%03d.mb'%index)
cmds.file(rename=str(scene));cmds.file(save=True,type='mayaBinary',force=True)
result.update(scene=str(scene),backup=str(backup),visible=visible,mesh_outputs_unchanged=len(before_meshes),
              joint_matrices_unchanged=len(before_joints),endpoints_unchanged=True,frame=frame,passed=True)
(asset/'validation').mkdir(exist_ok=True)
(asset/'validation/indicator_restore_20261016.json').write_text(json.dumps(result,indent=2))
