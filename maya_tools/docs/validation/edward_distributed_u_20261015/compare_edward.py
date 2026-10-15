"""Disposable native Edward comparison and software-rendered lip references."""
import hashlib,importlib.abc,importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'maya_tools/docs/validation/edward_distributed_u_20261015'
OUT.mkdir(parents=True,exist_ok=True)
(ROOT/'.git/edward_u_revision').mkdir(parents=True,exist_ok=True)
os.environ['MAYA_SKIP_USERSETUP_PY']='1';os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['AUTORIG_BUILD_CACHE_DIR']=str(ROOT/'.git/auto_wide_edward/cache')
sys.path[:0]=[str(ROOT),str(ROOT/'maya_tools/scripts')]
from PySide6 import QtWidgets
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
from mesh_intersections import crossings
SOURCE=ROOT/'maya_tools/scripts/biped/autorig/jaw_module_nurbs.py'
active=SOURCE
class SourceFinder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path,target=None):
        if fullname=='maya_tools.scripts.biped.autorig.jaw_module_nurbs':
            return importlib.util.spec_from_file_location(fullname,str(active))
finder=SourceFinder();sys.meta_path.insert(0,finder)
from maya_tools.scripts.utils import create_rig
from maya_tools.scripts.framework import context
context.service().set_asset('Edward');cmds.optionVar(stringValue=('currentAssetRigName','Edward'))
meshes=('cabeza_high','cabeza_low','cuerpo_base')
unchanged=[('neutral',{}),('jaw20',{'C_jaw_CTL.rx':20}),('jaw30',{'C_jaw_CTL.rx':30}),
           ('upper',{'C_jaw_CTL.rx':20,'C_upperLip_CTL.ty':1}),
           ('lower',{'C_jaw_CTL.rx':20,'C_lowerLip_CTL.ty':-1}),
           ('sticky',{'C_jaw_CTL.rx':30,'C_jaw_CTL.stickyLips':1}),
           ('mouth',{'C_mainMouth_CTL.tx':1,'C_mainMouth_CTL.ry':14})]
changed=[('wide0',{'C_jaw_CTL.rx':0,'L_lipCorner_CTL.tx':-1,'R_lipCorner_CTL.tx':-1}),
         ('wide20',{'C_jaw_CTL.rx':20,'L_lipCorner_CTL.tx':-1,'R_lipCorner_CTL.tx':-1})]
for angle in (0,20,30):
    changed.append(('U'+str(angle),{'C_jaw_CTL.rx':angle,'L_lipCorner_CTL.tx':5.2,
                    'R_lipCorner_CTL.tx':5.2,'L_lipCorner_CTL.ty':2,'R_lipCorner_CTL.ty':2}))
unchanged += changed[:2]
changed = changed[2:]
for angle in (0,1.25,2.5,3.75,5,7.5,10,15,20,30):
    for x in (2.6,5.2):
        for y in (1,2):
            changed.append(('grid_%s_%s_%s'%(angle,x,y),{'C_jaw_CTL.rx':angle,'L_lipCorner_CTL.tx':x,'R_lipCorner_CTL.tx':x,'L_lipCorner_CTL.ty':y,'R_lipCorner_CTL.ty':y}))
cases=unchanged+changed
report=dict(success=False,baseline_ref='a88f90d',source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            maya_version=cmds.about(version=True),maya_api=cmds.about(apiVersion=True),
            center_gain=.3,arc_power=2,center_jaw_fade_degrees=None,
            unchanged_pose_count=len(unchanged),u_pose_count=len(changed),
            measurement='CPU mesh/world matrix geometry and native Maya software reference renders. Private batch scenes; no artist scene changes or viewport FPS claim.',variants={},cases=[])

def render_setup():
    head=cmds.listRelatives('cabeza_high',shapes=True,noIntermediate=True,fullPath=True)[0]
    for mesh in cmds.ls(type='mesh',long=True):
        if mesh!=head and not cmds.getAttr(mesh+'.intermediateObject'):
            try:cmds.setAttr(mesh+'.visibility',0)
            except RuntimeError:pass
    cmds.setAttr(head+'.visibility',1)
    shader=cmds.shadingNode('lambert',asShader=True,name='ValidationGray')
    cmds.setAttr(shader+'.color',.55,.55,.55,type='double3')
    group=cmds.sets(renderable=True,noSurfaceShader=True,empty=True)
    cmds.connectAttr(shader+'.outColor',group+'.surfaceShader');cmds.sets(head,edit=True,forceElement=group)
    camera,shape=cmds.camera(name='ValidationCamera',focalLength=90)
    cmds.setAttr(camera+'.translate',25,193,50)
    target=cmds.createNode('transform');cmds.setAttr(target+'.translate',0,187.5,10)
    cmds.delete(cmds.aimConstraint(target,camera,aimVector=(0,0,-1),upVector=(0,1,0)))
    for camera_shape in cmds.ls(type='camera'):cmds.setAttr(camera_shape+'.renderable',camera_shape==shape)
    cmds.setAttr(shape+'.backgroundColor',.16,.16,.16,type='double3')
    light=cmds.directionalLight(intensity=1.0)
    cmds.setAttr(cmds.listRelatives(light,parent=True)[0]+'.rotate',-25,-30,0)
    cmds.ambientLight(intensity=.3)
    cmds.setAttr('defaultRenderGlobals.currentRenderer','mayaSoftware',type='string')
    cmds.setAttr('defaultRenderGlobals.imageFormat',32)
    cmds.setAttr('defaultRenderQuality.edgeAntiAliasing',1)
    return camera

