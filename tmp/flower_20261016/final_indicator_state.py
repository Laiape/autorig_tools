from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import module_nurbs
from importlib import reload
reload(module_nurbs)
def visible(node):
    selected=om.MSelectionList();selected.add(node)
    return selected.getDagPath(0).isVisible()
rows=[]
for pattern in ('*Pv_CRV','*eyeAim_CRV'):
    for curve in cmds.ls(pattern,type='transform',long=True) or []:
        control=module_nurbs.animator_indicator_control(curve)
        if control:
            rows.append({'line':curve.rsplit('|',1)[-1],'visible':visible(curve),'control_visible':visible(control),'parent':cmds.listRelatives(curve,parent=True)[0]})
assert len(rows)==6,rows
assert all(row['visible']==row['control_visible'] for row in rows)
result={'scene':cmds.file(query=True,sceneName=True),'lines':rows,
        'nurbs_curves_shown':cmds.modelEditor('modelPanel4',query=True,nurbsCurves=True),
        'idempotent':module_nurbs.restore_animator_indicators('Edward')}
