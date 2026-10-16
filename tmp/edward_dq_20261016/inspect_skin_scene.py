import os
from maya import cmds
assert os.getpid()==55092
result={'pid':os.getpid(),'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
        'frame':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True),
        'skins':{s:{'method':cmds.getAttr(s+'.skinningMethod'),'geometry':cmds.skinCluster(s,q=True,geometry=True)} for s in cmds.ls(type='skinCluster')},
        'method_enum':cmds.attributeQuery('skinningMethod',node=cmds.ls(type='skinCluster')[0],listEnum=True)}
