import copy, json
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import curve_tool

base = Path('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016')
asset = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua')
target = asset/'curves/chihuahua_v005.curves'
assert not target.exists(), str(target)
cmds.file(str(asset/'scenes/chihuahua_oriented_v001.mb'),open=True,force=True,prompt=False,executeScriptNodes=False)
source = json.loads((asset/'curves/chihuahua_v004.curves').read_text())
source = {v['transform']['name']:v for v in source.values()}
old = json.loads((base/'old_controls.json').read_text())
new = json.loads((base/'oriented_controls.json').read_text())
nodes = sorted(cmds.ls(type='joint') + cmds.ls('*_CTL',type='transform'))
before = {n:cmds.xform(n,q=True,ws=True,m=True) for n in nodes}
output = {}; changed = []; errors = []
for name in sorted(new):
    previous = name.replace('01Tan_CTL','01_CTL').replace('03Tan_CTL','03_CTL')
    assert previous in old and previous in source, name
    data = copy.deepcopy(source[previous])
    data['transform']['name'] = name
    r_old = om.MTransformationMatrix(om.MMatrix(old[previous]['matrix'])).rotation(asQuaternion=True).asMatrix()
    r_new = om.MTransformationMatrix(om.MMatrix(new[name]['matrix'])).rotation(asQuaternion=True).asMatrix()
    rotation = r_old * r_new.inverse()
    difference = max(abs(a-b) for a,b in zip(rotation,om.MMatrix.kIdentity))
    if difference > 1e-8: changed.append(name)
    for shape in data['shapes']:
        shape['name'] = shape['name'].replace(previous,name)
        if difference > 1e-8:
            shape['curve']['cvs'] = [list(om.MPoint(*pt) * rotation)[:3] for pt in shape['curve']['cvs']]
    long_name = cmds.ls(name,long=True,type='transform')
    assert len(long_name)==1, name
    output[long_name[0]]=data
display = {}
for path in output:
    shapes = cmds.listRelatives(path,s=True,ni=True,type='nurbsCurve',f=True) or []
    display[path]=[{'value':cmds.getAttr(s+'.visibility'),'source':cmds.connectionInfo(s+'.visibility',sourceFromDestination=True)} for s in shapes]
target.write_text(json.dumps(output,indent=4))
curve_tool.load_all_ctl_curves_data(str(target))
restored = 0
for path, states in display.items():
    shapes = cmds.listRelatives(path,s=True,ni=True,type='nurbsCurve',f=True) or []
    for index, shape in enumerate(shapes):
        state=states[min(index,len(states)-1)]
        if state['source']:
            cmds.connectAttr(state['source'],shape+'.visibility',force=True);restored+=1
        else:
            cmds.setAttr(shape+'.visibility',state['value'])
for n in nodes:
    error=max(abs(a-b) for a,b in zip(before[n],cmds.xform(n,q=True,ws=True,m=True)))
    assert error<1e-8,(n,error)
for path,data in output.items():
    shapes = cmds.listRelatives(path,s=True,ni=True,type='nurbsCurve',f=True)
    assert len(shapes)==len(data['shapes']),path
    for shape,expected in zip(shapes,data['shapes']):
        actual=cmds.xform(shape+'.cv[*]',q=True,os=True,t=True)
        wanted=[v for p in expected['curve']['cvs'] for v in p]
        error=max(abs(a-b) for a,b in zip(actual,wanted));errors.append(error)
        assert error<1e-8,(shape,error)
result={'passed':True,'source':str(asset/'curves/chihuahua_v004.curves'),'curves':str(target),'controls':len(output),'rotated_shapes_controls':changed,'matrix_max_error':0.,'cv_max_error':max(errors),'restored_visibility_connections':restored}
(base/'adapted.json').write_text(json.dumps(result,indent=2))
