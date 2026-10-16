"""Owned-Maya persistence and all-clothing data checks, outside timing."""
import hashlib
import importlib
import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
import edward_exact_worker as w
importlib.reload(w)
importlib.reload(w.bw)
w.owned()
FOLDER=w.FOLDER


def digest(value):
    if isinstance(value,np.ndarray):
        return hashlib.sha256(value.tobytes()).hexdigest()
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def fingerprint():
    meshes={}
    inventory=json.loads((FOLDER/'inventory.json').read_text())
    for row in inventory['meshes']:
        shape=row['shape'];path,fn=w.path_fn(shape)
        counts,vertices=fn.getVertices()
        shaders,shader_ids=fn.getConnectedShaders(path.instanceNumber())
        uv={name:{'coordinates':digest(np.asarray(fn.getUVs(name))),
                  'assignment':digest([list(x) for x in fn.getAssignedUVs(name)])}
            for name in fn.getUVSetNames()}
        normal_counts,normal_ids=fn.getNormalIds()
        meshes[shape]={'topology':digest([list(counts),list(vertices)]),'uv':uv,
            'materials':[om.MFnDependencyNode(n).name() for n in shaders],
            'material_ids':digest(list(shader_ids)),
            'hard_edges':digest([fn.isEdgeSmooth(i) for i in range(fn.numEdges)]),
            'normal_ids':digest([list(normal_counts),list(normal_ids)]),
            'normals':np.asarray(fn.getNormals(om.MSpace.kObject)).tolist(),
            'positions':digest(np.asarray(fn.getPoints(om.MSpace.kWorld)))}
    skins={}
    with w.bw.primary_inputs_for_skin_export():
        for name in cmds.ls(type='skinCluster') or []:
            fn=oma.MFnSkinCluster(om.MSelectionList().add(name).getDependNode(0))
            influences=fn.influenceObjects();names=[p.fullPathName() for p in influences]
            data=[];retained=set()
            for geo in fn.getOutputGeometry():
                path=om.MDagPath.getAPathTo(geo)
                if geo.hasFn(om.MFn.kTransform):
                    path.extendToShape();geo=path.node()
                if geo.hasFn(om.MFn.kMesh):
                    c=om.MFnSingleIndexedComponent();comp=c.create(om.MFn.kMeshVertComponent)
                    c.setCompleteData(om.MFnMesh(path).numVertices)
                elif geo.hasFn(om.MFn.kNurbsCurve):
                    c=om.MFnSingleIndexedComponent();comp=c.create(om.MFn.kCurveCVComponent)
                    c.setCompleteData(om.MFnNurbsCurve(path).numCVs)
                elif geo.hasFn(om.MFn.kNurbsSurface):
                    surface=om.MFnNurbsSurface(path)
                    c=om.MFnDoubleIndexedComponent();comp=c.create(om.MFn.kSurfaceCVComponent)
                    c.setCompleteData(surface.numCVsInU,surface.numCVsInV)
                else:raise RuntimeError('Unsupported skin output '+name+' '+path.fullPathName()+' '+geo.apiTypeStr)
                weights,count=fn.getWeights(path,comp)
                a=np.asarray(weights).reshape((-1,count))
                keep=[i for i in range(count) if np.any(a[:,i]!=0.)]
                keep.sort(key=lambda i:names[i]);retained.update(keep)
                data.append({'geometry':path.fullPathName(),'nonzero_names':[names[i] for i in keep],
                             'weights':digest(a[:,keep].copy()),
                             'dq_mask':digest(np.asarray(fn.getBlendWeights(path,comp)))})
            rests={names[i]:{'bind':cmds.getAttr('%s.bindPreMatrix[%d]'%(name,fn.indexForInfluenceObject(influences[i]))),
                            'matrix_source':cmds.connectionInfo('%s.matrix[%d]'%(name,fn.indexForInfluenceObject(influences[i])),sourceFromDestination=True)}
                   for i in sorted(retained)}
            attrs={a:cmds.getAttr(name+'.'+a) for a in ('skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution','envelope','nodeState')}
            skins[name]={'data':data,'rest':rests,'attributes':attrs}
    manager=make_manager()
    scene=manager._export_scene_deformers()
    scene['nodes']=[r for r in scene['nodes'] if r['type']!='skinCluster']
    # Export native corrective/PRX settings and original wrinkle fields separately.
    return {'meshes':meshes,'skins':skins,'deformers':digest(scene),
            'wrinkles':digest(w.bw.export_setups()),
            'joint_names':sorted(cmds.ls('Edward',dag=True,type='joint',long=True) or []),
            'controls':sorted(cmds.ls('*_CTL',type='transform',long=True) or []),
            'prx':sorted(cmds.ls(type='proximityWrap') or [])}


def make_manager():
    from maya_tools.scripts.tools import skin_manager_api as sm
    importlib.reload(sm)
    manager=sm.SkinManager.__new__(sm.SkinManager)
    manager.k_skin_attrs=['skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences','weightDistribution']
    manager.tolerance=1e-5
    return manager


