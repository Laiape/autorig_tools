"""Owned Maya trials: full output coverage and exact deformation candidates."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import runpy
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_benchmark as rb, rig_validation as qa
from maya_tools.scripts.tools import pose_blendshapes as pb, bifrost_wrinkles as bw

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
STATE = globals().get('STATE', {})


def write(name, value):
    (FOLDER / name).write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def progress(stage, **values):
    write('progress.json', dict(stage=stage, pid=os.getpid(), **values))


def owned():
    launch = json.loads((FOLDER / 'owned_maya.json').read_text())
    if os.getpid() != launch['pid']:
        raise RuntimeError('Exact optimization trials require the separate owned Maya process.')


def cpu(mode='parallel'):
    cmds.evaluator(name='cache', enable=False)
    cmds.evaluator(name='deformer', enable=False)
    cmds.evaluationManager(mode=mode)


def load(source=None):
    close()
    cpu('off')
    cmds.file(str(source or FOLDER / 'Edward_artist_baseline.mb'), open=True, force=True,
              prompt=False, executeScriptNodes=False)
    cpu()


def path_fn(shape):
    selection = om.MSelectionList(); selection.add(shape)
    path = selection.getDagPath(0)
    return path, om.MFnMesh(path)


def arrays(shape, normals=False):
    path, fn = path_fn(shape)
    value = np.asarray(fn.getPoints(om.MSpace.kWorld))[:, :3].copy()
    if normals:
        return value, np.asarray(fn.getVertexNormals(True, om.MSpace.kWorld)).copy()
    return value


def inventory():
    progress('inventory')
    load()
    meshes = cmds.ls('Edward', dag=True, type='mesh', noIntermediate=True, long=True) or []
    deformer_types = {'skinCluster', 'proximityWrap', 'blendShape', 'deltaMush', 'tension', 'wrap'}
    rows = []
    for shape in meshes:
        path, fn = path_fn(shape)
        counts, vertices = fn.getVertices()
        history = cmds.listHistory(shape, pruneDagObjects=True) or []
        history = [n for n in history if cmds.nodeType(n) in deformer_types]
        rows.append({'shape': shape, 'vertices': fn.numVertices, 'faces': fn.numPolygons,
                     'visible': path.isVisible(), 'history': [{'node': n, 'type': cmds.nodeType(n)} for n in history],
                     'topology': hashlib.sha256(np.asarray(list(counts)+list(vertices), dtype=np.int64).tobytes()).hexdigest(),
                     'uv_sets': {uv: fn.numUVs(uv) for uv in fn.getUVSetNames()},
                     'input': cmds.connectionInfo(shape+'.inMesh', sourceFromDestination=True),
                     'shaders': cmds.listConnections(shape, type='shadingEngine') or [],
                     'world_matrix': list(path.inclusiveMatrix())})
    prx = []
    for node in cmds.ls(type='proximityWrap') or []:
        drivers = []
        for index in cmds.getAttr(node+'.drivers', multiIndices=True) or []:
            base = '%s.drivers[%d].'%(node,index)
            drivers.append({'index': index, 'geometry': cmds.connectionInfo(base+'driverGeometry', sourceFromDestination=True),
                            'bind': cmds.connectionInfo(base+'driverBindGeometry', sourceFromDestination=True)})
        outputs = cmds.deformer(node, query=True, geometry=True) or []
        prx.append({'node': node, 'drivers': drivers, 'geometry': outputs,
                    'settings': {a: cmds.getAttr(node+'.'+a) for a in ('envelope','nodeState','maxDrivers','falloffScale','smoothInfluences')
                                 if cmds.attributeQuery(a,node=node,exists=True)}})
    from maya_tools.scripts.tools import rig_roles
    bindings = rig_roles.bindings('Edward')
    modules = cmds.ls('*Module_GRP',type='transform') or []
    wrinkle_records = bw.export_setups()
    write('wrinkle_source_records.json', wrinkle_records)
    result = {'meshes': rows, 'prx': prx, 'modules': modules, 'bindings': len(bindings),
              'nodes': len(cmds.ls()), 'skins': len(cmds.ls(type='skinCluster') or []),
              'wrinkles': [{'prefix': r['prefix'], 'compact':r.get('compact'), 'in_place':r.get('in_place'),
                            'control_fields':len(r.get('control_fields',[]))} for r in wrinkle_records],
              'scope':'Every nonintermediate mesh under Edward, including every garment, accessory, head/body and hair.'}
    write('inventory.json', result)
    return {'meshes': len(rows), 'prx': len(prx), 'modules':len(modules), 'skins':result['skins'], 'wrinkles':result['wrinkles']}


def prepare(source=None,extended=False):
    progress('prepare')
    load(source)
    cmds.undoInfo(stateWithoutFlush=False)
    cmds.autoKeyframe(state=False)
    if not (FOLDER/'inventory.json').exists():
        inventory()
    audit = runpy.run_path(str(ROOT/'scripts/edward_rig_audit.py'))
    cases, coverage = audit['audit_cases']()
    if extended:
        extra = [
            ('heldout_clothing_twist',{'C_spine03_CTL.rotateZ':25,'C_localChest_CTL.rotateY':-30,'C_neck_CTL.rotateY':40,'C_jaw_CTL.rotateX':35}),
            ('heldout_clothing_limbs',{'L_shoulderFk_CTL.rotateZ':95,'R_shoulderFk_CTL.rotateZ':75,'L_elbowFk_CTL.rotateY':100,'R_hipFk_CTL.rotateZ':85,'R_kneeFk_CTL.rotateZ':100}),
            ('heldout_lips',{'C_jaw_CTL.rotateX':20,'C_jaw_CTL.stickyLips':.5,'L_lipCorner_CTL.translateX':4,'R_lipCorner_CTL.translateY':-2}),
            ('heldout_fine_lips',{'L_upperLip02_CTL.translateX':.2,'R_lowerLip02_CTL.translateX':-.2,'C_upperLip_CTL.Roll':6,'C_lowerLip_CTL.Roll':-6}),
            ('heldout_eyes_brows',{'L_eyeDirect_CTL.Upper_Blink':1,'R_eyeDirect_CTL.Upper_Blink':.5,'R_eyeDirect_CTL.Lower_Blink':1,'L_eyebrowIn_CTL.translateY':2,'R_eyebrowIn_CTL.translateY':-2}),
            ('heldout_hands',{'L_thumb01_CTL.rotateZ':20,'R_thumb01_CTL.rotateZ':-15,'L_ring01_CTL.rotateZ':50,'R_pinky01_CTL.rotateZ':45}),
            ('heldout_global_scale',{'C_masterwalk_CTL.globalScale':1.15}),
            ('heldout_nonuniform_scale',{'C_character_CTL.scaleX':1.05,'C_character_CTL.scaleY':.95,'C_character_CTL.scaleZ':1.1}),
        ]
        STATE['omitted_optional_channels'] = []
        for name,values in extra:
            valid={p:v for p,v in values.items() if cmds.objExists(p) and cmds.getAttr(p,settable=True)}
            STATE['omitted_optional_channels'] += [p for p in values if p not in valid]
            if valid:cases.append((name,valid))
    from maya_tools.scripts.tools import rig_roles
    original = rig_roles.bindings
    bindings = original('Edward')
    try:
        rig_roles.bindings = lambda root: bindings
        resolved, missing, skipped = qa.resolve_cases('Edward', cases)
    finally:
        rig_roles.bindings = original
    if missing:
        raise RuntimeError(missing)
    stack = ExitStack()
    STATE['stack'] = stack
    stack.enter_context(pb._temporary_values(resolved[0]['values']))
    workload = stack.enter_context(rb.temporal_workload(resolved,(1,48)))
    STATE.update(resolved=resolved, coverage=coverage, workload=workload,extended=extended,
                 shapes=[r['shape'] for r in json.loads((FOLDER/'inventory.json').read_text())['meshes']],
                 original_head_input=cmds.connectionInfo('cabeza_high_Shape.inMesh',sourceFromDestination=True))
    cmds.playbackOptions(minTime=1,maxTime=48,animationStartTime=1,animationEndTime=48)
    cmds.currentTime(1);cmds.refresh(force=True)
    write('workload.json',{'cases':resolved,'coverage':coverage,'workload':workload,'skipped':skipped})
    progress('prepared', meshes=len(STATE['shapes']),channels=len(workload['animated_channels']))
    return {'meshes':len(STATE['shapes']),'channels':len(workload['animated_channels']),'modules':list(coverage)}


def close():
    if STATE.get('stack'):
        cpu('off')
        STATE['stack'].close()
    STATE.clear()


def wrinkles(enabled):
    source = 'EdwardWrinkles_ToMaya.mayaMesh[0]' if enabled else 'cabeza_high_poseCorrectives_BLS.outputGeometry[0]'
    if cmds.connectionInfo('cabeza_high_Shape.inMesh',sourceFromDestination=True) != source:
        cpu('off')
        cmds.connectAttr(source,'cabeza_high_Shape.inMesh',force=True)
    cpu()


def configure(mode, blocks=None, policy='on'):
    cpu('off')
    if mode != 'cpu' or blocks:
        cmds.deformerEvaluator(purge=True)
    if blocks:
        cmds.deformerEvaluator(blocks,gpuBlockPolicy=policy)
    cmds.evaluationManager(mode='parallel')
    cmds.currentTime(1);cmds.refresh(force=True)
    if mode == 'gpu':
        cmds.evaluator(name='deformer',enable=True)
    elif mode == 'cache':
        cmds.evaluator(name='deformer',enable=True)
        cmds.cacheEvaluator(cacheFillMode='syncAsync')
        cmds.evaluator(name='cache',enable=True)


def clear_blocks():
    nodes = list(cmds.ls(type='proximityWrap') or [])
    nodes += [s for s in STATE.get('shapes',[]) if 'collar' in s.lower()]
    if nodes:
        cmds.deformerEvaluator(nodes,gpuBlockPolicy='off')


def quality_probe():
    if not STATE.get('stack'):
        prepare()
    shapes = STATE['shapes']
    collar_shapes = [s for s in shapes if 'collar' in s.lower()]
    candidates = [('gpu_normal',[], 'on'),
                  ('gpu_collars_on',['collar2_PRX','collar3_PRX'],'on'),
                  ('gpu_collars_upstream_mesh',['collar2_PRX','collar3_PRX'],'upstreamMesh'),
                  ('gpu_collar_outputs_upstream',collar_shapes,'upstream'),
                  ('gpu_all_prx_on',cmds.ls(type='proximityWrap') or [],'on')]
    frames = (1,8,16,24,32,40,48,24,8,1)
    rows = []
    for enabled in (False,True):
        wrinkles(enabled)
        clear_blocks()
        configure('cpu')
        reference = {}
        for index, frame in enumerate(frames):
            progress('cpu_reference',wrinkles=enabled,index=index)
            cmds.currentTime(frame);cmds.refresh(force=True)
            for shape in shapes:
                reference[(index,shape)] = arrays(shape)
        for label,blocks,policy in candidates:
            progress('quality_candidate',label=label,wrinkles=enabled)
            clear_blocks()
            configure('gpu',blocks,policy)
            rb._play_once((1,48))
            errors = {s:0. for s in shapes}
            for index,frame in enumerate(frames):
                cmds.currentTime(frame);cmds.refresh(force=True)
                for shape in shapes:
                    errors[shape] = max(errors[shape],float(np.linalg.norm(arrays(shape)-reference[(index,shape)],axis=1).max()))
            query = {}
            if blocks:
                try:
                    query['policy'] = cmds.deformerEvaluator(blocks,query=True,gpuBlockPolicy=True)
                    query['status'] = cmds.deformerEvaluator(blocks,query=True,nodeStatus=True,asText=True)
                except Exception as error:
                    query['error'] = str(error)
            maximum = max(errors.values())
            row={'label':label,'wrinkles':enabled,'blocks':blocks,'policy':policy,'query':query,
                 'errors':errors,'max_error':maximum,'accepted':maximum<=1e-4,'outputs':len(shapes),'frames':list(frames)}
            rows.append(row)
            write('quality_probe.json',rows)
    clear_blocks()
    configure('cpu')
    return [{k:r[k] for k in ('label','wrinkles','max_error','accepted','query')} for r in rows]


def upstream_probe():
    """Bounded upstream isolation; no weight or deformation changes."""
    prepare()
    inventory = json.loads((FOLDER/'inventory.json').read_text())
    head_nodes = sorted({h['node'] for row in inventory['meshes'] if 'collar' in row['shape'].lower()
                         for h in row['history'] if h['type'] != 'proximityWrap'})
    collar_nodes = ['collar2_PRX','collar3_PRX']
    all_skin = cmds.ls(type='skinCluster') or []
    all_prx = cmds.ls(type='proximityWrap') or []
    all_blend = cmds.ls(type='blendShape') or []
    all_nodes = sorted(set(head_nodes+all_skin+all_prx+all_blend+['EdwardWrinkles_PrimaryWorld']))
    frames = (1,16,32,48,24,1)
    rows = []
    for enabled in (False,True):
        wrinkles(enabled)
        cmds.deformerEvaluator(all_nodes,gpuBlockPolicy='off')
        configure('cpu');rb._play_once((1,48))
        reference = {}
        for index,frame in enumerate(frames):
            cmds.currentTime(frame);cmds.refresh(force=True)
            for shape in STATE['shapes']:reference[(index,shape)] = arrays(shape)
        for label,blocks in [('head_skins_cpu',head_nodes),('head_and_collars_cpu',head_nodes+collar_nodes),
                             ('all_skins_cpu',all_skin),('all_skins_and_prx_cpu',all_skin+all_prx),
                             ('all_deformers_cpu',all_skin+all_prx+all_blend),('cpu_bookend',[])]:
            progress('upstream_probe',label=label,wrinkles=enabled)
            cpu('off');cmds.deformerEvaluator(all_nodes,gpuBlockPolicy='off')
            configure('cpu' if label=='cpu_bookend' else 'gpu',blocks)
            rb._play_once((1,48))
            errors={s:0. for s in STATE['shapes']}
            for index,frame in enumerate(frames):
                cmds.currentTime(frame);cmds.refresh(force=True)
                for shape in errors:
                    errors[shape]=max(errors[shape],float(np.linalg.norm(arrays(shape)-reference[(index,shape)],axis=1).max()))
            row={'label':label,'wrinkles':enabled,'max_error':max(errors.values()),'errors':errors,
                 'accepted':max(errors.values())<=1e-4,'blocks':blocks,
                 'gpu_status':cmds.deformerEvaluator(blocks,query=True,nodeStatus=True,asText=True) if blocks else [],
                 'frames':list(frames),'outputs':len(errors)}
            rows.append(row);write('upstream_probe.json',rows)
    cpu('off');cmds.deformerEvaluator(all_nodes,gpuBlockPolicy='off');cpu()
    return [{k:r[k] for k in ('label','wrinkles','max_error','accepted')} for r in rows]


def static_opportunities():
    """Inspect exact-zero skin columns and constant scalp point curves."""
    load()
    from maya.api import OpenMayaAnim as oma
    skins=[]
    with bw.primary_inputs_for_skin_export():
        for node in cmds.ls(type='skinCluster') or []:
            fn=oma.MFnSkinCluster(om.MSelectionList().add(node).getDependNode(0))
            influences=fn.influenceObjects()
            nonzero=np.zeros(len(influences),dtype=bool)
            supported=True
            for geometry in fn.getOutputGeometry():
                if not geometry.hasFn(om.MFn.kMesh):supported=False;break
                path=om.MDagPath.getAPathTo(geometry);mesh=om.MFnMesh(path)
                c=om.MFnSingleIndexedComponent();component=c.create(om.MFn.kMeshVertComponent);c.setCompleteData(mesh.numVertices)
                weights,count=fn.getWeights(path,component)
                nonzero|=np.any(np.asarray(weights).reshape((mesh.numVertices,count))!=0,axis=0)
            unused=[p.fullPathName() for index,p in enumerate(influences) if not nonzero[index]] if supported else []
            skins.append({'skin':node,'influences':len(influences),'unused_zero_weight_influences':unused,'supported_mesh':supported})
    curves=[]
    for node in cmds.ls(type='animCurveTL') or []:
        if cmds.listConnections(node+'.input',source=True,destination=False):continue
        destinations=cmds.listConnections(node+'.output',source=False,destination=True,plugs=True) or []
        if len(destinations)!=1 or '.pnts[' not in destinations[0] or 'scalp' not in destinations[0].lower():continue
        curves.append({'node':node,'destination':destinations[0],'value':cmds.getAttr(destinations[0]),
                       'keys':cmds.keyframe(node,query=True,keyframeCount=True)})
    result={'skins':skins,'static_point_curves':curves,
            'counts':{'unused_influences':sum(len(s['unused_zero_weight_influences']) for s in skins),
                      'affected_skins':sum(bool(s['unused_zero_weight_influences']) for s in skins),'static_point_curves':len(curves)}}
    write('static_opportunities.json',result)
    return result['counts']


def apply_candidate(candidate):
    cpu('off')
    from importlib import reload
    from maya_tools.scripts.tools import rig_exact_cleanup
    reload(rig_exact_cleanup)
    result={}
    if candidate in ('share_math','safe_full','math_static'):
        from maya_tools.scripts.tools import rig_exact_cleanup
        result['share_math']=rig_exact_cleanup.share_identical_lip_math()
    if candidate in ('jaw','combined','full'):
        from maya_tools.scripts.tools import jaw_graph_optimizer
        result['jaw']=jaw_graph_optimizer.optimize()
    if candidate in ('static_points','combined','full','zero_static','safe_full','math_static'):
        from maya_tools.scripts.tools import rig_exact_cleanup
        scalp=[s for s in STATE.get('shapes',[]) if 'scalp' in s.lower()]
        if not scalp:
            scalp=[s for s in cmds.ls(type='mesh',long=True) or [] if 'scalp' in s.lower() and not cmds.getAttr(s+'.intermediateObject')]
        result['static_points']=rig_exact_cleanup.bake_static_point_curves(scalp,apply=True)
    if candidate in ('zero_influences','full','zero_static','safe_full'):
        from maya_tools.scripts.tools import rig_exact_cleanup
        frozen=json.loads((FOLDER/'static_opportunities.json').read_text())
        skins=[r['skin'] for r in frozen['skins'] if r['unused_zero_weight_influences']]
        result['zero_influences']=rig_exact_cleanup.remove_exact_zero_influences(skins,apply=True)
    if candidate not in ('original','jaw','static_points','combined','cache','zero_influences','full','zero_static','share_math','safe_full','math_static'):
        raise ValueError(candidate)
    cpu()
    return result


def quality_reference():
    prepare(extended=True)
    from maya.api import OpenMayaAnim as oma
    paths=[om.MSelectionList().add(n).getDagPath(0) for n in cmds.ls('Edward',dag=True,type='joint',long=True) or []]
    frames=[1.+47.*i/(len(STATE['resolved'])-1) for i in range(len(STATE['resolved']))]
    frames=frames+list(reversed(frames))
    points={};meta={'frames':frames,'shapes':STATE['shapes'],'joints':[p.fullPathName() for p in paths],
                   'coverage':STATE['coverage'],'omitted_optional_channels':STATE.get('omitted_optional_channels',[])}
    for enabled in (False,True):
        wrinkles(enabled);configure('cpu')
        rb._play_once((1,48))
        for index,frame in enumerate(frames):
            progress('exact_reference',wrinkles=enabled,index=index,total=len(frames))
            cmds.currentTime(frame);cmds.refresh(force=True)
            for mesh_index,shape in enumerate(STATE['shapes']):
                p,n=arrays(shape,normals=True)
                points['p_%d_%d_%d'%(enabled,index,mesh_index)]=p
                points['n_%d_%d_%d'%(enabled,index,mesh_index)]=n
            points['j_%d_%d'%(enabled,index)]=np.asarray([list(p.inclusiveMatrix()) for p in paths])
    np.savez_compressed(FOLDER/'exact_reference.npz',**points)
    write('exact_reference.json',meta)
    return {'poses_per_mode':len(frames),'outputs':len(STATE['shapes']),'joints':len(paths),'missing':meta['omitted_optional_channels']}


def exact_quality(candidate,source=None,label=None):
    label=label or candidate
    prepare(source,extended=True)
    change=apply_candidate(candidate)
    reference=np.load(FOLDER/'exact_reference.npz')
    metadata=json.loads((FOLDER/'exact_reference.json').read_text())
    assert STATE['shapes']==metadata['shapes']
    paths=[om.MSelectionList().add(n).getDagPath(0) for n in metadata['joints']]
    rows=[]
    for enabled in (False,True):
        wrinkles(enabled);configure('cache' if candidate=='cache' else 'cpu')
        rb._play_once((1,48))
        if candidate=='cache':cmds.cacheEvaluator(waitForCache=10.)
        errors={s:0. for s in STATE['shapes']};normals=dict(errors);matrix_error=0.
        for index,frame in enumerate(metadata['frames']):
            progress('exact_quality',candidate=label,wrinkles=enabled,index=index,total=len(metadata['frames']))
            cmds.currentTime(frame);cmds.refresh(force=True)
            for mesh_index,shape in enumerate(STATE['shapes']):
                p,n=arrays(shape,normals=True)
                errors[shape]=max(errors[shape],float(np.linalg.norm(p-reference['p_%d_%d_%d'%(enabled,index,mesh_index)],axis=1).max()))
                normals[shape]=max(normals[shape],float(np.linalg.norm(n-reference['n_%d_%d_%d'%(enabled,index,mesh_index)],axis=1).max()))
            matrices=np.asarray([list(p.inclusiveMatrix()) for p in paths])
            matrix_error=max(matrix_error,float(np.abs(matrices-reference['j_%d_%d'%(enabled,index)]).max()))
        row={'wrinkles':enabled,'errors':errors,'normal_errors':normals,'matrix_error':matrix_error,
             'max_error':max(errors.values()),'max_normal_error':max(normals.values()),
             'accepted':max(errors.values())<=1e-4 and max(normals.values())<=1e-4 and matrix_error<=1e-4,
             'meshes':len(errors),'samples':len(metadata['frames'])*len(errors)}
        rows.append(row)
        write(label+'.quality.json',{'candidate':candidate,'label':label,'rows':rows,'change':change,'reference':'Current artist snapshot, Parallel CPU',
                                     'accepted':all(r['accepted'] for r in rows)})
    return {'candidate':label,'change_counts':{k:len(v.get('removed',[])) if k in ('jaw','share_math') else v.get('count',v.get('removed_count')) for k,v in change.items()},
            'accepted':all(r['accepted'] for r in rows),'rows':[{k:r[k] for k in ('wrinkles','max_error','max_normal_error','matrix_error','accepted','samples')} for r in rows]}


def timing_series(candidates):
    """Interleaved clean timings; no geometry/Profiler calls inside samples."""
    order=['original']+list(candidates)+['original']+list(reversed(candidates))+['original']
    rows=[]
    from maya.api import OpenMayaUI as omui
    size=None
    for enabled in (False,True):
        for index,candidate in enumerate(order):
            label='timing_w%d_%02d_%s'%(enabled,index,candidate)
            if (FOLDER/(label+'.performance.json')).exists():
                rows.append(json.loads((FOLDER/(label+'.performance.json')).read_text()))
                continue
            progress('timing_prepare',candidate=candidate,wrinkles=enabled,index=index,total=len(order))
            prepare();change=apply_candidate(candidate);wrinkles(enabled)
            configure('cache' if candidate=='cache' else 'cpu')
            view=omui.M3dView.active3dView();current_size=[view.portWidth(),view.portHeight()]
            if size is None:size=current_size
            if size!=current_size:raise RuntimeError('Viewport size changed during the comparison.')
            progress('timing_warmup',candidate=candidate,wrinkles=enabled,index=index)
            start=time.perf_counter();rb._play_once((1,48));warmup=time.perf_counter()-start
            if candidate=='cache':cmds.cacheEvaluator(waitForCache=10.)
            runs=[]
            for repeat in range(3):
                progress('timing',candidate=candidate,wrinkles=enabled,index=index,repeat=repeat)
                runs.append(rb._play_once((1,48))[8:])
            row={'candidate':candidate,'label':label,'wrinkles':enabled,'index':index,'viewport':size,
                 'state':'D' if candidate=='cache' else 'B','raw_runs_ms':runs,
                 'runs':[rb.statistics_ms(v) for v in runs],
                 'timing':rb.statistics_ms([v for run in runs for v in run]),'warmup_seconds':warmup,
                 'workload':STATE['workload'],'coverage':STATE['coverage'],
                 'measurement':'currentTime plus forced VP2 refresh wall time; 3 x 40 retained samples, complete warmup; no geometry reads or Profiler within timing.',
                 'native_original_routes':{'body':cmds.connectionInfo('cuerpo_base_Shape.inMesh',sourceFromDestination=True),
                                           'belt':cmds.connectionInfo('cinturon3_PRX.drivers[0].driverGeometry',sourceFromDestination=True)},
                 'change_counts':{k:len(v.get('removed',[])) if k in ('jaw','share_math') else v.get('count',v.get('removed_count')) for k,v in change.items()}}
            write(label+'.performance.json',row);rows.append(row)
            write('timing_series.json',rows)
    return [{k:r[k] for k in ('candidate','wrinkles','timing')} for r in rows]


def profiles(candidate):
    rows=[]
    for selected in ('original',candidate):
        for enabled in (False,True):
            label='profile_%s_w%d'%(selected,enabled)
            if (FOLDER/(label+'.json')).exists():continue
            source=FOLDER/'saved_variants'/('Edward_'+selected+'.mb')
            prepare(source);wrinkles(enabled);configure('cpu')
            rb._play_once((1,48))
            progress('profiler',candidate=selected,wrinkles=enabled)
            buffer=cmds.profiler(query=True,bufferSize=True)
            cmds.profiler(reset=True);cmds.profiler(bufferSize=256);cmds.profiler(sampling=True)
            try:
                rb._play_once((1,48))
                complete=cmds.profiler(query=True,sampling=True)
            finally:cmds.profiler(sampling=False)
            target=FOLDER/(label+'.txt')
            cmds.profiler(output=target.as_posix())
            nodes={};iterator=om.MItDependencyNodes()
            while not iterator.isDone():
                obj=iterator.thisNode();fn=om.MFnDependencyNode(obj)
                nodes[fn.name()]={'type':fn.typeName}
                iterator.next()
            row={'candidate':selected,'wrinkles':enabled,'frames':48,'buffer_mb':256,
                 'buffer_not_exhausted':bool(complete),'events':cmds.profiler(query=True,eventCount=True),
                 'nodes':nodes,'file':str(target),'source':str(source),'workload':STATE['workload'],
                 'meaning':'Inclusive diagnostic CPU; not additive wall time or FPS.'}
            write(label+'.json',row);rows.append({'label':label,'events':row['events'],'complete':bool(complete)})
            cmds.profiler(bufferSize=buffer)
    return rows


def save_variants(candidates):
    from maya_tools.scripts.utils import scene_evaluation
    output=FOLDER/'saved_variants';output.mkdir(exist_ok=True)
    rows=[]
    for candidate in ['original']+list(candidates):
        path=output/('Edward_'+candidate+'.mb')
        if path.exists():continue
        progress('save_variant',candidate=candidate)
        load();change=apply_candidate(candidate)
        scene_evaluation.register('Edward');scene_evaluation.apply()
        cmds.currentTime(json.loads((FOLDER/'snapshot.json').read_text())['artist_state']['frame'])
        cmds.file(rename=path.as_posix());cmds.file(save=True,type='mayaBinary',force=False)
        row={'candidate':candidate,'file':str(path),'bytes':path.stat().st_size,
             'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'nodes':len(cmds.ls()),
             'temporary_curves':cmds.ls('rigBenchmarkTemporaryCurve*') or [],'change':change,
             'head_source':cmds.connectionInfo('cabeza_high_Shape.inMesh',sourceFromDestination=True)}
        assert not row['temporary_curves']
        rows.append(row);write('saved_variants.json',rows)
    return [{k:r[k] for k in ('candidate','file','bytes','nodes','head_source')} for r in rows]


def reopened_timings(candidates,skip_cache=False):
    """Benchmark persisted scenes, with undo disabled before animation setup."""
    order=['original']+list(candidates)+['original']+list(reversed(candidates))+['original']
    from maya.api import OpenMayaUI as omui
    rows=[];size=None;rejected=set();reference_medians={}
    for enabled in (False,True):
        for index,candidate in enumerate(order):
            if skip_cache and candidate=='cache':continue
            if candidate in rejected:continue
            label='reopened_w%d_%02d_%s'%(enabled,index,candidate)
            if (FOLDER/(label+'.performance.json')).exists():
                rows.append(json.loads((FOLDER/(label+'.performance.json')).read_text()));continue
            progress('reopened_load',candidate=candidate,wrinkles=enabled,index=index)
            source=FOLDER/'saved_variants'/('Edward_'+('original' if candidate=='cache' else candidate)+'.mb')
            prepare(source);wrinkles(enabled);configure('cache' if candidate=='cache' else 'cpu')
            view=omui.M3dView.active3dView();current=[view.portWidth(),view.portHeight()]
            if size is None:size=current
            if size!=current:raise RuntimeError('Viewport changed during reopened comparison.')
            progress('reopened_warmup',candidate=candidate,wrinkles=enabled,index=index)
            start=time.perf_counter();rb._play_once((1,48));warmup=time.perf_counter()-start
            if candidate=='cache':cmds.cacheEvaluator(waitForCache=10.)
            if candidate!='original' and enabled in reference_medians:
                screening=rb._play_once((1,12))[2:]
                screen=rb.statistics_ms(screening)
                if screen['median_ms']>reference_medians[enabled]*2:
                    rejected.add(candidate)
                    write(label+'.rejected_screen.json',{'candidate':candidate,'wrinkles':enabled,'screening':screen,
                          'baseline_median':reference_medians[enabled],'reason':'Severe reopened regression >2x reference; do not promote this candidate.'})
                    continue
            runs=[]
            for repeat in range(3):
                progress('reopened_timing',candidate=candidate,wrinkles=enabled,index=index,repeat=repeat)
                runs.append(rb._play_once((1,48))[8:])
            row={'candidate':candidate,'label':label,'wrinkles':enabled,'viewport':size,
                 'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                 'state':'D' if candidate=='cache' else 'B','undo_enabled':cmds.undoInfo(query=True,state=True),
                 'raw_runs_ms':runs,'runs':[rb.statistics_ms(v) for v in runs],
                 'timing':rb.statistics_ms([v for run in runs for v in run]),'warmup_seconds':warmup,
                 'workload':STATE['workload'],'coverage':STATE['coverage'],
                 'measurement':'Reopened native scene; undo OFF; currentTime plus forced VP2 refresh. Warmup48,3x40 retained samples. No mesh reads or Profiler inside timing.'}
            write(label+'.performance.json',row);rows.append(row);write('reopened_timings.json',rows)
            if candidate=='original':reference_medians[enabled]=row['timing']['median_ms']
    return [{k:r[k] for k in ('candidate','wrinkles','timing')} for r in rows]


def payloads():
    """Every baked output; native selected-skin exports are unsafe here."""
    load(FOLDER/'saved_variants/Edward_safe_full.mb')
    folder=FOLDER/'payloads';folder.mkdir(exist_ok=True)
    rows=[]
    shapes=[r['shape'] for r in json.loads((FOLDER/'inventory.json').read_text())['meshes']]
    for index,shape in enumerate(shapes):
        progress('payload_mesh',index=index,total=len(shapes))
        path,fn=path_fn(shape)
        duplicate=om.MFnMesh().copy(path.node())
        root=om.MFnDagNode(duplicate).fullPathName()
        try:
            target=folder/('mesh_%02d.mb'%index)
            cmds.select([root]+(cmds.listRelatives(root,allDescendents=True,fullPath=True) or []),replace=True,noExpand=True)
            if not target.exists():cmds.file(target.as_posix(),exportSelectedStrict=True,type='mayaBinary',force=False)
            rows.append({'kind':'baked_mesh','node':shape,'bytes':target.stat().st_size,'file':str(target)})
        finally:cmds.delete(root)
    result={'payloads':rows,'meaning':'Baked native mesh copies without rig/history/material networks. Native selected-skin export crashed this Maya/Bifrost installation; use exact SKC entries for weight bytes and preserve the failure record. Includes headers; not additive scene savings or RAM.'}
    write('payloads_geometry.json',result)
    return {'meshes':len(rows),'native_skin_export':'excluded_after_native_crash'}


def run(arguments):
    owned()
    action = arguments['action']
    if action == 'inventory':return inventory()
    if action == 'prepare':return prepare()
    if action == 'quality_probe':return quality_probe()
    if action == 'upstream_probe':return upstream_probe()
    if action == 'static_opportunities':return static_opportunities()
    if action == 'quality_reference':return quality_reference()
    if action == 'exact_quality':return exact_quality(arguments['candidate'],arguments.get('source'),arguments.get('label'))
    if action == 'timing_series':return timing_series(arguments['candidates'])
    if action == 'profiles':return profiles(arguments['candidate'])
    if action == 'save_variants':return save_variants(arguments['candidates'])
    if action == 'reopened_timings':return reopened_timings(arguments['candidates'],arguments.get('skip_cache',False))
    if action == 'payloads':return payloads()
    if action == 'close':close();return {'closed':True}
    raise ValueError(action)
