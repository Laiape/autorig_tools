import numpy as np
from maya.api import OpenMaya as om
from tools import proximity_bake as pb, proximity_wrap as pw
details={}
for short in ('cinturon3','cinturones2'):
    shape=pw.mesh_shape(short)
    details[short]={'shape':shape,'stack':pb.direct_deformers(shape),'matrix':cmds.xform(short,q=True,ws=True,m=True),
                    'skins':{n:cmds.skinCluster(n,q=True,inf=True) for n in cmds.ls(cmds.listHistory(shape) or [],type='skinCluster') or []},
                    'vertices':cmds.polyEvaluate(shape,vertex=True)}
details['controls']={node:{a:cmds.getAttr(node+'.'+a) for a in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ','scaleX','scaleY','scaleZ')}
                     for node in ('C_spine03_CTL','C_spine07_CTL','C_localHip_CTL','C_character_CTL') if cmds.objExists(node)}
details['correctives']={node:{'aliases':cmds.aliasAttr(node,q=True),'weights':cmds.getAttr(node+'.weight')[0],
                             'inputs':cmds.listConnections(node+'.weight',s=True,d=False,p=True,c=True)}
                        for node in cmds.ls(cmds.listHistory('cinturon3') or [],type='blendShape') or []}
details['joints_count']=len(cmds.ls(type='joint'))
details['runtime']=pb.__file__
result=details