def consumer_map():
    inventory=json.loads((FOLDER/'inventory.json').read_text())
    prx={r['node']:r for r in inventory['prx']}
    rows=[]
    for row in inventory['meshes']:
        source=cmds.connectionInfo(row['shape']+'.inMesh',sourceFromDestination=True)
        chain=[];seen=set()
        while source:
            node=source.split('.')[0]
            if node in seen:break
            seen.add(node)
            kind=cmds.nodeType(node)
            if kind in ('skinCluster','proximityWrap','blendShape','deltaMush','tension','wrap'):
                chain.append({'node':node,'type':kind})
                index=source.rsplit('[',1)[-1].split(']')[0] if '[' in source else '0'
                plug=node+'.input['+index+'].inputGeometry'
            else:plug=node+'.inMesh'
            if not cmds.objExists(plug):break
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
        direct={r['node'] for r in chain}
        rows.append({'shape':row['shape'],'vertices':row['vertices'],'visible':row['visible'],
                     'primary_chain':chain,'upstream_driver_deformers':[r for r in row['history'] if r['node'] not in direct],
                     'prx_drivers':[prx[r['node']] for r in chain if r['node'] in prx]})
    w.write('consumer_map.json',rows)
    return rows


NORMAL_COMPARISONS=[]
def compare(a,b):
    differences=[]
    for group in a:
        if group in ('meshes','skins'):
            if set(a[group])!=set(b[group]):differences.append(group+' names')
            for name in a[group]:
                if a[group][name]!=b[group].get(name):
                    for key,value in a[group][name].items():
                        other=b[group].get(name,{}).get(key)
                        if key=='normals' and other is not None:
                            error=float(np.linalg.norm(np.asarray(value)-np.asarray(other),axis=1).max())
                            NORMAL_COMPARISONS.append(error)
                            if error>1e-4:differences.append(group+':'+name+':normals')
                        elif value!=other:differences.append(group+':'+name+':'+key)
        elif a[group]!=b.get(group):differences.append(group)
    return differences


arguments=globals().get('TRIAL_ARGUMENTS',{})
action=arguments.get('action','data')
source=FOLDER/'saved_variants/Edward_safe_full.mb'
if action=='data':
    w.progress('persistence_original');w.load();consumer_map();original=fingerprint()
    w.write('persistence_original.json',original)
    w.progress('persistence_saved');w.load(source);saved=fingerprint()
    w.write('persistence_saved.json',saved)
    diff=compare(original,saved)
    result={'accepted':not diff,'differences':diff,'meshes':len(saved['meshes']),'skins':len(saved['skins']),
            'max_face_vertex_normal_error':max(NORMAL_COMPARISONS,default=0.),
            'joints':len(saved['joint_names']),'prx':len(saved['prx']),
            'scope':'Native mesh topology/UVs/materials/hard edges/face-vertex normals, all skin positive weights/DQ/rest/methods incl curves/surfaces, PRX/corrective payloads, wrinkle presets, control/joint names.'}
    w.write('persistence_data_result.json',result)
elif action=='reproduce':
    w.progress('reproduce_cleanup');w.load();change=w.apply_candidate('safe_full')
    from maya_tools.scripts.utils import scene_evaluation
    scene_evaluation.register('Edward');scene_evaluation.apply()
    label=arguments.get('label','repeat02')
    destination=FOLDER/('saved_variants/Edward_safe_full_'+label+'.mb')
    assert not destination.exists()
    cmds.file(rename=destination.as_posix());cmds.file(save=True,type='mayaBinary')
    w.load(destination);second=fingerprint()
    previous=json.loads((FOLDER/'persistence_saved.json').read_text())
    diff=compare(previous,second)
    result={'accepted':not diff,'differences':diff,'file':str(destination),
            'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
            'changes':{k:len(v.get('removed',[])) if k=='share_math' else v.get('count',v.get('removed_count')) for k,v in change.items()},
            'scope':'Second deterministic cleanup reconstruction from frozen native inputs; not a full CREATE RIG rebuild.'}
    w.write('reproducibility.json',result)
elif action=='skc':
    w.progress('skc_export');w.load(source);cmds.select(clear=True)
    suffix=arguments.get('suffix','')
    manager=make_manager();target=FOLDER/('Edward_exact_lossless'+suffix+'.skc')
    assert not target.exists()
    before=fingerprint();manager.export_skins(str(target))
    full=json.loads(target.read_text())
    polygon={k:v for k,v in full.items() if not k.startswith('__')}
    # Isolate a replacement weight round-trip from a separate deformer rebuild.
    # The native candidate retains the original PRX/corrective/wrinkle graph.
    weight_file=FOLDER/('Edward_exact_weights_only'+suffix+'.skc')
    weight_file.write_text(json.dumps(polygon,separators=(',',':')))
    w.progress('skc_import_weights')
    with w.bw.primary_inputs_for_skin_export():
        manager.import_skins(str(weight_file),replace_existing=True,import_method='index',import_wrinkles=False)
    after=fingerprint();diff=compare(before,after)
    destination=FOLDER/('saved_variants/Edward_safe_full_skc_roundtrip'+suffix+'.mb')
    assert not destination.exists()
    cmds.file(rename=destination.as_posix());cmds.file(save=True,type='mayaBinary')
    result={'accepted':not diff,'differences':diff,'skc':str(target),'bytes':target.stat().st_size,
            'mesh_entries':len(polygon),'skin_entries':sum(len(v) for v in polygon.values()),
            'file':str(destination),'scope':'All exported polygon-skin weight/DQ replacement by index. Original PRX/corrective/wrinkle native graph retained; full deformer/preset rebuild is a separate gate.'}
    w.write('skc_roundtrip.json',result)
else:raise ValueError(action)
