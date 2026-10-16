from maya import cmds
from maya.api import OpenMaya as om
curve='L_eyeAim_CRV'
shape=cmds.listRelatives(curve,shapes=True,noIntermediate=True,fullPath=True)[0]
sl=om.MSelectionList();sl.add(shape);fn=om.MFnNurbsCurve(sl.getDagPath(0))
result={'shape':shape,'degree':fn.degree,'numCVs':fn.numCVs,'inherits':cmds.getAttr(curve+'.inheritsTransform'),
        'overrides':[cmds.getAttr(curve+'.'+a) for a in ['overrideEnabled','overrideDisplayType']],
        'consumers':{a:cmds.listConnections(shape+'.'+a,source=False,destination=True) for a in ['worldSpace','local']},
        'rows':{str(i):cmds.listConnections('%s.controlPoints[%d]'%(shape,i),source=True,destination=False,type='rowFromMatrix') for i in (0,1)}}
for i,rows in result['rows'].items():
    for row in rows or []:
        result[row]={'input':cmds.getAttr(row+'.input'),'sources':cmds.listConnections(row+'.matrix',source=True,destination=False,plugs=True)}
result['connections_transform']=cmds.listConnections(curve,source=True,destination=False,connections=True,plugs=True)
result['connections_shape']=cmds.listConnections(shape,source=True,destination=False,connections=True,plugs=True)
result['leaf_transform']=cmds.listConnections(curve+'.controlPoints[0].xValue',source=True,destination=False,plugs=True)
result['leaf_shape']=cmds.listConnections(shape+'.controlPoints[0].xValue',source=True,destination=False,plugs=True)
result['raw_rows']={row:{'type':cmds.nodeType(row),'input':cmds.getAttr(row+'.input'),'matrix':cmds.listConnections(row+'.matrix',source=True,destination=False,plugs=True)} for row in ['L_eyeAim_RFM','L_eyeAimCtl_RFM']}
result['filtered_leaf']=cmds.listConnections(shape+'.controlPoints[0].xValue',source=True,destination=False,type='rowFromMatrix')
result['control_type']=cmds.nodeType('L_eye_CTL')
result['control_typed']=cmds.ls('L_eye_CTL',long=True,type='transform')
from maya_tools.scripts.utils import module_nurbs
result['resolved']=module_nurbs.animator_indicator_control(curve)
