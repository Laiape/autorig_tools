from maya import cmds
import math
result={'scene':cmds.file(q=True,sn=True),'selection':cmds.ls(sl=True,long=True),
        'frame':cmds.currentTime(q=True),'controls':{},'paths':{}}
for node in cmds.ls('*eyelid*CTL')+cmds.ls('*Eyelid*CTL'):
    values={attr:cmds.getAttr(node+'.'+attr) for attr in ('translate','rotate')}
    if any(abs(v)>1e-5 for group in values.values() for v in group[0]):
        result['controls'][node]=values
for side in ('L','R'):
    direct=side+'_eyeDirect_CTL'
    result['controls'][direct]={attr:cmds.getAttr(direct+'.'+attr) for attr in ('Upper_Blink','Lower_Blink','Blink_Height')}
    rows=[]
    for path in cmds.ls(side+'_*Eyelid*_MTP',type='motionPath'):
        stem=path[:-4]
        radius=math.sqrt(cmds.getAttr(stem+'Horizsq_SUB.input1'))
        point=[cmds.getAttr(stem+'Local_RFM.output'+axis) for axis in 'XYZ']
        rows.append({'path':path,'point':point,'radius':radius,
                     'joint_matrix':cmds.getAttr(stem+'ControlRotation_MMX.matrixSum'),
                     'latitude_ratio':abs(point[1])/radius})
    result['paths'][side]=rows
