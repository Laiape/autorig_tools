import json, runpy
from pathlib import Path
import maya.cmds as cmds
from maya_tools.scripts.utils import scene_evaluation, curve_tool
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016')
target=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua/scenes/chihuahua_oriented_v002.mb')
assert not target.exists(),str(target)
def snapshot():
    nodes=sorted(cmds.ls(type='joint')+cmds.ls('*_CTL',type='transform'))
    matrices={n:cmds.xform(n,q=True,ws=True,m=True) for n in nodes}
    shapes={}
    for n in cmds.ls('*_CTL',type='transform'):
        shapes[n]=[{'cvs':cmds.xform(s+'.cv[*]',q=True,ws=True,t=True),'visible':cmds.getAttr(s+'.visibility')} for s in cmds.listRelatives(n,s=True,ni=True,type='nurbsCurve',f=True) or []]
    return matrices,shapes
visibility={n:[{'value':cmds.getAttr(s+'.visibility'),'source':cmds.connectionInfo(s+'.visibility',sourceFromDestination=True)} for s in cmds.listRelatives(n,s=True,ni=True,type='nurbsCurve',f=True) or []] for n in cmds.ls('*_CTL',type='transform')}
curve_tool.load_all_ctl_curves_data('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua/curves/chihuahua_v005.curves')
for n,states in visibility.items():
    for i,s in enumerate(cmds.listRelatives(n,s=True,ni=True,type='nurbsCurve',f=True) or []):
        state=states[min(i,len(states)-1)]
        if state['source']:cmds.connectAttr(state['source'],s+'.visibility',force=True)
        else:cmds.setAttr(s+'.visibility',state['value'])
original_matrices,expected_shapes=snapshot()
build=runpy.run_path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016/build_default.py')['result']
assert build['success'],build
actual_matrices,actual_shapes=snapshot()
assert original_matrices.keys()==actual_matrices.keys()
matrix_error=max(abs(a-b) for n in original_matrices for a,b in zip(original_matrices[n],actual_matrices[n]))
assert matrix_error<1e-4,matrix_error
assert expected_shapes.keys()==actual_shapes.keys()
shape_error=0.
for n in expected_shapes:
    assert len(expected_shapes[n])==len(actual_shapes[n]),n
    for a,b in zip(expected_shapes[n],actual_shapes[n]):
        assert len(a['cvs'])==len(b['cvs']),n
        err=max(abs(x-y) for x,y in zip(a['cvs'],b['cvs']));shape_error=max(shape_error,err)
        assert err<1e-4,(n,err)
        assert a['visible']==b['visible'],('visibility',n,a['visible'],b['visible'])
scene_evaluation.apply()
cmds.select(clear=True)
cmds.file(rename=str(target));cmds.file(save=True,type='mayaBinary',force=True)
cmds.file(str(target),open=True,force=True,prompt=False,executeScriptNodes=False)
reopened,reopened_shapes=snapshot()
reopen_error=max(abs(a-b) for n in actual_matrices for a,b in zip(actual_matrices[n],reopened[n]))
assert reopen_error<1e-4,reopen_error
assert actual_shapes==reopened_shapes
assert cmds.getAttr('C_spine00_CTL.tanVisibility')==0
assert len(cmds.ls('C_spine*Tan_CTL',type='transform'))==2
result={'passed':True,'scene':str(target),'curve_version':'chihuahua_v005.curves','controllers':len(actual_shapes),'compared_joints_and_controls':len(actual_matrices),'matrix_max_error':matrix_error,'world_shape_cv_max_error':shape_error,'native_reopen_matrix_max_error':reopen_error,'native_shape_data_exact':True,'visibility_preserved':True,'spine_tangents_hidden':True}
(base/'validation.json').write_text(json.dumps(result,indent=2))
