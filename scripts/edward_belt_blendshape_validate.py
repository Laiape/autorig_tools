"""Geometry gate for the owned Edward belt blendshape trial, outside timing."""
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from tools import proximity_wrap as pw

FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Use the owned trial process'
manifest=json.loads((FOLDER/'manifest.json').read_text())
options=globals().get('TRIAL_ARGUMENTS',{})
if options.get('reopen_scene'):
    source=Path(options['reopen_scene']).resolve()
    assert source.parent==FOLDER.resolve(), 'Only reopen an owned experiment scene'
    cmds.evaluationManager(mode='off')
    cmds.file(str(source),open=True,force=True,prompt=False,executeScriptNodes=False)
if options.get('variants'):
    manifest['variants']={k:v for k,v in manifest['variants'].items() if k in options['variants']}
AXES=manifest['axes'];BELTS=tuple(manifest['joints'])
saved={p:cmds.getAttr(p) for p in AXES}
switches={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk')
          for s in ('L','R') for limb in ('arm','leg')}
global_plugs=['C_masterwalk_CTL.'+a for a in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ','globalScale')]+['Edward.'+a for a in ('scaleX','scaleY','scaleZ')]
globals_saved={p:cmds.getAttr(p) for p in global_plugs}


def meshfn(mesh):
    shape=pw.mesh_shape(mesh);cmds.dgeval(shape+'.outMesh')
    selection=om.MSelectionList();selection.add(shape)
    return om.MFnMesh(selection.getDagPath(0))


def read_surface(mesh):
    fn=meshfn(mesh)
    return np.asarray(fn.getPoints(om.MSpace.kWorld))[:,:3].copy(),np.asarray(fn.getFaceVertexNormals(om.MSpace.kWorld))[:,:3].copy()


def invariants(mesh):
    fn=meshfn(mesh)
    vertices=fn.getVertices()
    topo=hashlib.sha256(np.asarray(vertices[0],dtype='<i4').tobytes()+np.asarray(vertices[1],dtype='<i4').tobytes()).hexdigest()
    uv={}
    for name in fn.getUVSetNames():
        uv[name]=hashlib.sha256(b''.join(np.asarray(a).tobytes() for a in fn.getUVs(name)+fn.getAssignedUVs(name))).hexdigest()
    hard=hashlib.sha256(bytes(int(fn.isEdgeSmooth(i)) for i in range(fn.numEdges))).hexdigest()
    shaders,indices=fn.getConnectedShaders(0)
    return {'topology':topo,'uv':uv,'edge_smoothness':hard,
            'materials':[om.MFnDependencyNode(s).name() for s in shaders],
            'material_assignment':hashlib.sha256(np.asarray(indices,dtype='<i4').tobytes()).hexdigest()}


def apply(case):
    for p in AXES:cmds.setAttr(p,case['channels'].get(p,0))
    for p,v in globals_saved.items():cmds.setAttr(p,case['channels'].get(p,v))


cases=[dict(c,bank='fit') for c in manifest['fit']]+[dict(c,bank='held_out') for c in manifest['held_out']]
for name,channels in (
    ('global_translate',{'C_masterwalk_CTL.translateX':12,'C_masterwalk_CTL.translateY':3}),
    ('global_rotate',{'C_masterwalk_CTL.rotateY':35}),
    ('global_authored_scale',{'C_masterwalk_CTL.globalScale':1.15}),
    ('root_uniform_scale_probe',{'Edward.scaleX':1.1,'Edward.scaleY':1.1,'Edward.scaleZ':1.1}),
    ('root_nonuniform_scale_probe',{'Edward.scaleX':1.1,'Edward.scaleY':.9,'Edward.scaleZ':1.05}),
):cases.append({'name':name,'channels':channels,'bank':'held_global'})
if options.get('quick'):
    names={'neutral','C_spine03_CTL_rotateY_-20','C_spine07_CTL_rotateZ_35','held_combination_03','held_combination_07',
           'global_translate','global_rotate','global_authored_scale'}
    cases=[c for c in cases if c['name'] in names]
rows=[];t0=time.perf_counter()
try:
    for p in switches:cmds.setAttr(p,1)
    apply({'channels':{}})
    discrete={b:{'reference':invariants(b),**{k:invariants(v['meshes'][b]) for k,v in manifest['variants'].items()}} for b in BELTS}
    for direction,ordered in (('forward',cases),('reverse',list(reversed(cases)))):
        for index,case in enumerate(ordered):
            apply(case)
            reference={b:read_surface(b) for b in BELTS}
            current={k:{b:read_surface(v['meshes'][b]) for b in BELTS} for k,v in manifest['variants'].items()}
            for kind,meshes in current.items():
                for belt,(points,normals) in meshes.items():
                    ep=np.linalg.norm(points-reference[belt][0],axis=1)
                    en=np.linalg.norm(normals-reference[belt][1],axis=1)
                    pair=(('blendshape_only_separate' if kind=='blendshape_only_shared' else 'blendshape_only_shared') if kind.startswith('blendshape_only') else ('separate' if kind=='shared' else 'shared')) if kind!='skin_only' else 'skin_only'
                    rows.append({'direction':direction,'pose':case['name'],'bank':case['bank'],
                                 'variant':kind,'belt':belt,'max_position':float(ep.max()),
                                 'rms_position':float(np.sqrt(np.mean(ep*ep))),
                                 'max_face_vertex_normal':float(en.max()),
                                 'shared_separate_max':float(np.linalg.norm(points-current[pair][belt][0],axis=1).max())})
            if index%10==0:
                (FOLDER/'progress.json').write_text(json.dumps({'phase':'quality','direction':direction,'completed':index,'total':len(cases)}))
    summary={}
    for kind in manifest['variants']:
        summary[kind]={}
        for belt in BELTS:
            selected=[r for r in rows if r['variant']==kind and r['belt']==belt]
            summary[kind][belt]={}
            for bank in ('fit','held_out','held_global'):
                subset=[r for r in selected if r['bank']==bank]
                worst=max(subset,key=lambda r:r['max_position'])
                summary[kind][belt][bank]={'max_position':worst['max_position'],'worst_pose':worst['pose'],
                                          'rms_at_worst':worst['rms_position'],
                                          'max_face_vertex_normal':max(r['max_face_vertex_normal'] for r in subset),
                                          'samples':len(subset)}
    result={'tolerance':manifest['tolerance'],'units':manifest['units'],'cases':len(cases),'rows':len(rows),
            'summary':summary,'shared_separate_max':max(r['shared_separate_max'] for r in rows),
            'invariants':discrete,'invariants_match':all(all(d==data['reference'] for d in data.values()) for data in discrete.values()),
            'passed':all(r['max_position']<=manifest['tolerance'] and r['max_face_vertex_normal']<=manifest['tolerance'] for r in rows),
            'seconds':time.perf_counter()-t0}
    prefix=options.get('prefix','quality')
    (FOLDER/(prefix+'_rows.json')).write_text(json.dumps(rows,indent=2))
    (FOLDER/(prefix+'_summary.json')).write_text(json.dumps(result,indent=2))
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
    for p,v in globals_saved.items():cmds.setAttr(p,v)
    for p,v in switches.items():cmds.setAttr(p,v)
