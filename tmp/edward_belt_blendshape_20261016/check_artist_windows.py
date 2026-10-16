import os
from pathlib import Path
from maya import cmds, OpenMaya as om, OpenMayaUI as omui
assert os.getpid() in (7248,55092)
folder=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
image_path=folder/('artist_window_%d.png'%os.getpid())
view=omui.M3dView.active3dView()
pixels=om.MImage();view.readColorBuffer(pixels,True);pixels.writeToFile(str(image_path),'png')
result={'pid':os.getpid(),'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
        'selector':cmds.getAttr('Edward_BeltBlendshape_Review.beltVariant'),'viewport':[view.portWidth(),view.portHeight()],
        'visible_candidates':{n:cmds.getAttr(n+'.visibility') for n in cmds.ls('*TEST',type='transform')},
        'image':str(image_path),'joints':len(cmds.ls(type='joint'))}
