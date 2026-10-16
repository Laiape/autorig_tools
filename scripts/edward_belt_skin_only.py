"""Add fitted skin-only belt copies for artist comparison in the owned trial."""
import json
import os
from pathlib import Path
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from tools import proximity_wrap as pw, proximity_bake as pb
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid']
manifest=json.loads((FOLDER/'manifest.json').read_text())
samples=np.load(FOLDER/'samples.npz')
axes=manifest['axes'];saved={p:cmds.getAttr(p) for p in axes}
switches={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk') for s in ('L','R') for limb in ('arm','leg')}
alljoints=list(dict.fromkeys(j for joints in manifest['joints'].values() for j in joints))
pb.check_cancel=lambda:None
fit_count=len(manifest['fit'])
outputs={};weights_out={};fitting=[]
t0=time.perf_counter()
try:
    cmds.evaluationManager(mode='off')
    for p in axes:cmds.setAttr(p,0)
    for p in switches:cmds.setAttr(p,1)
    for belt,joints in manifest['joints'].items():
        (FOLDER/'progress.json').write_text(json.dumps({'phase':'fit_skin_only','belt':belt}))
        indices=[alljoints.index(j) for j in joints]
        matrices=samples['matrices'][:,indices].transpose(1,0,2,3)
        weights=pb.fit_weights(samples[belt][:fit_count],matrices[:,:fit_count],min(8,len(joints)))
        weights_out[belt]=weights
        mesh=cmds.duplicate(belt,name=belt+'_SKIN_ONLY_TEST',returnRootsOnly=True)[0]
        cmds.delete(mesh,ch=True)
        for shape in cmds.listRelatives(mesh,s=True,f=True) or []:
            if cmds.getAttr(shape+'.intermediateObject'):cmds.delete(shape)
        skin=cmds.skinCluster(joints,mesh,tsb=True,skinMethod=0,maximumInfluences=8,
                              normalizeWeights=1,name=belt+'_SKIN_ONLY_TEST_SKC')[0]
        selection=om.MSelectionList();selection.add(skin);fn=oma.MFnSkinCluster(selection.getDependNode(0))
        selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh));path=selection.getDagPath(0)
        cf=om.MFnSingleIndexedComponent();component=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(len(weights))
        columns=[joints.index(j.fullPathName()) for j in fn.influenceObjects()]
        fn.setWeights(path,component,om.MIntArray(range(len(columns))),
                      om.MDoubleArray(weights[:,columns].ravel().tolist()),False)
        outputs[belt]={'mesh':mesh,'skin':skin}
        cmds.setAttr(mesh+'.visibility',False)
        fitting.append({'belt':belt,'influences':len(joints),'fit_poses':fit_count,'held_out_poses':len(manifest['held_out']),
                        'maximum_nonzero_per_vertex':int((weights!=0).sum(axis=1).max()),
                        'weight_sum_max_error':float(np.abs(weights.sum(axis=1)-1).max())})
    manifest['variants']['skin_only']={'meshes':{b:v['mesh'] for b,v in outputs.items()},
                                       'skins':{b:v['skin'] for b,v in outputs.items()},'blendshapes':{},'curves':[],
                                       'new_fit':fitting,'seconds':time.perf_counter()-t0}
    np.savez_compressed(FOLDER/'skin_only_weights.npz',**weights_out)
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2))
    result=manifest['variants']['skin_only']
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
    for p,v in switches.items():cmds.setAttr(p,v)
