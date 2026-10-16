import sys
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
sys.path.insert(0,'C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts')
cmds.loadPlugin('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/plug-ins/2026/ngSkinTools2.mll')
from ngSkinTools2 import api
m=cmds.polyPlane(sx=1,sy=1)[0]
j=[cmds.createNode('joint') for _ in range(3)]
s=cmds.skinCluster(j,m,tsb=True)[0]
l=api.init_layers(s).add('base')
def dump(label):
 print(label,{i:l.get_weights(i) for i in [0,1,2,'mask','dq']},flush=True)
dump('initial')
with api.suspend_updates(s):
 for i,w in enumerate([.2,.3,.5]):l.set_weights(i,[w]*4,undo_enabled=False)
dump('set .2 .3 .5')
l.set_weights(0,[1.0]*4,undo_enabled=False)
dump('set 1')
with api.suspend_updates(s):
 for i,w in enumerate([.2,.3,.5]):l.set_weights(i,[w]*4,undo_enabled=False)
dump('restore .2 .3 .5')
l.locked_influences=[1]
l.set_weights(0,[1.0]*4,undo_enabled=False)
dump('locked1 paint0')
print('locked',l.locked_influences)
maya.standalone.uninitialize()
