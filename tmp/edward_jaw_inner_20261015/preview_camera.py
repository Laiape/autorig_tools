import json,numpy as np
from pathlib import Path
from maya import cmds
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015/latest')
if not cmds.objExists('EdwardJawReview_CAM'):
    camera,shape=cmds.camera(name='EdwardJawReview_CAM')
else:camera='EdwardJawReview_CAM';shape=cmds.listRelatives(camera,s=True)[0]
position=np.array([32.,194.,42.]);target=np.array([0.,189.,9.])
z=position-target;z/=np.linalg.norm(z);x=np.cross([0,1,0],z);x/=np.linalg.norm(x);y=np.cross(z,x)
matrix=np.eye(4);matrix[0,:3]=x;matrix[1,:3]=y;matrix[2,:3]=z;matrix[3,:3]=position
cmds.xform(camera,ws=True,matrix=matrix.ravel().tolist());cmds.setAttr(shape+'.focalLength',65)
cmds.modelPanel('modelPanel4',edit=True,camera=camera)
cmds.modelEditor('modelPanel4',edit=True,useDefaultMaterial=True,displayTextures=False,nurbsCurves=False,joints=False,grid=False,activeView=True)
cmds.select(clear=True);cmds.refresh(force=True)
result=cmds.playblast(completeFilename=str(WORK/'after_mouth.png'),format='image',compression='png',frame=cmds.currentTime(q=True),viewer=False,offScreen=True,showOrnaments=False,widthHeight=(1318,748),percent=100,forceOverwrite=True)
