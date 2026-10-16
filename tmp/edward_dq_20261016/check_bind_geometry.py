import json,os
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
assert os.getpid()==55092
folder=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001')
manifest=json.loads((folder/'manifest.json').read_text())
def data_points(plug):
    sel=om.MSelectionList();sel.add(plug)
    return np.asarray(om.MFnMesh(sel.getPlug(0).asMObject()).getPoints())[:,:3]
records=[]
for wrap,record in manifest['skin'].items():
    skin=record['skin']
    a=data_points(wrap+'.input[0].inputGeometry')
    b=data_points(skin+'.input[0].inputGeometry')
    records.append({'wrap':wrap,'skin':skin,'max_rest_offset':float(np.linalg.norm(a-b,axis=1).max())})
result=records
