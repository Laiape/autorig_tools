"""Audit saved Edward geometry and corrective activations in a private Maya."""
import os,sys,json,hashlib
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'maya_tools/docs/validation/edward_distributed_u_20261015';OUT.mkdir(exist_ok=True)
os.environ['MAYA_SKIP_USERSETUP_PY']='1';os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(ROOT),str(ROOT/'maya_tools/scripts')]
import maya.standalone
if not os.environ.get('EDWARD_AUDIT_INITIALIZED'):maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
from maya_tools.scripts.tools import pose_blendshapes as tool
snapshot=Path(os.environ.get('EDWARD_AUDIT_SCENE',ROOT/'.git/edward_u_revision/distributed_final.mb'))
cmds.file(str(snapshot),open=True,force=True);cmds.evaluationManager(mode='off')
def points(mesh):
    shape=cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True)[0]
    fn=om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0))
    return np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)])
report=dict(snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),nodes=[],errors=[])
records=tool._find(tool.POSE_MARKER)
reset={}
for record in records:
    controller=tool.linked(record,'controller')
    if controller:
        for item in json.loads(cmds.getAttr(record+'.channels')):
            reset[controller+'.'+item['channel']]=item['default']
def neutral():
    for plug,value in reset.items():
        if cmds.getAttr(plug,settable=True):cmds.setAttr(plug,value)
neutral()
for bs in cmds.ls(type='blendShape'):
    row=dict(node=bs,envelope=cmds.getAttr(bs+'.envelope'),state=cmds.getAttr(bs+'.nodeState'),
             geometries=cmds.blendShape(bs,q=True,geometry=True),targets=[],
             outputs=cmds.listConnections(bs+'.outputGeometry',s=False,d=True,p=True) or [])
    meshes=[cmds.listRelatives(shape,parent=True,fullPath=True)[0] for shape in row['geometries']]
    for index,name in tool.targets(bs):
        neutral();plug=bs+'.weight[%d]'%index;record=tool.pose_record(bs,index)
        item=dict(index=index,name=name,neutral_weight=cmds.getAttr(plug),
                  connection=cmds.connectionInfo(plug,sourceFromDestination=True),record=record)
        if record:
            controller=tool.linked(record,'controller');values=json.loads(cmds.getAttr(record+'.channels'))
            meshes=[tool.linked(record,'mesh')]
            item['geometry_index']=tool.geometry_index(bs,meshes[0])
            item.update(controller=controller,channels=values,samples=[])
            for fraction in (0,.25,.5,.75,1,1.5,-.5):
                neutral()
                for value in values:
                    cmds.setAttr(controller+'.'+value['channel'],value['default']+(value['pose']-value['default'])*fraction)
                weight=cmds.getAttr(plug)
                item['samples'].append(dict(fraction=fraction,weight=weight))
            neutral()
            for value in values:cmds.setAttr(controller+'.'+value['channel'],value['pose'])
            active=[points(mesh) for mesh in meshes]
            source=item['connection']
            if source:cmds.disconnectAttr(source,plug)
            weight=cmds.getAttr(plug);cmds.setAttr(plug,0)
            off=[points(mesh) for mesh in meshes]
            cmds.setAttr(plug,weight)
            if source:cmds.connectAttr(source,plug,force=True)
            item['full_contribution']={mesh:float(np.linalg.norm(a-b,axis=1).max()) for mesh,a,b in zip(meshes,active,off)}
            item['affected_vertices']={mesh:int(np.sum(np.linalg.norm(a-b,axis=1)>1e-6)) for mesh,a,b in zip(meshes,active,off)}
        elif row['geometries'] and cmds.nodeType(row['geometries'][0])=='mesh' and cmds.getAttr(plug,settable=True):
            meshes=[cmds.listRelatives(row['geometries'][0],parent=True,fullPath=True)[0]]
            active=points(meshes[0]);weight=cmds.getAttr(plug);cmds.setAttr(plug,0)
            off=points(meshes[0]);cmds.setAttr(plug,weight)
            item['constant_target_contribution']=float(np.linalg.norm(active-off,axis=1).max())
        row['targets'].append(item)
    report['nodes'].append(row)
neutral()
if os.environ.get('EDWARD_AUDIT_VALIDATE','1'):
    managed=[t for n in report['nodes'] for t in n['targets'] if t['record']]
    assert len(managed)==10
    for item in managed:
        assert item['geometry_index']==0
        assert all(v>1e-5 for v in item['full_contribution'].values()),item['name']
        assert abs(item['samples'][0]['weight'])<1e-6,item['name']
        for sample in item['samples'][1:5]:
            assert abs(sample['weight']-sample['fraction'])<1e-5,(item['name'],sample)
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    exported=SkinManager.__new__(SkinManager)._export_scene_deformers()
    head=next(n for n in exported['nodes'] if n['name']=='cabeza_high_poseCorrectives_BLS')
    assert cmds.nodeType(head['geometries'][0]['shape'])=='mesh'
    report['canonical_reexport_geometry']=head['geometries']
    report['pose_count_reexport']=len(exported['pose_targets'])
    compare_meshes=('cabeza_high','cabeza_low')
    for plug,value in {'C_jaw_CTL.rx':20,'L_lipCorner_CTL.tx':2.6,'R_lipCorner_CTL.tx':2.6,'L_lipCorner_CTL.ty':1,'R_lipCorner_CTL.ty':1}.items():cmds.setAttr(plug,value)
    reference=[points(m) for m in compare_meshes]
    report['evaluation_errors']={}
    for mode in ('serial','parallel','off'):
        cmds.evaluationManager(mode=mode)
        error=max(float(np.abs(points(m)-p).max()) for m,p in zip(compare_meshes,reference))
        assert error<1e-4,(mode,error)
        report['evaluation_errors'][mode]=error
    roundtrip=ROOT/'.git/edward_u_revision/verified_roundtrip.mb';cmds.file(rename=str(roundtrip));cmds.file(save=True,type='mayaBinary',force=True)
    cmds.file(str(roundtrip),open=True,force=True)
    report['reopen_error']=max(float(np.abs(points(m)-p).max()) for m,p in zip(compare_meshes,reference))
    assert report['reopen_error']<1e-4,report['reopen_error']
    report['success']=True
(OUT/os.environ.get('EDWARD_AUDIT_REPORT','correctives_after.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
