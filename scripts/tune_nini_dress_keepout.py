"""Tune sparse chain clearance against the real body before final save."""
import json,os,sys
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import dress_keepout_chains as tool,rig_surface_contact as audit
directory=ROOT/'maya_tools/assets/Nini/experiments/dress_keepout'
cmds.file(str(directory/'Nini_dress_chains_v002.ma'),open=True,force=True)
data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
cmds.evaluationManager(mode='off')
rest={side:cmds.xform(side+'_ankleIk_CTL',q=True,ws=True,t=True) for side in ('L','R')}
result=[]
poses=[((0,0,0),(0,0,0)),((0,15,18),(0,0,0)),((0,0,0),(0,15,18)),((0,14,15),(0,14,15)),((14,4,0),(-14,4,0))]
for margin in (2.3,3.0,3.7):
    cmds.setAttr('C_dressSettings_CTL.collisionMargin',margin)
    for index,pose in enumerate(poses):
        for side,delta in zip(('L','R'),pose): cmds.xform(side+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[side],delta)])
        info=tool.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],'c_body_GEO')
        points=tool.mesh_points('c_tunic_GEO')
        fn=om.MFnMesh(tool.mesh_path('c_body_GEO'))
        details=[]
        for vertex in info['penetrating_vertices']+info['uncertain_vertices']:
            point=om.MPoint(*points[vertex]);closest,normal,_=fn.getClosestPointAndNormal(point,om.MSpace.kWorld)
            details.append({'vertex':vertex,'point':points[vertex],'closest':tuple(closest)[:3],'normal_sign':om.MVector(point-closest)*normal,'alpha':data['garments'][0]['alpha'][vertex]})
        result.append({'margin':margin,'pose':index,'contact':info,'details':details})
        print(json.dumps(result[-1]),flush=True)
(directory/'tuning.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
maya.standalone.uninitialize()
