import os
from maya import cmds
assert os.getpid()==23404
skins=cmds.ls(type='skinCluster') or []
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'frame':cmds.currentTime(q=True),
        'skins':{s:cmds.getAttr(s+'.skinningMethod') for s in skins},'wraps':cmds.ls(type='proximityWrap'),
        'selection':cmds.ls(sl=True,long=True)}
