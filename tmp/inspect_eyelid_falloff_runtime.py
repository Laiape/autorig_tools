import sys
from maya import cmds
result={'modules':{name:getattr(module,'__file__',None) for name,module in sys.modules.items() if name.endswith(('eyelid_module','eyelid_rotation','eyelid_corners'))},'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'pose':{ctl:{a:cmds.getAttr(ctl+'.'+a) for a in ('translate','rotate')} for ctl in cmds.ls('*_eyelid*CTL')},'version':cmds.getAttr('L_upperLidJoined_CRV.eyelidCornerVersion')}
