"""Compare native skinning methods and local DQ masks without changing weights."""
import json, math
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from maya_tools.scripts.tools import rig_validation as qa, pose_blendshapes as poses

def skin_data(mesh, skin):
    selection=om.MSelectionList();selection.add(skin);fn=oma.MFnSkinCluster(selection.getDependNode(0))
    shape=cmds.listRelatives(poses.mesh_transform(mesh),shapes=True,noIntermediate=True,fullPath=True)[0]
    selection=om.MSelectionList();selection.add(shape);path=selection.getDagPath(0)
    comp=om.MFnSingleIndexedComponent();component=comp.create(om.MFn.kMeshVertComponent)
    comp.setCompleteData(om.MFnMesh(path).numVertices)
    return fn,path,component

def influence_mask(mesh,skin,joints):
    fn,path,component=skin_data(mesh,skin)
    weights,count=fn.getWeights(path,component)
    influence_names=[p.fullPathName() for p in fn.influenceObjects()]
    selected=set(cmds.ls(joints,long=True) or [])
    columns=[i for i,n in enumerate(influence_names) if n in selected]
    if not columns:raise ValueError('No selected joint influences this skin.')
    return np.clip(np.asarray(weights).reshape(-1,count)[:,columns].sum(axis=1),0,1).tolist()

def local_mask(mesh,skin,joints):
    regional=influence_mask(mesh,skin,joints)
    fn,path,component=skin_data(mesh,skin)
    existing=list(fn.getBlendWeights(path,component)) if cmds.getAttr(skin+'.skinningMethod')==2 else [0.]*len(regional)
    return regional,np.maximum(regional,existing).tolist()

@poses.undoable
def apply_mask(mesh,skin,mask):
    fn,path,component=skin_data(mesh,skin)
    values=np.asarray(mask,dtype=float)
    if len(values)!=om.MFnMesh(path).numVertices or not np.isfinite(values).all() or (values<0).any() or (values>1).any():
        raise ValueError('DQ blend mask must contain one finite 0..1 weight per vertex.')
    cmds.setAttr(skin+'.blendWeights[0:%d]' % (len(values)-1), *values.tolist(), size=len(values))
    cmds.setAttr(skin+'.skinningMethod',2)

def metrics(points,vertices):
    p=np.asarray(points,dtype=float)[vertices]
    centered=p-p.mean(axis=0)
    eigenvalues=np.linalg.eigvalsh(centered.T@centered/len(p))
    return {'principal_rms':np.sqrt(np.maximum(eigenvalues,0)).tolist(),
            'bbox':(p.max(axis=0)-p.min(axis=0)).tolist(),
            'measurement':'Principal RMS extents are thickness proxies, not enclosed anatomical volume.'}

def compare(root,mesh,skin,output,cases,mask,vertices=None):
    output=Path(output)
    if output.exists():raise ValueError('Choose a new skin comparison report.')
    fn,path,component=skin_data(mesh,skin)
    previous_method=cmds.getAttr(skin+'.skinningMethod');previous_blend=fn.getBlendWeights(path,component)
    count=om.MFnMesh(path).numVertices
    vertices=list(range(count)) if vertices is None else list(vertices)
    if len(vertices)<3 or min(vertices)<0 or max(vertices)>=count:raise ValueError('Select a valid region with at least three vertices.')
    resolved,missing,skipped=qa.resolve_cases(root,cases)
    if missing:raise ValueError('Missing skinning test controls: '+', '.join(missing))
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']}
    report={'version':1,'mesh':mesh,'skin':skin,'vertices':vertices,'mask':mask,'topology':qa.mesh_data(mesh)['topology'],
            'units':cmds.currentUnit(q=True,linear=True),'variants':{}}
    try:
        with qa._session(),poses._temporary_values(initial):
            for variant,method in (('original',previous_method),('linear',0),('dual_quaternion',1),('local_blend',2)):
                if variant=='original':
                    fn,path,component=skin_data(mesh,skin)
                    fn.setBlendWeights(path,component,previous_blend);cmds.setAttr(skin+'.skinningMethod',previous_method)
                elif method==2:apply_mask(mesh,skin,mask)
                else:cmds.setAttr(skin+'.skinningMethod',method)
                samples=[]
                for case in resolved:
                    for plug,value in case['values'].items():cmds.setAttr(plug,value)
                    geometry=qa.mesh_data(mesh)
                    samples.append({'pose':case['name'],'metrics':metrics(geometry['points'],vertices),
                                    'points':geometry['points']})
                report['variants'][variant]=samples
    finally:
        fn,path,component=skin_data(mesh,skin)
        fn.setBlendWeights(path,component,previous_blend);cmds.setAttr(skin+'.skinningMethod',previous_method)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(report,stream,separators=(',',':'),allow_nan=False)
    return report
