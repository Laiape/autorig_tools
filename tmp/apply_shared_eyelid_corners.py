from importlib import reload
from maya import cmds
from maya_tools.scripts.tools import eyelid_rotation,eyelid_corners,eyelid_contact
from maya_tools.scripts.biped.autorig import eyelid_module
import math
for module in (eyelid_corners,eyelid_rotation,eyelid_contact,eyelid_module):reload(module)
mode=cmds.evaluationManager(q=True,mode=True)[0]
selection=cmds.ls(sl=True,long=True)
cmds.evaluationManager(mode='off')
cmds.undoInfo(openChunk=True,chunkName='Continuous eyelid corners')
try:
    changed=[]
    for prefix in ('L','R'):changed+=eyelid_rotation.install(prefix)
    rows=[]
    for prefix in ('L','R'):
        for index in (0,20):
            a=cmds.xform(prefix+'_upperEyelid0%dSkinning_JNT'%index,q=True,ws=True,t=True)
            b=cmds.xform(prefix+'_downEyelid0%dSkinning_JNT'%index,q=True,ws=True,t=True)
            gap=math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
            if not math.isfinite(gap) or gap>1e-4:raise RuntimeError('Corner gap: %s'%gap)
            rows.append({'side':prefix,'index':index,'gap':gap})
    cmds.select(selection,r=True) if selection else cmds.select(clear=True)
except Exception:
    cmds.undoInfo(closeChunk=True);cmds.undo();raise
else:
    cmds.undoInfo(closeChunk=True)
finally:
    cmds.evaluationManager(mode=mode)
result={'changed':changed,'corners':rows,'pose':cmds.getAttr('L_eyelidDown_CTL.rotate')}
