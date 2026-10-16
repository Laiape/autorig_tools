"""Owned all-PRX bake experiment: capture, native targets, fitted skins, review.

This is a finite-pose approximation on comparison copies, never CREATE RIG.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from tools import proximity_wrap as pw, proximity_bake as pb
ROOT=Path(r'C:/proyectos/auto-rig')
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001'
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Owned trial only'
assert cmds.about(batch=True)


def write(name,value):
    (FOLDER/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')


def progress(phase,**values):write('progress.json',dict(phase=phase,**values))


def fn(mesh):
    selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh))
    return om.MFnMesh(selection.getDagPath(0))


def points(mesh):
    shape=pw.mesh_shape(mesh);cmds.dgeval(shape+'.outMesh')
    return np.asarray(fn(shape).getPoints(om.MSpace.kWorld))[:,:3].copy()


def apply(case,axes):
    for p in axes:cmds.setAttr(p,case.get(p,0))


def switches():
    return {s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk')
            for s in ('L','R') for limb in ('arm','leg')}


def capture():
    previous=json.loads((ROOT/'tmp/edward_wrap_bake_20261015/wrap_sample_plan.json').read_text())
    axes={}
    for case in previous['fit']:
        if len(case['channels'])!=1:continue
        p,v=next(iter(case['channels'].items()))
        axes.setdefault(p,[0,0]);axes[p]=[min(axes[p][0],v),max(axes[p][1],v)]
    for node in ('C_spine00_CTL','C_localChest_CTL','C_localHip_CTL'):
        for channel in ('rotateX','rotateY','rotateZ'):axes[node+'.'+channel]=[-25,25]
    for node in ('C_spine00_CTL','C_spine03_CTL','C_spine07_CTL','C_localChest_CTL','C_localHip_CTL'):
        for channel in ('translateX','translateY','translateZ'):axes[node+'.'+channel]=[-4,4]
    axes={p:v for p,v in axes.items() if cmds.objExists(p) and cmds.getAttr(p,settable=True)}
    fit=[{'name':'neutral','channels':{}}];held=[]
    for p,limits in axes.items():
        for value in limits:
            if value:fit.append({'name':p.replace('.','_')+'_%g'%value,'channels':{p:value}})
        for side,factor in ((0,.37),(1,.73)):
            value=limits[side]*factor
            if value:held.append({'name':'held_'+p.replace('.','_')+'_%g'%value,'channels':{p:value}})
    rng=np.random.default_rng(1610202601)
    for i in range(24):
        chosen=rng.choice(list(axes),4,replace=False)
        held.append({'name':'held_combination_%02d'%i,'channels':{p:float(rng.uniform(*axes[p]))*.55 for p in chosen}})
    items={};seen=set()
    for wrap in cmds.ls(type='proximityWrap') or []:
        geometry=cmds.deformer(wrap,q=True,geometry=True) or []
        assert len(geometry)==1, 'Record a multi-output wrap explicitly'
        shape=pw.mesh_shape(geometry[0]);assert shape not in seen
        seen.add(shape);mesh=cmds.listRelatives(shape,p=True,f=True)[0]
        template=previous['targets'][wrap]
        joints=[j for j in template['joints'] if cmds.objExists(j)]
        assert joints and len(joints)==len(template['joints'])
        direct=pw.direct_deformers(shape,('skinCluster','proximityWrap','blendShape','deltaMush'))
        items[wrap]={'source':mesh,'shape':shape,'vertices':fn(shape).numVertices,'joints':joints,
                     'driver_inputs':cmds.listConnections(wrap+'.drivers',s=True,d=False,p=True) or [],
                     'direct_deformers':[n for n,_ in direct],
                     'consumers':cmds.listConnections(shape+'.worldMesh',s=False,d=True,p=True) or [],
                     'neutral_world_matrix':cmds.xform(mesh,q=True,ws=True,m=True)}
    alljoints=list(dict.fromkeys(j for item in items.values() for j in item['joints']))
    saved={p:cmds.getAttr(p) for p in axes};mode=switches()
    sample={w:[] for w in items};matrices=[];start=time.perf_counter()
    try:
        for p in mode:cmds.setAttr(p,1)
        for index,case in enumerate(fit+held):
            apply(case['channels'],axes)
            for wrap,item in items.items():sample[wrap].append(points(item['source']))
            matrices.append([cmds.xform(j,q=True,ws=True,m=True) for j in alljoints])
            if index%10==0:progress('capture',pose=index,total=len(fit+held),seconds=time.perf_counter()-start)
        arrays={w:np.asarray(values) for w,values in sample.items()}
        arrays['matrices']=np.asarray(matrices).reshape(len(fit+held),len(alljoints),4,4)
        np.savez_compressed(FOLDER/'samples.npz',**arrays)
        manifest={'format':'edward-all-prx-bake-trial','date':'2026-10-16','source':str(FOLDER/'Edward_artist_baseline.ma'),
                  'items':items,'axes':axes,'fit':fit,'held_out':held,'all_joints':alljoints,'tolerance_cm':1e-4,
                  'saved_axes':saved,'saved_switches':mode,'capture_seconds':time.perf_counter()-start,
                  'scope':'Whole evaluated output of each of the 23 PRX garment meshes, on separate copies.',
                  'candidates_approved':False,'runtime':pb.__file__}
        write('manifest.json',manifest)
        return {'outputs':len(items),'vertices':sum(i['vertices'] for i in items.values()),'fit':len(fit),'held_out':len(held),'seconds':manifest['capture_seconds']}
    finally:
        apply(saved,axes)
        for p,v in mode.items():cmds.setAttr(p,v)


def copy_mesh(item,suffix,parent=None):
    leaf=item['source'].rsplit('|',1)[-1]
    mesh=cmds.duplicate(item['source'],name=leaf+suffix,returnRootsOnly=True)[0]
    cmds.delete(mesh,ch=True)
    for shape in cmds.listRelatives(mesh,s=True,f=True) or []:
        if cmds.getAttr(shape+'.intermediateObject'):cmds.delete(shape)
    if parent:mesh=cmds.parent(mesh,parent)[0]
    return mesh


def build():
    manifest=json.loads((FOLDER/'manifest.json').read_text());data=np.load(FOLDER/'samples.npz')
    axes=manifest['axes'];items=manifest['items'];fit=manifest['fit'];mode=switches()
    sample_by_wrap={wrap:data[wrap] for wrap in items}
    joint_matrices=data['matrices']
    saved={p:cmds.getAttr(p) for p in axes};pb.check_cancel=lambda:None
    start=time.perf_counter();weights_all={};bs_records={};skin_records={}
    try:
        apply({},axes)
        for p in mode:cmds.setAttr(p,1)
        group=cmds.createNode('transform',name='Edward_AllPRX_BlendshapeCopies_GRP')
        matrix=cmds.createNode('multMatrix',name='Edward_AllPRX_GlobalMotion_MM')
        rest=om.MMatrix(cmds.getAttr('C_masterwalk_CTL.worldMatrix[0]')).inverse()
        cmds.setAttr(matrix+'.matrixIn[0]',*list(rest),type='matrix')
        cmds.connectAttr('C_masterwalk_CTL.worldMatrix[0]',matrix+'.matrixIn[1]')
        cmds.connectAttr(matrix+'.matrixSum',group+'.offsetParentMatrix')
        shared=None
        for wrap,item in items.items():
            mesh=copy_mesh(item,'_ALLPRX_BLS_TEST',group)
            if shared is None:shared=cmds.blendShape(mesh,name='Edward_AllPRX_SHARED_BLS_TEST',origin='local')[0]
            else:cmds.blendShape(shared,e=True,geometry=mesh)
            bs_records[wrap]={'mesh':mesh,'targets':[]}
        # Sparse per-base targets: unaffected geometry does not store a zero target.
        active=[i for i in range(1,len(fit)) if any(np.linalg.norm(sample_by_wrap[w][i]-sample_by_wrap[w][0],axis=1).max()>1e-7 for w in items)]
        for index,sample in enumerate(active):
            for wrap,item in items.items():
                sample_points=sample_by_wrap[wrap][sample]
                if np.linalg.norm(sample_points-sample_by_wrap[wrap][0],axis=1).max()<=1e-7:continue
                mesh=bs_records[wrap]['mesh']
                scratch=cmds.duplicate(mesh,name='allPrxTargetScratch',returnRootsOnly=True)[0];cmds.delete(scratch,ch=True)
                inverse=np.linalg.inv(np.asarray(cmds.xform(mesh,q=True,ws=True,m=True)).reshape(4,4))
                local=np.column_stack((sample_points,np.ones(len(sample_points))))@inverse
                fn(scratch).setPoints(om.MPointArray(local.tolist()),om.MSpace.kObject)
                cmds.blendShape(shared,e=True,target=(mesh,index,scratch,1))
                cmds.delete(scratch);bs_records[wrap]['targets'].append(index)
            cmds.aliasAttr(fit[sample]['name'].replace('-','neg').replace('.','p'),shared+'.weight[%d]'%index)
            if index%10==0:progress('build_blendshape',target=index,total=len(active))
        curves=[]
        for index,sample in enumerate(active):
            plug,value=next(iter(fit[sample]['channels'].items()))
            values=sorted({0}|{next(iter(c['channels'].values())) for c in fit[1:] if plug in c['channels']})
            output=shared+'.weight[%d]'%index
            for key in values:
                cmds.setDrivenKeyframe(output,currentDriver=plug,driverValue=key,value=float(key==value),inTangentType='linear',outTangentType='linear')
            curves.extend(cmds.listConnections(output,s=True,d=False,type='animCurve') or [])
        for record in bs_records.values():cmds.setAttr(record['mesh']+'.visibility',False)
        manifest['blendshape']={'node':shared,'group':group,'matrix':matrix,'curves':curves,'target_samples':active,'outputs':bs_records,
                                'geometry_indices':cmds.blendShape(shared,q=True,geometryIndices=True)}
        write('manifest.json',manifest)
        for index,(wrap,item) in enumerate(items.items()):
            progress('fit_skin',output=index,total=len(items),wrap=wrap)
            indices=[manifest['all_joints'].index(j) for j in item['joints']]
            matrices=joint_matrices[:,indices].transpose(1,0,2,3)
            samples=sample_by_wrap[wrap]
            weights=pb.fit_weights(samples[:len(fit)],matrices[:,:len(fit)],min(8,len(indices)))
            weights_all[wrap]=weights
            mesh=copy_mesh(item,'_ALLPRX_SKIN_TEST')
            skin=cmds.skinCluster(item['joints'],mesh,tsb=True,skinMethod=0,maximumInfluences=8,normalizeWeights=1,
                                  name=wrap+'_BAKED_TEST_SKC')[0]
            selection=om.MSelectionList();selection.add(skin);skin_fn=oma.MFnSkinCluster(selection.getDependNode(0))
            selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh));path=selection.getDagPath(0)
            cf=om.MFnSingleIndexedComponent();component=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(len(weights))
            columns=[item['joints'].index(j.fullPathName()) for j in skin_fn.influenceObjects()]
            skin_fn.setWeights(path,component,om.MIntArray(range(len(columns))),om.MDoubleArray(weights[:,columns].ravel().tolist()),False)
            cmds.setAttr(mesh+'.visibility',False)
            skin_records[wrap]={'mesh':mesh,'skin':skin,'influences':len(indices),'actual_max':int((weights!=0).sum(axis=1).max())}
            np.savez_compressed(FOLDER/'skin_weights.npz',**weights_all)
            manifest['skin']=skin_records;write('manifest.json',manifest)
        manifest['build_seconds']=time.perf_counter()-start;write('manifest.json',manifest)
        return {'shared_blendshape':shared,'targets':len(active),'blendshape_outputs':len(bs_records),'skin_outputs':len(skin_records),'seconds':manifest['build_seconds']}
    finally:
        apply(saved,axes)
        for p,v in mode.items():cmds.setAttr(p,v)


action=globals().get('TRIAL_ARGUMENTS',{}).get('action','capture')
result={'capture':capture,'build':build}[action]()
