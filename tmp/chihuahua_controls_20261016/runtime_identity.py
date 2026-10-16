import sys
import maya.cmds as cmds
result=dict(scene=cmds.file(q=True,sn=True),runtime={k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith(('quadruped.autorig.tail_module','quadruped.autorig.spine_module','quadruped.autorig.neck_module'))})
