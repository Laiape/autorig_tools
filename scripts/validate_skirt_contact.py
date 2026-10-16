"""Native regression and delivery gate for the Nini skirt-contact upgrade.

Run through run_maya_test.py in an owned process. Geometry collection and
contact audits are explicitly outside timing. Failed candidates are retained.
"""
import hashlib
import json
import math
import os
import statistics
import struct
import sys
import time
from pathlib import Path

os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from maya_tools.scripts.tools import skirt_contact as skirt, dress_keepout_chains as dress
from maya_tools.scripts.framework import registry

SOURCE=ROOT/'maya_tools/assets/Nini/scenes/Nini_dress_chains_v005.ma'
FOLDER=ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
version=1
while (FOLDER/('validation_v{:03d}.json'.format(version))).exists():version+=1
REPORT=FOLDER/('validation_v{:03d}.json'.format(version))
DELIVERY=ROOT/'maya_tools/assets/Nini/scenes'/('Nini_skirt_contact_v{:03d}.ma'.format(version))
PRESET=FOLDER/('preset_v{:03d}.json'.format(version))
STAGED=FOLDER/('validated_candidate_v{:03d}.ma'.format(version))
report={'source':str(SOURCE),'candidate':str(STAGED),'delivery':str(DELIVERY),
        'passed':False,'cases':{},'contact_tolerance_cm':.01,'length_ratio_limit':1.05,
        'reference_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(skirt.__file__),Path(dress.__file__),Path(skirt.__file__).with_name('skirt_surface_contact.py'))}}


def record(name,value):
    report['cases'][name]=value
    REPORT.write_text(json.dumps(report,indent=2),encoding='ascii')
    print('SKIRT_VALIDATION='+json.dumps({'case':name,'result':value}),flush=True)


def points(mesh):return dress.mesh_points(mesh)


def error(a,b):return max((math.dist(p,q) for p,q in zip(a,b)),default=0)


def appearance(mesh):
    fn=om.MFnMesh(dress.mesh_path(mesh))
    counts,indices=fn.getVertices()
    uv=fn.getUVs();uv_ids=fn.getAssignedUVs()
    sg,assigned=fn.getConnectedShaders(0)
    material=[om.MFnDependencyNode(sg[i]).name() if i>=0 else '' for i in assigned]
    discrete=repr((list(counts),list(indices),[list(a) for a in uv],
                   [list(a) for a in uv_ids],material)).encode('ascii')
    return {'discrete':hashlib.sha256(discrete).hexdigest(),
            'normals':[tuple(n) for n in fn.getFaceVertexNormals(om.MSpace.kWorld)]}


def skin_digest(skin):
    fn=oma.MFnSkinCluster(om.MSelectionList().add(skin).getDependNode(0))
    mesh=om.MFnDagNode(fn.getOutputGeometry()[0]).getPath()
    comp=om.MFnSingleIndexedComponent();obj=comp.create(om.MFn.kMeshVertComponent)
    comp.addElements(range(om.MFnMesh(mesh).numVertices))
    weights,_=fn.getWeights(mesh,obj)
    blend=fn.getBlendWeights(mesh,obj)
    matrices=[list(cmds.getAttr(skin+'.bindPreMatrix[{}]'.format(fn.indexForInfluenceObject(p))))
              for p in fn.influenceObjects()]
    payload=list(weights)+list(blend)+[v for matrix in matrices for v in matrix]
    digest=hashlib.sha256(struct.pack('<{}d'.format(len(payload)),*payload)).hexdigest()
    return {'digest':digest,'method':cmds.getAttr(skin+'.skinningMethod'),
            'influences':[p.partialPathName() for p in fn.influenceObjects()]}


POSES={'neutral':((0,0,0),(0,0,0)),'left_step':((0,15,18),(0,0,0)),
       'right_step':((0,0,0),(0,15,18)),'both_up':((0,14,15),(0,14,15)),
       'spread':((14,4,0),(-14,4,0)),'held_left':((0,9,12),(0,0,0)),
       'cross_left':((-9,5,7),(2,0,0)),'cross_right':((-2,0,0),(9,5,7))}


def pose(name,fraction=1.0):
    for side,delta in zip(('L','R'),POSES[name]):
        cmds.xform(side+'_ankleIk_CTL',ws=True,t=[a+b*fraction for a,b in zip(rest[side],delta)])


try:
    if DELIVERY.exists():raise FileExistsError(str(DELIVERY))
    cmds.file(str(SOURCE),open=True,force=True)
    cmds.evaluationManager(mode='off')
    data=skirt._data()
    meshes=[g['mesh'] for g in data['garments']]
    rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
    baseline={m:points(m) for m in meshes+['c_body_GEO']}
    looks={m:appearance(m) for m in meshes}
    skins={g['skin']:skin_digest(g['skin']) for g in data['garments']}
    cycles=set(cmds.cycleCheck(all=True,list=True) or [])
    body_poses={}
    cloth_poses={}
    for name in POSES:
        pose(name);body_poses[name]=points('c_body_GEO');cloth_poses[name]={m:points(m) for m in meshes}
    pose('neutral')
    started=time.perf_counter();info=skirt.upgrade();elapsed=time.perf_counter()-started
    cmds.evaluationManager(mode='off')
    after={m:points(m) for m in meshes+['c_body_GEO']}
    assert max(error(baseline[m],after[m]) for m in baseline)<=1e-4
    assert all(skin_digest(s)==value for s,value in skins.items())
    assert all(appearance(m)['discrete']==looks[m]['discrete'] for m in meshes)
    assert max(error(looks[m]['normals'],appearance(m)['normals']) for m in meshes)<1e-4
    assert not (set(cmds.cycleCheck(all=True,list=True) or [])-cycles)
    count=len(cmds.ls());assert skirt.upgrade()['version']==1 and len(cmds.ls())==count
    record('neutral_and_original_data',{'passed':True,'max_error_cm':max(error(baseline[m],after[m]) for m in baseline),
            'skin_bind_DQ_unchanged':True,'topology_UV_materials_unchanged':True,
            'normals_unchanged':True,'idempotent':True,'build_seconds':elapsed,'owned_nodes':info['owned_node_count']})
    snapshots={}
    coverage=[]
    for name in POSES:
        fractions=(0.25,.5,.75,1.0) if name!='neutral' else (1.0,)
        for fraction in fractions:
            pose(name,fraction)
            stats=skirt.check_contact()
            label=name+'_'+str(fraction)
            coverage.append({'pose':label,'stretch':stats['max_stretch_ratio'],
                'lift_cm':stats['max_lift_cm_local'],'passed':stats['passed'],
                'contacts':{m:{'minimum_cm':r['minimum_signed_clearance_cm'],
                               'inside':r['penetrating_vertices'],'uncertain':r['uncertain_vertices']}
                            for m,r in stats['contacts'].items()}})
            if fraction==1.0:
                assert error(points('c_body_GEO'),body_poses[name])<=1e-4
                snapshots[name]={m:points(m) for m in meshes}
            print('SKIRT_COVERAGE='+json.dumps(coverage[-1]),flush=True)
    record('pose_transitions',{'passed':all(row['passed'] for row in coverage),'coverage':coverage})
    assert all(row['passed'] for row in coverage),'A transition failed the unchanged quality contract.'
    mode_rows={}
    for mode in ('serial','parallel'):
        cmds.evaluationManager(mode=mode)
        maximum=0
        for name in reversed(list(POSES)):
            pose(name)
            maximum=max(maximum,max(error(snapshots[name][m],points(m)) for m in meshes))
        fallback=cmds.evaluationManager(q=True,fallbackTriggered=True)
        mode_rows[mode]={'max_error_cm':maximum,'fallback':fallback}
        assert maximum<=1e-4 and not fallback
    record('evaluators_and_reverse_access',{'passed':True,'modes':mode_rows})
    pose('held_left');settings=data['settings']
    cmds.setAttr(settings+'.solverBlend',0)
    assert all(error(points(m),cloth_poses['held_left'][m])<=1e-4 for m in meshes)
    cmds.setAttr(settings+'.solverBlend',1)
    assert all(error(points(m),snapshots['held_left'][m])<=1e-4 for m in meshes)
    ctl=info['controls']['Front'];reference=points(meshes[0])
    cmds.setAttr(ctl+'.translateZ',2)
    assert error(points(meshes[0]),reference)>0.1
    skirt.reset_controls()
    assert error(points(meshes[0]),reference)<=1e-4
    record('manual_controls_and_baseline_switch',{'passed':True})
    pose('neutral');skirt.export_preset(PRESET)
    cmds.setAttr(settings+'.autoLift',.3);skirt.import_preset(PRESET)
    assert cmds.getAttr(settings+'.autoLift')==1
    cmds.setAttr(settings+'.collisionMargin',3.1)
    assert not cmds.getAttr(settings+'.calibrationValid')
    skirt.recalibrate()
    assert cmds.getAttr(settings+'.calibrationValid')
    calibration_errors={m:error(points(m),baseline[m]) for m in meshes}
    assert max(calibration_errors.values())<=1e-4,calibration_errors
    cmds.setAttr(settings+'.collisionMargin',3);skirt.recalibrate()
    pose('held_left')
    try:
        skirt.recalibrate();raise AssertionError('Posed recalibration was accepted.')
    except ValueError:pass
    pose('neutral')
    record('presets_and_recalibration',{'passed':True})
    # Preserve the neutral candidate before independent import/rebuild trials.
    cmds.file(rename=str(STAGED));cmds.file(save=True,type='mayaAscii')
    # Skin round-trip uses the project's exact export/import implementation.
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    manager=SkinManager.__new__(SkinManager)
    manager.k_skin_attrs=['skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution']
    manager.tolerance=1e-5
    skc=FOLDER/('roundtrip_v{:03d}.skc'.format(version))
    cmds.select(list(skins))
    manager.export_skins(str(skc),lossless=True)
    exported=json.loads(skc.read_text())
    actual_entries=[entry for name,entries in exported.items() if not name.startswith('__') for entry in entries]
    assert {e['name'] for e in actual_entries}==set(skins),'Incomplete garment skin export.'
    assert all(e['weight_encoding']=='float64_exact_nonzero' for e in actual_entries)
    manager.import_skins(str(skc),import_method='index',import_wrinkles=False)
    assert all(skin_digest(s)==value for s,value in skins.items())
    assert all(error(points(m),baseline[m])<=1e-4 for m in meshes)
    record('lossless_SKC_roundtrip',{'passed':True,'path':str(skc),'skin_count':len(actual_entries)})
    cmds.file(str(STAGED),open=True,force=True)
    assert all(error(points(m),baseline[m])<=1e-4 for m in meshes)
    pose('held_left');assert all(error(points(m),snapshots['held_left'][m])<=1e-4 for m in meshes)
    record('native_reopen',{'passed':True})
    # A second rebuild starts from the same unmodified calibrated source.
    cmds.file(str(SOURCE),open=True,force=True);cmds.evaluationManager(mode='off')
    skirt.upgrade()
    assert all(skin_digest(s)==value for s,value in skins.items())
    for name in ('neutral','left_step','right_step','cross_left'):
        pose(name);assert all(error(points(m),snapshots[name][m])<=1e-4 for m in meshes)
    record('two_reproducible_builds',{'passed':True})
    # Namespace and rename handling use live message bindings.
    cmds.file(new=True,force=True)
    cmds.file(str(SOURCE),i=True,namespace='wardrobe',preserveReferences=True)
    namespaced=skirt.upgrade('wardrobe:NiniDress_Module_GRP')
    assert namespaced['controls']['Front'].startswith('wardrobe:')
    renamed=cmds.rename(namespaced['controls']['Front'],'wardrobe:RenamedFront_CTL')
    cmds.setAttr(renamed+'.translateZ',1)
    skirt.reset_controls('wardrobe:NiniDress_Module_GRP')
    assert cmds.getAttr(renamed+'.translateZ')==0
    record('namespace_and_renamed_controls',{'passed':True})
    # Deliver only after all gates above; retain the original source separately.
    cmds.file(str(STAGED),open=True,force=True)
    cmds.evaluationManager(mode='parallel')
    pose('neutral')
    cmds.select(data['settings'])
    cmds.file(rename=str(DELIVERY));cmds.file(save=True,type='mayaAscii')
    report['passed']=True
    REPORT.write_text(json.dumps(report,indent=2),encoding='ascii')
    print('SKIRT_DELIVERED='+str(DELIVERY),flush=True)
except BaseException:
    import traceback
    report['error']=traceback.format_exc()
    REPORT.write_text(json.dumps(report,indent=2),encoding='ascii')
    raise
