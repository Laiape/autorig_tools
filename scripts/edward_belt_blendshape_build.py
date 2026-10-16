"""Capture independent belt poses and build native shared/separate target trials.

Execute only through the owned edward_belt_blendshape_trial.py host. This is a
finite-pose approximation experiment, not an approved autorig replacement.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from tools import proximity_wrap as pw

assert cmds.about(batch=True), 'Use the owned standalone host'
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Use the owned trial process'
OLD=Path(r'C:/proyectos/auto-rig/tmp/edward_wrap_bake_20261015')
TOLERANCE=1e-4
BELTS=('cinturon3','cinturones2')


def meshfn(mesh):
    selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh))
    return om.MFnMesh(selection.getDagPath(0))


def points(mesh):
    shape=pw.mesh_shape(mesh)
    cmds.dgeval(shape+'.outMesh')
    return np.asarray(meshfn(shape).getPoints(om.MSpace.kWorld))[:,:3].copy()


def surface(mesh):
    fn=meshfn(mesh)
    return points(mesh), np.asarray(fn.getFaceVertexNormals(om.MSpace.kWorld))[:,:3].copy()


def pose(values):
    for plug in AXES:
        cmds.setAttr(plug,values.get(plug,0))


def progress(phase,**kwargs):
    (FOLDER/'progress.json').write_text(json.dumps(dict(phase=phase,**kwargs),indent=2))


AXES={}
for node in ('C_spine03_CTL','C_spine07_CTL'):
    for channel,limits in {'rotateX':(-25,25),'rotateY':(-20,20),'rotateZ':(-20,35)}.items():
        AXES[node+'.'+channel]=limits
for side in ('L','R'):
    for part,values in {
        'shoulderFk':{'rotateX':(-45,55),'rotateY':(-45,70),'rotateZ':(-40,100)},
        'hipFk':{'rotateX':(-35,35),'rotateY':(-30,60),'rotateZ':(-45,95)},
        'elbowFk':{'rotateX':(-60,60),'rotateY':(-100,100)},
    }.items():
        for channel,limits in values.items():AXES[side+'_'+part+'_CTL.'+channel]=limits
for channel in ('rotateX','rotateY','rotateZ'):
    AXES['C_localHip_CTL.'+channel]=(-25,25)
AXES={p:v for p,v in AXES.items() if cmds.objExists(p) and cmds.getAttr(p,settable=True)}
SAVED={p:cmds.getAttr(p) for p in AXES}
SWITCHES={side+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(side+'_'+limb+'Settings_CTL.Ik_Fk')
          for side in ('L','R') for limb in ('arm','leg')}
old_plan=json.loads((OLD/'wrap_sample_plan.json').read_text())
old_weights=np.load(OLD/'refined_weights.npz')
JOINTS={belt:old_plan['targets'][belt+'_PRX']['joints'] for belt in BELTS}
WEIGHTS={belt:old_weights[belt+'_PRX'].copy() for belt in BELTS}
ALL_JOINTS=list(dict.fromkeys(j for belt in BELTS for j in JOINTS[belt]))

# Four nonzero samples per axis. Held-out fractions and combinations are never
# used to construct deltas or fit the reused diagnostic skin weights.
FIT=[{'name':'neutral','channels':{}}]
HELD=[]
for plug,(lo,hi) in AXES.items():
    for value in (lo,lo*.5,hi*.5,hi):
        FIT.append({'name':plug.replace('.','_')+'_%g'%value,'channels':{plug:value}})
    for value in (lo*.37,hi*.73):
        HELD.append({'name':'held_'+plug.replace('.','_')+'_%g'%value,'channels':{plug:value}})
rng=np.random.default_rng(16102026)
body=list(AXES)
for i in range(24):
    chosen=rng.choice(body,4,replace=False)
    HELD.append({'name':'held_combination_%02d'%i,
                 'channels':{p:float(rng.uniform(*AXES[p]))*.65 for p in chosen}})

SAMPLES={belt:[] for belt in BELTS}
MATRICES=[]
t0=time.perf_counter()
try:
    for p in SWITCHES:cmds.setAttr(p,1)
    for i,case in enumerate(FIT+HELD):
        pose(case['channels'])
        for belt in BELTS:SAMPLES[belt].append(points(belt))
        MATRICES.append([cmds.xform(j,q=True,ws=True,m=True) for j in ALL_JOINTS])
        if i%10==0:progress('sample',completed=i,total=len(FIT+HELD))
    SAMPLES={belt:np.asarray(values) for belt,values in SAMPLES.items()}
    MATRICES=np.asarray(MATRICES).reshape(len(FIT+HELD),len(ALL_JOINTS),4,4)
    np.savez_compressed(FOLDER/'samples.npz',matrices=MATRICES,**SAMPLES)
    pose({})
    BASE={belt:SAMPLES[belt][0] for belt in BELTS}
    DELTAS={belt:[] for belt in BELTS}
    for belt in BELTS:
        indexes=[ALL_JOINTS.index(j) for j in JOINTS[belt]]
        relative=np.linalg.inv(MATRICES[0,indexes])[None]@MATRICES[:,indexes]
        for i,case in enumerate(FIT):
            blended=np.einsum('vj,jab->vab',WEIGHTS[belt],relative[i],optimize=True)
            target=np.column_stack((SAMPLES[belt][i],np.ones(len(BASE[belt]))))
            rest=np.einsum('va,vab->vb',target,np.linalg.inv(blended))[:,:3]
            DELTAS[belt].append(rest-BASE[belt])
        DELTAS[belt]=np.asarray(DELTAS[belt])
    keep=[i for i in range(1,len(FIT)) if max(float(np.linalg.norm(DELTAS[b][i],axis=1).max()) for b in BELTS)>1e-7]
    np.savez_compressed(FOLDER/'deltas_and_weights.npz',**{b+'_delta':DELTAS[b] for b in BELTS},
                        **{b+'_weights':WEIGHTS[b] for b in BELTS})

    def bind(mesh,belt):
        skin=cmds.skinCluster(JOINTS[belt],mesh,tsb=True,skinMethod=0,maximumInfluences=8,
                              normalizeWeights=1,name=mesh+'_SKC')[0]
        selection=om.MSelectionList();selection.add(skin)
        fn=oma.MFnSkinCluster(selection.getDependNode(0))
        selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh));path=selection.getDagPath(0)
        cf=om.MFnSingleIndexedComponent();comp=cf.create(om.MFn.kMeshVertComponent)
        cf.setCompleteData(len(BASE[belt]))
        columns=[JOINTS[belt].index(j.fullPathName()) for j in fn.influenceObjects()]
        fn.setWeights(path,comp,om.MIntArray(range(len(columns))),
                      om.MDoubleArray(WEIGHTS[belt][:,columns].ravel().tolist()),False)
        return skin

    def copy_base(belt,suffix):
        mesh=cmds.duplicate(belt,name=belt+'_'+suffix,returnRootsOnly=True)[0]
        cmds.delete(mesh,ch=True)
        for shape in cmds.listRelatives(mesh,shapes=True,fullPath=True) or []:
            if cmds.getAttr(shape+'.intermediateObject'):cmds.delete(shape)
        cmds.setAttr(mesh+'.visibility',True)
        return mesh

    VARIANTS={}
    for kind in ('shared','separate'):
        progress('construct',variant=kind)
        bases={belt:copy_base(belt,kind.upper()+'_BS_TEST') for belt in BELTS}
        if kind=='shared':
            bs=cmds.blendShape(bases[BELTS[0]],name='EdwardBelts_SHARED_BLS_TEST',origin='local')[0]
            cmds.blendShape(bs,e=True,geometry=bases[BELTS[1]])
            blends={belt:bs for belt in BELTS}
        else:
            blends={belt:cmds.blendShape(mesh,name=belt+'_SEPARATE_BLS_TEST',origin='local')[0] for belt,mesh in bases.items()}
        for target_index,sample_index in enumerate(keep):
            case=FIT[sample_index]
            for belt in BELTS:
                scratch=cmds.duplicate(bases[belt],name='beltTargetScratch',returnRootsOnly=True)[0]
                cmds.delete(scratch,ch=True)
                target=BASE[belt]+DELTAS[belt][sample_index]
                meshfn(scratch).setPoints(om.MPointArray(np.column_stack((target,np.ones(len(target)))).tolist()),om.MSpace.kObject)
                cmds.blendShape(blends[belt],e=True,target=(bases[belt],target_index,scratch,1.0))
                cmds.delete(scratch)
            for bs in set(blends.values()):
                cmds.aliasAttr(case['name'].replace('-','neg').replace('.','p'),bs+'.weight[%d]'%target_index)
        skins={belt:bind(mesh,belt) for belt,mesh in bases.items()}
        # Piecewise linear hats provide exact stored axis samples and automatic
        # controller activation. Shared node weights are genuinely shared.
        curves=[]
        for target_index,sample_index in enumerate(keep):
            plug,value=next(iter(FIT[sample_index]['channels'].items()))
            values=sorted({0.0}|{next(iter(c['channels'].values())) for c in FIT[1:] if plug in c['channels']})
            for bs in set(blends.values()):
                output=bs+'.weight[%d]'%target_index
                for key in values:
                    cmds.setDrivenKeyframe(output,currentDriver=plug,driverValue=key,value=float(key==value),
                                           inTangentType='linear',outTangentType='linear')
                curve=cmds.listConnections(output,s=True,d=False,type='animCurve')[0]
                cmds.setInfinity(curve,pri='constant',poi='constant')
                curves.append(curve)
        for mesh in bases.values():cmds.setAttr(mesh+'.visibility',False)
        VARIANTS[kind]={'meshes':bases,'blendshapes':blends,'skins':skins,'curves':curves,
                        'geometry_indices':{b:cmds.blendShape(bs,q=True,geometryIndices=True) for b,bs in blends.items()}}

    manifest={'source':str(FOLDER/'Edward_artist_baseline.ma'),'units':cmds.currentUnit(q=True,linear=True),
              'tolerance':TOLERANCE,'axes':AXES,'fit':FIT,'held_out':HELD,'target_sample_indices':keep,
              'variants':VARIANTS,'joints':JOINTS,'weight_source':str(OLD/'refined_weights.npz'),
              'runtime':'autorig_tools/maya_tools/scripts','capture_seconds':time.perf_counter()-t0,
              'source_wraps':{b:cmds.listConnections(b+'_PRX.drivers',s=True,d=False,p=True) for b in BELTS}}
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2))
    result={'targets_per_blendshape':len(keep),'fit':len(FIT),'held_out':len(HELD),
            'variants':{k:{'meshes':v['meshes'],'nodes':list(set(v['blendshapes'].values()))} for k,v in VARIANTS.items()},
            'seconds':time.perf_counter()-t0}
finally:
    for p,v in SAVED.items():cmds.setAttr(p,v)
    for p,v in SWITCHES.items():cmds.setAttr(p,v)
