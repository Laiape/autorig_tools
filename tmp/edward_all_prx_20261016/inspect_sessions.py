import os,sys
from maya import cmds
assert os.getpid() in (23404,7248,55092)
result={'pid':os.getpid(),'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
        'frame':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True),
        'wraps':{n:cmds.deformer(n,q=True,geometry=True) for n in cmds.ls(type='proximityWrap') or []},
        'pose':{n:{a:cmds.getAttr(n+'.'+a) for a in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ')}
                 for n in ('C_spine03_CTL','C_spine07_CTL','C_localHip_CTL','C_head_CTL','C_masterwalk_CTL') if cmds.objExists(n)},
        'loaded_module':getattr(sys.modules.get('tools.proximity_bake'),'__file__',None)}
