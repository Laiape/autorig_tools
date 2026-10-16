"""Requested blendshape-only trials, with shared or per-belt native nodes."""
import json
import os
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from tools import proximity_wrap as pw
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Use the owned trial process'
manifest=json.loads((FOLDER/'manifest.json').read_text())
data=np.load(FOLDER/'samples.npz')
BELTS=tuple(manifest['joints']);AXES=manifest['axes'];FIT=manifest['fit']
saved={p:cmds.getAttr(p) for p in AXES}
switches={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk') for s in ('L','R') for limb in ('arm','leg')}


def meshfn(mesh):
    selection=om.MSelectionList();selection.add(pw.mesh_shape(mesh))
    return om.MFnMesh(selection.getDagPath(0))


def copy_base(belt,name):
    mesh=cmds.duplicate(belt,name=name,returnRootsOnly=True)[0]
    cmds.delete(mesh,ch=True)
    for shape in cmds.listRelatives(mesh,s=True,f=True) or []:
        if cmds.getAttr(shape+'.intermediateObject'):cmds.delete(shape)
    return mesh


try:
    for p in AXES:cmds.setAttr(p,0)
    for p in switches:cmds.setAttr(p,1)
    keep=[i for i in range(1,len(FIT)) if max(np.linalg.norm(data[b][i]-data[b][0],axis=1).max() for b in BELTS)>1e-7]
    for kind in ('blendshape_only_shared','blendshape_only_separate'):
        group=cmds.createNode('transform',name='EdwardBelts_'+kind+'_GRP')
        matrix=cmds.createNode('multMatrix',name=kind+'_globalMotion_MM')
        rest=om.MMatrix(cmds.getAttr('C_masterwalk_CTL.worldMatrix[0]')).inverse()
        cmds.setAttr(matrix+'.matrixIn[0]',*list(rest),type='matrix')
        cmds.connectAttr('C_masterwalk_CTL.worldMatrix[0]',matrix+'.matrixIn[1]')
        cmds.connectAttr(matrix+'.matrixSum',group+'.offsetParentMatrix')
        bases={b:cmds.parent(copy_base(b,b+'_'+kind+'_TEST'),group)[0] for b in BELTS}
        if kind.endswith('_shared'):
            bs=cmds.blendShape(bases[BELTS[0]],name='EdwardBelts_BLENDSHAPE_ONLY_SHARED_TEST',origin='local')[0]
            cmds.blendShape(bs,e=True,geometry=bases[BELTS[1]])
            blends={b:bs for b in BELTS}
        else:
            blends={b:cmds.blendShape(mesh,name=b+'_BLENDSHAPE_ONLY_TEST',origin='local')[0] for b,mesh in bases.items()}
        for index,sample in enumerate(keep):
            for b in BELTS:
                scratch=cmds.duplicate(bases[b],name='beltOnlyScratch',returnRootsOnly=True)[0]
                cmds.delete(scratch,ch=True)
                target=data[b][sample]
                meshfn(scratch).setPoints(om.MPointArray(np.column_stack((target,np.ones(len(target)))).tolist()),om.MSpace.kObject)
                cmds.blendShape(blends[b],e=True,target=(bases[b],index,scratch,1.0))
                cmds.delete(scratch)
            for bs in set(blends.values()):
                cmds.aliasAttr(FIT[sample]['name'].replace('-','neg').replace('.','p'),bs+'.weight[%d]'%index)
        curves=[]
        for index,sample in enumerate(keep):
            plug,value=next(iter(FIT[sample]['channels'].items()))
            values=sorted({0.0}|{next(iter(c['channels'].values())) for c in FIT[1:] if plug in c['channels']})
            for bs in set(blends.values()):
                output=bs+'.weight[%d]'%index
                for key in values:
                    cmds.setDrivenKeyframe(output,currentDriver=plug,driverValue=key,value=float(key==value),
                                           inTangentType='linear',outTangentType='linear')
                curve=cmds.listConnections(output,s=True,d=False,type='animCurve')[0]
                curves.append(curve)
        for mesh in bases.values():cmds.setAttr(mesh+'.visibility',False)
        manifest['variants'][kind]={'meshes':bases,'blendshapes':blends,'skins':{},'curves':curves,
                                    'target_sample_indices':keep,'global_group':group,'global_motion_node':matrix,
                                    'geometry_indices':{b:cmds.blendShape(bs,q=True,geometryIndices=True) for b,bs in blends.items()}}
        (FOLDER/'progress.json').write_text(json.dumps({'phase':'build_blendshape_only','completed':kind,'targets':len(keep)}))
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2))
    result={'targets_per_node':len(keep),'variants':{k:{'meshes':v['meshes'],'nodes':list(set(v['blendshapes'].values()))}
                                                     for k,v in manifest['variants'].items() if k.startswith('blendshape_only')}}
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
    for p,v in switches.items():cmds.setAttr(p,v)