try:
    with tempfile.TemporaryDirectory(prefix='u_center_compare_') as directory:
        old=Path(directory)/'jaw_before.py'
        old.write_bytes(subprocess.check_output(['git','show','a88f90d:maya_tools/scripts/biped/autorig/jaw_module_nurbs.py'],cwd=ROOT))
        reference=None;current_data=None;orientation_failures=[]
        for label,active in (('before',old),('after',SOURCE)):
            create_rig.AutoRig().build();cmds.evaluationManager(mode='off')
            assert all(not cmds.objExists(s+'_lipCorner_CTL.autoWideRoll') for s in ('L','R'))
            report['variants'][label]=dict(scene_nodes=len(cmds.ls()),source_sha256=hashlib.sha256(active.read_bytes()).hexdigest())
            fns=[];triangles=[]
            for mesh in meshes:
                shape=cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True)[0]
                fn=om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0));fns.append(fn)
                triangles.append(np.array(fn.getTriangles()[1],dtype=int).reshape(-1,3))
            defaults={p:cmds.getAttr(p) for _,case in cases for p in case}
            if label=='after':
                cmds.file(rename=str(ROOT/'.git/edward_u_revision/distributed_final.mb'));cmds.file(save=True,type='mayaBinary',force=True)
            def pose(values):
                for p,v in defaults.items():cmds.setAttr(p,v)
                for p,v in values.items():cmds.setAttr(p,v)
            data={}
            for name,values in cases:
                pose(values)
                data[name]=[np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)]) for fn in fns]
                assert all(np.isfinite(p).all() for p in data[name]),name
            if reference is None:
                reference=data
                np.savez_compressed(ROOT/'.git/edward_u_revision/restored_reference.npz',**{name+'__'+mesh:p for name,rows in data.items() for mesh,p in zip(meshes,rows)})
            else:
                current_data=data
                for name,_ in cases:
                    row=dict(pose=name,meshes={})
                    for mesh,a,b,tri in zip(meshes,reference[name],data[name],triangles):
                        error=float(np.abs(a-b).max())
                        n0=np.cross(a[tri[:,1]]-a[tri[:,0]],a[tri[:,2]]-a[tri[:,0]])
                        n1=np.cross(b[tri[:,1]]-b[tri[:,0]],b[tri[:,2]]-b[tri[:,0]])
                        moved=np.linalg.norm(b-a,axis=1)>1e-7
                        flipped=(np.sum(n0*n1,axis=1)<0)&(np.linalg.norm(n0,axis=1)>1e-8)&moved[tri].any(axis=1)
                        row['meshes'][mesh]=dict(maximum_vertex_error=error,new_triangle_reversals=int(flipped.sum()))
                        active=np.flatnonzero(moved[tri].any(axis=1))
                        nondegenerate=np.linalg.norm(n0,axis=1)>1e-8
                        collapsed=(np.linalg.norm(n1,axis=1)<1e-10)&nondegenerate
                        assert not collapsed.any(),(name,mesh,'collapsed triangles')
                        if name in ('U0','U20','U30','grid_0_2.6_1') and mesh!='cuerpo_base':
                            old_crossings=crossings(a,tri,active);new_crossings=crossings(b,tri,active)
                            row['meshes'][mesh]['crossings_before']=len(old_crossings)
                            row['meshes'][mesh]['crossings_after']=len(new_crossings)
                            row['meshes'][mesh]['new_crossings']=len(new_crossings-old_crossings)
                        if name in {n for n,_ in unchanged} or mesh=='cuerpo_base':assert error<1e-6,(name,mesh,error)
                        if flipped.any():orientation_failures.append(dict(pose=name,mesh=mesh,triangles=np.flatnonzero(flipped).tolist()))
                    report['cases'].append(row)
            camera=render_setup()
            for name,values in changed:
                if name not in ('U0','grid_0_2.6_1'):continue
                pose(values)
                cmds.setAttr('defaultRenderGlobals.imageFilePrefix',str(OUT/(name+'_'+label)),type='string')
                print('REFERENCE_RENDER',cmds.render(camera,x=960,y=720),flush=True)
            print('EDWARD_VARIANT',label,'COMPLETE',flush=True)
        report['orientation_failures']=orientation_failures
        report['normal_rotation_note']='Intentional arc changes can rotate triangle normals beyond 90 degrees. These counts are diagnostic, not an inversion test. Collapsed triangles and strict non-adjacent crossings are checked separately.'
        report['success']=True
finally:
    sys.meta_path.remove(finder)
    (OUT/'edward_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PASS Edward before/after: unchanged neutral/general poses, unchanged forward Wide and central U follow, finite meshes and separate contact diagnostics',flush=True)
