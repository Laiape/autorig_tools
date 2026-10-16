"""Build a canonical-name DQ SKC from current authoring plus the 23 fitted skins.

All destructive preparation and the import round-trip run in the owned host.
Static pre-skin offsets preserve the fitted copies' bind geometry on model meshes.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from tools import proximity_wrap as pw
from maya_tools.scripts.tools.skin_manager_api import SkinManager
ROOT=Path(r'C:/proyectos/auto-rig')
BASE=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001'
FOLDER=BASE/'dq_20261016_v001'
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid']
manifest=json.loads((BASE/'manifest.json').read_text())
ATTRS=['skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution']


def write(name,value):
    (FOLDER/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')


def manager():
    obj=SkinManager.__new__(SkinManager);obj.k_skin_attrs=ATTRS;obj.tolerance=1e-5
    obj.folder_path=str(ROOT/'autorig_tools/maya_tools/assets/Edward/skin_clusters');obj.asset_name='Edward';obj.ext='.skc'
    return obj


def mesh_fn(mesh):
    shape=pw.mesh_shape(mesh);cmds.dgeval(shape+'.outMesh')
    selection=om.MSelectionList();selection.add(shape)
    return om.MFnMesh(selection.getDagPath(0))


def skin_fn(skin,mesh):
    selection=om.MSelectionList();selection.add(skin);fn=oma.MFnSkinCluster(selection.getDependNode(0))
    selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh));path=selection.getDagPath(0)
    cf=om.MFnSingleIndexedComponent();component=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(mesh_fn(mesh).numVertices)
    return fn,path,component


def arrays(skin,mesh):
    fn,path,component=skin_fn(skin,mesh)
    return np.asarray(fn.getWeights(path,component)[0]).reshape(-1,len(fn.influenceObjects())).copy(),np.asarray(fn.getBlendWeights(path,component)).copy(),[p.fullPathName() for p in fn.influenceObjects()]


def surface(mesh):
    fn=mesh_fn(mesh)
    return np.asarray(fn.getPoints(om.MSpace.kWorld))[:,:3].copy(),np.asarray(fn.getFaceVertexNormals(om.MSpace.kWorld))[:,:3].copy()


def pose(channels):
    for plug in manifest['axes']:cmds.setAttr(plug,channels.get(plug,0))
    for p in ('C_masterwalk_CTL.translateX','C_masterwalk_CTL.rotateY'):cmds.setAttr(p,channels.get(p,0))
    cmds.setAttr('C_masterwalk_CTL.globalScale',channels.get('C_masterwalk_CTL.globalScale',1))
    for side in ('L','R'):
        for limb in ('arm','leg'):cmds.setAttr(side+'_'+limb+'Settings_CTL.Ik_Fk',1)


def prepare_export():
    # Read only clothing DAG APIs before replacing the owned scene with the
    # newest authoring snapshot. No older facial/skin settings are published.
    fitted={}
    for wrap,record in manifest['skin'].items():
        skin=record['skin'];weights,blend,joints=arrays(skin,record['mesh'])
        sel=om.MSelectionList();sel.add(skin+'.input[0].inputGeometry')
        points=np.asarray(om.MFnMesh(sel.getPlug(0).asMObject()).getPoints())[:,:3].copy()
        fitted[wrap]={'weights':weights,'blend':blend,'joints':joints,'points':points,
                      'attributes':{a:cmds.getAttr(skin+'.'+a) for a in ATTRS},
                      'nonrigid':cmds.getAttr(skin+'.dqsSupportNonRigid')}
        assert fitted[wrap]['attributes']['skinningMethod']==1
    cmds.evaluationManager(mode='off')
    cmds.file(str(FOLDER/'Edward_artist_current_before_DQ_export.ma'),open=True,force=True,prompt=False,executeScriptNodes=False)
    other_methods={s:cmds.getAttr(s+'.skinningMethod') for s in cmds.ls(type='skinCluster')}
    pose({});records={}
    for index,(wrap,item) in enumerate(manifest['items'].items()):
        write('progress.json',{'phase':'canonical_DQ_binding','output':index,'total':23})
        source=item['source'];sample=fitted[wrap]
        assert len(sample['points'])==mesh_fn(source).numVertices
        cmds.delete(wrap)
        leaf=source.rsplit('|',1)[-1]
        base_before=np.asarray(mesh_fn(source).getPoints())[:,:3].copy()
        bs=cmds.blendShape(source,name=leaf+'_BakedBindRest_BLS',origin='local')[0]
        scratch=cmds.duplicate(source,name='dqRestScratch',returnRootsOnly=True)[0];cmds.delete(scratch,ch=True)
        mesh_fn(scratch).setPoints(om.MPointArray(np.column_stack((sample['points'],np.ones(len(sample['points'])))).tolist()),om.MSpace.kObject)
        cmds.blendShape(bs,e=True,target=(source,0,scratch,1));cmds.delete(scratch)
        cmds.aliasAttr('bakedBindRest',bs+'.weight[0]');cmds.setAttr(bs+'.weight[0]',1)
        skin=cmds.skinCluster(sample['joints'],source,tsb=True,skinMethod=1,maximumInfluences=8,normalizeWeights=1,name=leaf+'_DQ_SKC')[0]
        for attr,value in sample['attributes'].items():cmds.setAttr(skin+'.'+attr,value)
        cmds.setAttr(skin+'.dqsSupportNonRigid',sample['nonrigid'])
        fn,path,component=skin_fn(skin,source)
        names=[j.fullPathName() for j in fn.influenceObjects()];columns=[sample['joints'].index(j) for j in names]
        cmds.setAttr(skin+'.normalizeWeights',0)
        fn.setWeights(path,component,om.MIntArray(range(len(names))),om.MDoubleArray(sample['weights'][:,columns].ravel().tolist()),False)
        fn.setBlendWeights(path,component,om.MDoubleArray(sample['blend'].tolist()))
        cmds.setAttr(skin+'.normalizeWeights',sample['attributes']['normalizeWeights'])
        history=cmds.listHistory(source) or []
        if history.index(skin)>history.index(bs):cmds.reorderDeformers(bs,skin,source)
        history=cmds.listHistory(source) or [];assert history.index(skin)<history.index(bs)
        check,check_blend,check_names=arrays(skin,source)
        assert np.array_equal(check,sample['weights'][:,columns]) and np.array_equal(check_blend,sample['blend'])
        records[wrap]={'source':source,'shape':pw.mesh_shape(source),'skin':skin,'rest_blendshape':bs,'vertices':len(check),
                       'weights_sha256':hashlib.sha256(check.tobytes()).hexdigest(),'influences':check_names,
                       'max_baked_rest_offset_cm':float(np.linalg.norm(sample['points']-base_before,axis=1).max()),
                       'method':cmds.getAttr(skin+'.skinningMethod')}
    assert not cmds.ls(type='proximityWrap')
    assert all(cmds.getAttr(s+'.skinningMethod')==m for s,m in other_methods.items())
    assert len(cmds.ls(type='joint'))==852
    write('canonical_bindings.json',records)
    return finish_export(records,other_methods)


def finish_export(records=None,other_methods=None):
    if records is None:
        records={}
        for wrap,item in manifest['items'].items():
            source=item['source'];leaf=source.rsplit('|',1)[-1];skin=leaf+'_DQ_SKC';bs=leaf+'_BakedBindRest_BLS'
            weights,blend,joints=arrays(skin,source)
            def base_points(plug):
                sel=om.MSelectionList();sel.add(plug)
                return np.asarray(om.MFnMesh(sel.getPlug(0).asMObject()).getPoints())[:,:3]
            offset=base_points(bs+'.outputGeometry[0]')-base_points(bs+'.input[0].inputGeometry')
            records[wrap]={'source':source,'shape':pw.mesh_shape(source),'skin':skin,'rest_blendshape':bs,'vertices':len(weights),
                           'weights_sha256':hashlib.sha256(weights.tobytes()).hexdigest(),'influences':joints,
                           'max_baked_rest_offset_cm':float(np.linalg.norm(offset,axis=1).max()),'method':cmds.getAttr(skin+'.skinningMethod')}
        new_skins={r['skin'] for r in records.values()}
        other_methods={s:cmds.getAttr(s+'.skinningMethod') for s in cmds.ls(type='skinCluster') if s not in new_skins}
    # Only stale routes to the deliberately removed PRX are retired. Authored
    # fields, masks, depth controls and every surviving detail consumer remain.
    removed_routes=[]
    for settings in cmds.ls('*_Settings',type='transform') or []:
        if not cmds.attributeQuery('wrinklePrimaryConsumers',node=settings,exists=True):continue
        plug=settings+'.wrinklePrimaryConsumers';routes=json.loads(cmds.getAttr(plug) or '{}')
        for destination in list(routes):
            if destination.split('.')[0] in manifest['items']:
                removed_routes.append({'settings':settings,'destination':destination,'route':routes.pop(destination)})
        cmds.setAttr(plug,json.dumps(routes),type='string')
    pose({});cmds.select(clear=True)
    native=FOLDER/'Edward_all_PRX_DQ_canonical_v002.ma';assert not native.exists()
    cmds.file(rename=str(native));cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
    staged=FOLDER/'Edward_DQ_staged.skc';assert not staged.exists()
    obj=manager();obj.export_skins(str(staged),lossless=True)
    package=json.loads(staged.read_text());meta=package[obj.SCENE_DEFORMERS_KEY]
    assert not any(n['type']=='proximityWrap' for n in meta['nodes'])
    assert not any('_ALLPRX_' in key for key in package)
    keys={}
    for wrap,record in records.items():
        key=next(k for k,v in package.items() if not k.startswith('__') and any(e['name']==record['skin'] for e in v))
        entry=next(e for e in package[key] if e['name']==record['skin']);assert entry['attributes']['skinningMethod']==1
        keys[wrap]=key
    data={'records':records,'keys':keys,'native_scene':str(native),'staged_skc':str(staged),
          'other_methods':other_methods,'skin_count':len(cmds.ls(type='skinCluster')),
          'wrinkles_present':bool(package.get(obj.WRINKLES_KEY)),'retired_prx_detail_routes':removed_routes,
          'runtime':__import__('maya_tools.scripts.tools.skin_manager_api',fromlist=['']).__file__}
    write('canonical_export.json',data)
    return {'skins_DQ':len(records),'all_skin_nodes':data['skin_count'],'staged_skc':str(staged),'native_scene':str(native),'wrinkles_present':data['wrinkles_present']}


def roundtrip():
    data=json.loads((FOLDER/'canonical_export.json').read_text());records=data['records'];obj=manager()
    package=json.loads(Path(data['staged_skc']).read_text())
    cases=[{'name':'neutral','channels':{}},
           {'name':'torso','channels':{'C_spine03_CTL.rotateY':-20,'C_localChest_CTL.rotateZ':15}},
           {'name':'arms','channels':{'L_shoulderFk_CTL.rotateZ':70,'R_shoulderFk_CTL.rotateY':35}},
           {'name':'legs','channels':{'L_hipFk_CTL.rotateX':25,'R_hipFk_CTL.rotateZ':55,'L_ankleFk_CTL.rotateX':20}},
           {'name':'neck','channels':{'C_neck_CTL.rotateY':25,'C_head_CTL.rotateZ':15}},
           {'name':'global','channels':{'C_masterwalk_CTL.translateX':12,'C_masterwalk_CTL.rotateY':25}},
           {'name':'scale','channels':{'C_masterwalk_CTL.globalScale':1.15}}]
    baseline={}
    weights_before={w:arrays(r['skin'],r['source']) for w,r in records.items()}
    for case in cases:
        pose(case['channels']);baseline[case['name']]={w:surface(r['source']) for w,r in records.items()}
    pose({})
    subset={data['keys'][w]:copy.deepcopy(package[data['keys'][w]]) for w in records}
    rest_nodes={r['rest_blendshape'] for r in records.values()};skin_nodes={r['skin'] for r in records.values()}
    metadata=copy.deepcopy(package[obj.SCENE_DEFORMERS_KEY])
    metadata['nodes']=[n for n in metadata['nodes'] if n['name'] in rest_nodes|skin_nodes]
    metadata['geometry_stacks']={r['shape']:[r['rest_blendshape'],r['skin']] for r in records.values()}
    for name in ('auxiliary_nodes','pose_targets','orientation_systems','detail_modes'):metadata[name]=[]
    subset[obj.SCENE_DEFORMERS_KEY]=metadata
    portable=bool(globals().get('TRIAL_ARGUMENTS',{}).get('portable'))
    partial=FOLDER/('DQ_roundtrip_subset_portable.skc' if portable else 'DQ_roundtrip_subset.skc');assert not partial.exists()
    with partial.open('x') as stream:json.dump(subset,stream,separators=(',',':'))
    for record in records.values():cmds.delete(record['skin'])
    for record in records.values():cmds.delete(record['rest_blendshape'])
    if portable:
        for record in records.values():
            shape=pw.mesh_shape(record['source'])
            cmds.rename(shape,record['source'].rsplit('|',1)[-1]+'_ModelShapeRoundtrip')
    obj.import_skins(str(partial),replace_existing=True,import_wrinkles=False)
    rows=[];max_error=0.;max_normal=0.
    for case in cases+list(reversed(cases)):
        pose(case['channels'])
        for wrap,record in records.items():
            p,n=surface(record['source']);a,b=baseline[case['name']][wrap]
            error=float(np.linalg.norm(p-a,axis=1).max());normal=float(np.linalg.norm(n-b,axis=1).max())
            rows.append({'pose':case['name'],'wrap':wrap,'max_position_cm':error,'max_face_vertex_normal':normal})
            max_error=max(max_error,error);max_normal=max(max_normal,normal)
    weight_errors=[]
    for wrap,record in records.items():
        w,b,names=arrays(record['skin'],record['source']);a,ab,anames=weights_before[wrap]
        columns=[anames.index(n) for n in names]
        weight_errors.append(float(np.abs(w-a[:,columns]).max()))
        assert np.array_equal(b,ab) and cmds.getAttr(record['skin']+'.skinningMethod')==1
    pose({})
    result={'poses':len(cases),'comparisons':len(rows),'max_position_cm':max_error,'max_face_vertex_normal':max_normal,
            'max_weight_error':max(weight_errors),'tolerance_cm':1e-4,'rows':rows,
            'passed':max_error<=1e-4 and max_normal<=1e-4 and max(weight_errors)==0.}
    write('roundtrip_portable.json' if portable else 'roundtrip.json',result)
    assert result['passed'], 'DQ package import changed weights or output; do not publish'
    return {k:v for k,v in result.items() if k!='rows'}


def portable_keys():
    data=json.loads((FOLDER/'canonical_export.json').read_text())
    package=json.loads(Path(data['staged_skc']).read_text())
    for wrap,record in data['records'].items():
        old=data['keys'][wrap];new=record['source']
        assert new not in package
        package[new]=package.pop(old);data['keys'][wrap]=new
    target=FOLDER/'Edward_DQ_portable_staged.skc';assert not target.exists()
    with target.open('x') as stream:json.dump(package,stream,separators=(',',':'),allow_nan=False)
    data['raw_staged_skc']=data['staged_skc'];data['staged_skc']=str(target)
    write('canonical_export.json',data)
    return {'portable_transform_keys':len(data['keys']),'staged_skc':str(target)}


action=globals().get('TRIAL_ARGUMENTS',{}).get('action','export')
result={'export':prepare_export,'resume_export':finish_export,'roundtrip':roundtrip,'portable':portable_keys}[action]()
