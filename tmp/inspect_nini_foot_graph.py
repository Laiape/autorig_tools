from maya import cmds
from maya.api import OpenMaya as om
import math
def pos(p):
 return list(om.MTransformationMatrix(om.MMatrix(cmds.getAttr(p))).translation(om.MSpace.kWorld))
result={}
for side in ('L','R'):
 nodes=cmds.ls(side+'_*IkHandleManager*')+cmds.ls(side+'_*ballIk*SC*')+cmds.ls(side+'_*toeIk*SC*')
 result[side]={'nodes':{n:cmds.listConnections(n,s=True,d=False,p=True,c=True) for n in nodes},'matrices':{}}
 for node in [side+'_ankle_BM',side+'_ball_BM',side+'_legToe_ENV',side+'_legBallBase_MMX']:
  plug=node+('.outputMatrix' if node.endswith('_BM') else '.matrixSum' if node.endswith('MMX') else '.worldMatrix[0]')
  result[side]['matrices'][plug]=pos(plug)
 for node in cmds.ls(side+'_*IkHandleManager*'):
  result[side]['matrices'][node+'.matrixSum']=pos(node+'.matrixSum')
 result[side]['blend_sources']={n:cmds.listConnections(n+'.inputMatrix',s=True,d=False,p=True) for n in (side+'_ankle_BM',side+'_ball_BM',side+'_toe_BM') if cmds.objExists(n)}
