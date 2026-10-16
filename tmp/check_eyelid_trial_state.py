from maya import cmds
result={'undo':cmds.undoInfo(q=True,state=True),'queue':cmds.undoInfo(q=True,undoName=True),'pose':cmds.getAttr('L_eyelidDown_CTL.rotate'),'joined':cmds.connectionInfo('L_upperLidJoined_CRVShape.controlPoints[0].xValue',sourceFromDestination=True),'nodes':len(cmds.ls())}
