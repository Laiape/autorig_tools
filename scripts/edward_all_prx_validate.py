"""Independent geometry/persistence gate for all 23 PRX comparison outputs."""
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from tools import proximity_wrap as pw
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid']
options=globals().get('TRIAL_ARGUMENTS',{})
manifest=json.loads((FOLDER/'manifest.json').read_text())
if options.get('reopen'):
    cmds.evaluationManager(mode='off')
    cmds.file(manifest['scenes'][options['reopen']]['path'],open=True,force=True,prompt=False,executeScriptNodes=False)


def mesh_fn(mesh):
    shape=pw.mesh_shape(mesh);cmds.dgeval(shape+'.outMesh')
    selection=om.MSelectionList();selection.add(shape)
    return om.MFnMesh(selection.getDagPath(0))


def surface(mesh):
    fn=mesh_fn(mesh)
    return np.asarray(fn.getPoints(om.MSpace.kWorld))[:,:3].copy(),np.asarray(fn.getFaceVertexNormals(om.MSpace.kWorld))[:,:3].copy()


def invariant(mesh):
    fn=mesh_fn(mesh);counts,indices=fn.getVertices();shaders,faces=fn.getConnectedShaders(0)
    uv={name:hashlib.sha256(b''.join(np.asarray(a).tobytes() for a in fn.getUVs(name)+fn.getAssignedUVs(name))).hexdigest() for name in fn.getUVSetNames()}
    return {'topology':hashlib.sha256(np.asarray(list(counts)+list(indices),dtype='<i4').tobytes()).hexdigest(),
            'uv':uv,'hard_edges':hashlib.sha256(bytes(int(fn.isEdgeSmooth(i)) for i in range(fn.numEdges))).hexdigest(),
            'materials':[om.MFnDependencyNode(s).name() for s in shaders],
            'material_faces':hashlib.sha256(np.asarray(faces,dtype='<i4').tobytes()).hexdigest()}


items=manifest['items'];axes=manifest['axes'];saved={p:cmds.getAttr(p) for p in axes}
switches={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk') for s in ('L','R') for limb in ('arm','leg')}
globals_saved={p:cmds.getAttr(p) for p in ('C_masterwalk_CTL.translateX','C_masterwalk_CTL.rotateY','C_masterwalk_CTL.globalScale')}
variants={'BLENDSHAPE':manifest['blendshape']['outputs'],'SKIN':manifest['skin']}
if options.get('reopen'):variants={options['reopen']:variants[options['reopen']]}
cases=[dict(c,bank='capture') for c in manifest['fit']]+[dict(c,bank='held_out') for c in manifest['held_out']]
cases +=[{'name':'global_translate','bank':'global','channels':{'C_masterwalk_CTL.translateX':12}},
         {'name':'global_rotate','bank':'global','channels':{'C_masterwalk_CTL.rotateY':35}},
         {'name':'global_scale','bank':'global','channels':{'C_masterwalk_CTL.globalScale':1.15}}]
if options.get('quick'):
    wanted={'neutral','C_spine03_CTL_rotateY_-20','C_localChest_CTL_rotateZ_25','L_ankleFk_CTL_rotateX_35',
            'held_combination_03','held_combination_07','held_combination_12','global_translate','global_rotate','global_scale'}
    cases=[c for c in cases if c['name'] in wanted]
rows=[];start=time.perf_counter()
try:
    cmds.evaluationManager(mode='off')
    for p in axes:cmds.setAttr(p,0)
    for p in switches:cmds.setAttr(p,1)
    discrete={wrap:{'reference':invariant(item['source']),**{kind:invariant(records[wrap]['mesh']) for kind,records in variants.items()}}
              for wrap,item in items.items()}
    for direction,ordered in (('forward',cases),('reverse',list(reversed(cases)))):
        for index,case in enumerate(ordered):
            for p in axes:cmds.setAttr(p,case['channels'].get(p,0))
            for p,v in globals_saved.items():cmds.setAttr(p,case['channels'].get(p,v))
            reference={wrap:surface(item['source']) for wrap,item in items.items()}
            for kind,records in variants.items():
                for wrap,record in records.items():
                    points,normals=surface(record['mesh']);a,b=reference[wrap]
                    errors=np.linalg.norm(points-a,axis=1);normal=np.linalg.norm(normals-b,axis=1)
                    rows.append({'variant':kind,'wrap':wrap,'pose':case['name'],'bank':case['bank'],'direction':direction,
                                 'max_position_cm':float(errors.max()),'rms_position_cm':float(np.sqrt(np.mean(errors**2))),
                                 'max_normal':float(normal.max())})
            if index%10==0:
                (FOLDER/'progress.json').write_text(json.dumps({'phase':'validate','direction':direction,'case':index,'total':len(cases)}))
    summaries={}
    for kind in variants:
        summaries[kind]={}
        for wrap in items:
            summaries[kind][wrap]={}
            for bank in ('capture','held_out','global'):
                selected=[r for r in rows if r['variant']==kind and r['wrap']==wrap and r['bank']==bank]
                if not selected:continue
                worst=max(selected,key=lambda r:r['max_position_cm'])
                summaries[kind][wrap][bank]={'max_position_cm':worst['max_position_cm'],'worst_pose':worst['pose'],
                                            'max_normal':max(r['max_normal'] for r in selected),
                                            'passed':all(r['max_position_cm']<=1e-4 and r['max_normal']<=1e-4 for r in selected)}
    result={'cases':len(cases),'mesh_comparisons':len(rows),'tolerance_cm':1e-4,'summary':summaries,
            'invariants':discrete,'invariants_match':all(all(v==data['reference'] for v in data.values()) for data in discrete.values()),
            'passed':all(r['max_position_cm']<=1e-4 and r['max_normal']<=1e-4 for r in rows),'seconds':time.perf_counter()-start}
    prefix=options.get('prefix','quality')
    (FOLDER/(prefix+'_rows.json')).write_text(json.dumps(rows,indent=2))
    (FOLDER/(prefix+'_summary.json')).write_text(json.dumps(result,indent=2))
    result={k:v for k,v in result.items() if k not in ('summary','invariants')}
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
    for p,v in globals_saved.items():cmds.setAttr(p,v)
    for p,v in switches.items():cmds.setAttr(p,v)
