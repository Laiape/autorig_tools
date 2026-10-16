"""Bounded final audit captures. Operates only on versioned Edward snapshots.

No module mass-freezing: that diagnostic stalled Maya and is not a valid result.
Profiler data is captured separately from clean wall-clock timing.
"""
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'autorig_tools'))
import edward_driver_routing_trial as routing
from maya import cmds, mel
from maya_tools.scripts.tools import rig_benchmark as rb, rig_validation as qa, pose_blendshapes as pb

audit = runpy.run_path(str(ROOT / 'scripts/edward_rig_audit.py'))
FOLDER = audit['FOLDER']
ARGS = globals().get('TRIAL_ARGUMENTS', {})

def write(name, value):
    (FOLDER / name).write_text(json.dumps(value, indent=2, default=str), encoding='utf-8')

def progress(**value):
    write('final_progress.json', dict(pid=os.getpid(), **value))

def resolved_workload(cases):
    # The generic resolver repeatedly scans semantic roles for every explicit
    # channel. Cache discovery during this read-only preparation only; pose
    # values, FK switches and neutral defaults remain exactly the same.
    from maya_tools.scripts.tools import rig_roles
    original=rig_roles.bindings
    cache={}
    def cached(root):
        key=cmds.ls(root,long=True)[0]
        if key not in cache:cache[key]=original(root)
        return cache[key]
    try:
        rig_roles.bindings=cached
        return qa.resolve_cases('Edward',cases)
    finally:
        rig_roles.bindings=original

@contextmanager
def animated(variant='original', wrinkles=False):
    progress(stage='load_snapshot',variant=variant,wrinkles=wrinkles)
    routing.load(variant)
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4',e=True,displayAppearance='smoothShaded',displayTextures=False,
                     shadows=False,selectionHiliteDisplay=False,rendererName='vp2Renderer')
    cmds.refresh(force=True)
    progress(stage='route_wrinkles',variant=variant,wrinkles=wrinkles)
    routing.wrinkle(wrinkles, variant)
    cases, channels = audit['audit_cases']()
    resolved, missing, _ = resolved_workload(cases)
    if missing:
        raise RuntimeError(missing)
    initial = {p: cmds.getAttr(p) for p in resolved[0]['values']}
    auto = cmds.autoKeyframe(q=True, state=True)
    undo = cmds.undoInfo(q=True, state=True)
    cmds.autoKeyframe(state=False)
    cmds.undoInfo(stateWithoutFlush=False)
    try:
        progress(stage='create_animation',variant=variant,wrinkles=wrinkles)
        with pb._temporary_values(resolved[0]['values']), rb.temporal_workload(resolved, (1, 48)) as workload:
            progress(stage='animation_ready',variant=variant,wrinkles=wrinkles)
            yield dict(channels=channels, workload=workload,
                       verified_fk={p:cmds.getAttr(p) for p in resolved[0]['values'] if p.endswith('.Ik_Fk')})
    finally:
        cmds.evaluator(name='cache', enable=False)
        cmds.evaluator(name='deformer', enable=False)
        cmds.evaluationManager(mode='parallel')
        cmds.autoKeyframe(state=auto)
        cmds.undoInfo(stateWithoutFlush=undo)

def configure(state):
    mode, gpu, cache = rb.STATES[state]
    cmds.evaluator(name='cache', enable=False)
    cmds.evaluator(name='deformer', enable=False)
    cmds.evaluationManager(mode=mode)
    cmds.currentTime(1)
    cmds.refresh(force=True)
    if gpu:
        cmds.deformerEvaluator(purge=True)
        cmds.evaluator(name='deformer', enable=True)
    if cache:
        cmds.cacheEvaluator(cacheFillMode='syncAsync')
        cmds.evaluator(name='cache', enable=True)

def timed(label, environment, workload, state='C', intervention=None):
    path = FOLDER / (label + '.performance.json')
    if path.exists():
        return json.loads(path.read_text())
    progress(stage='configure', label=label, state=state)
    configure(state)
    progress(stage='warmup', label=label)
    start = time.perf_counter()
    rb._play_once((1, 48))
    warmup = time.perf_counter() - start
    if state == 'D':
        cmds.cacheEvaluator(waitForCache=10.)
    runs = []
    for repeat in range(3):
        progress(stage='timing', label=label, repeat=repeat + 1)
        runs.append(rb._play_once((1, 48))[8:])
    report = dict(format='edward-final-audit', label=label, cohort='final_pid'+str(os.getpid()),
                  state=state, environment=environment, workload=workload, frames=[1,48],
                  repeats=3, discard_per_pass=8, warmup_seconds=warmup,
                  measurement='currentTime + forced VP2 refresh wall time; no Profiler or mesh reads inside timing',
                  raw_runs_ms=runs, runs=[rb.statistics_ms(r) for r in runs],
                  timing=rb.statistics_ms([s for r in runs for s in r]),
                  intervention=intervention, diagnostics=rb.diagnostics(), memory=audit['memory']())
    from maya.api import OpenMayaUI as omui
    view=omui.M3dView.active3dView()
    report['viewport_after_timing']={'width':view.portWidth(),'height':view.portHeight(),
                                     'visible_panels':cmds.getPanel(visiblePanels=True),
                                     'view_panes_configuration':cmds.paneLayout('viewPanes',q=True,configuration=True)}
    write(path.name, report)
    return report

def components():
    rows = []
    # Native bypass tests, with fresh reference measurements between groups.
    scenarios = [(n, i) for n, i in audit['component_scenarios']() if not n.startswith('module_')]
    if ARGS.get('labels'):
        scenarios=[r for r in scenarios if r[0] in ARGS['labels'] or r[0].startswith('reference')]
    with animated() as workload:
        environment = rb.environment('Edward')
        write('final_environment.json', environment)
        for name, intervention in scenarios:
            label = ARGS.get('prefix','final_component_') + name
            if (FOLDER / (label+'.performance.json')).exists():
                continue
            progress(stage='component_prepare', label=label)
            context = (audit['bypass_deformers'](intervention['nodes']) if intervention
                       else nullcontext({'mechanism':'Normal reference'}))
            with context as changed:
                rows.append(timed(label, environment, workload, intervention=changed)['timing'])
    return rows

def profiles():
    results=[]
    for wrinkles in (False, True):
        label=ARGS.get('prefix','final_profile_wrinkles')+str(int(wrinkles))
        if (FOLDER/(label+'.json')).exists():
            continue
        with animated(wrinkles=wrinkles) as workload:
            configure('C'); rb._play_once((1,48))
            progress(stage='profiler', label=label)
            buffer = cmds.profiler(q=True, bufferSize=True)
            cmds.profiler(reset=True);cmds.profiler(bufferSize=256)
            cmds.profiler(sampling=True)
            start=time.perf_counter()
            try:
                rb._play_once((1,48))
                still_sampling=cmds.profiler(q=True,sampling=True)
            finally:
                cmds.profiler(sampling=False)
            file=FOLDER/(label+'.txt')
            cmds.profiler(output=file.as_posix())
            meta=dict(file=str(file),frames=48,wrinkles=wrinkles,workload=workload,
                      events=cmds.profiler(q=True,eventCount=True),buffer_mb=256,
                      buffer_not_exhausted=bool(still_sampling),wall_seconds=time.perf_counter()-start,
                      meaning='Diagnostic inclusive CPU events; overlapping events do not add to frame wall time.',
                      environment=rb.environment('Edward'))
            write(label+'.json',meta);results.append(meta)
            cmds.profiler(bufferSize=buffer)
    return results

def routing_repeat():
    rows=[]
    # Original is a separate artistic result. New variants are compared to direct.
    pairs=[('original',False),('original',True),('face_driver',True),('direct',True),
           ('shared_wrinkles',True),('shared',True),('body_driver',True),
           ('shared',False),('shared_wrinkles',False),('direct',False),
           ('face_driver',False),('body_driver',False),('direct',True),('face_driver',True)]
    for index,(variant, wrinkles) in enumerate(pairs):
        label='final_routing_%02d_%s_w%d'%(index,variant,wrinkles)
        if (FOLDER/(label+'.performance.json')).exists():continue
        progress(stage='routing_load',label=label)
        with animated(variant,wrinkles) as workload:
            row=timed(label,rb.environment('Edward'),workload)
            row.update(variant=variant,wrinkles=wrinkles)
            write(label+'.performance.json',row);rows.append(row['timing'])
    return rows

def states():
    rows=[]
    with animated() as workload:
        env=rb.environment('Edward')
        for state in ('C','B','A','D','C'):
            label='final_states_'+state+('_bookend' if state=='C' and rows else '')
            rows.append(timed(label,env,workload,state=state)['timing'])
    return rows

def display_tests():
    from maya_tools.scripts.tools import rig_performance as rp
    rows=[]
    with animated() as workload:
        env=rb.environment('Edward')
        rows.append(timed('final_display_reference',env,workload)['timing'])
        # Visibility is an animation LOD test: upstream evaluation may also be
        # pruned. It is not reported as isolated raster cost.
        old=cmds.getAttr('cabello_geo.visibility')
        try:
            cmds.evaluator(name='deformer',enable=False)
            cmds.setAttr('cabello_geo.visibility',False)
            rows.append(timed('final_display_hide_hair',env,workload,
                              intervention={'meaning':'Animation LOD, polygon hair hidden; may also prune its skin branch.'})['timing'])
        finally:cmds.setAttr('cabello_geo.visibility',old)
        panels=cmds.getPanel(type='modelPanel') or []
        previous={p:cmds.modelEditor(p,q=True,nurbsCurves=True) for p in panels}
        try:
            for p in panels:cmds.modelEditor(p,e=True,nurbsCurves=False)
            rows.append(timed('final_display_hide_control_curves',env,workload,
                              intervention={'meaning':'Viewport NURBS curves hidden; includes construction curves and controls.'})['timing'])
        finally:
            for p,value in previous.items():cmds.modelEditor(p,e=True,nurbsCurves=value)
        rp.set_detail_mode('Edward',0)
        routing.wrinkle(False,'original')
        rows.append(timed('final_display_low_detail',env,workload,
                          intervention={'meaning':'Existing native low detail mode. High face may remain needed by collar drivers.'})['timing'])
        rp.set_detail_mode('Edward',1);routing.wrinkle(False,'original')
        rows.append(timed('final_display_reference_end',env,workload)['timing'])
    return rows

def quality_extended():
    import numpy as np
    rows=[]
    # Direct is the common artistic baseline of the new routing prototypes.
    # Captures all display outputs while exercising all 18 modules, both orders.
    names=None;baseline={};off_faces={};wrinkle_displacement=0.
    for wrinkles in (False,True):
        baseline={}
        for variant in ('direct','shared','shared_wrinkles','body_driver','face_driver'):
            label='final_quality_%s_w%d'%(variant,wrinkles)
            progress(stage='quality_load',label=label)
            routing.load(variant);routing.wrinkle(wrinkles,variant)
            cases,channels=audit['audit_cases']();resolved,missing,_=resolved_workload(cases)
            if missing:raise RuntimeError(missing)
            initial={p:cmds.getAttr(p) for p in resolved[0]['values']}
            names=routing.meshes();errors={n:0. for n in names}
            cmds.evaluationManager(mode='parallel');cmds.evaluator(name='deformer',enable=False)
            changing=[p for p in resolved[0]['values'] if len({c['values'][p] for c in resolved})>1]
            with pb._temporary_values(resolved[0]['values']):
                for i,case in enumerate(resolved+list(reversed(resolved))):
                    progress(stage='quality_pose',label=label,index=i)
                    for plug in changing:cmds.setAttr(plug,case['values'][plug])
                    cmds.refresh(force=True)
                    for n in names:
                        points=routing.points(n)
                        if variant=='direct':
                            baseline[(i,n)]=points
                            if n=='cabeza_high':
                                if not wrinkles:off_faces[i]=points
                                else:wrinkle_displacement=max(wrinkle_displacement,float(np.linalg.norm(points-off_faces[i],axis=1).max()))
                        else:errors[n]=max(errors[n],float(np.linalg.norm(points-baseline[(i,n)],axis=1).max()))
            row=dict(variant=variant,wrinkles=wrinkles,reference='direct',max_error=errors,
                     samples=len(resolved)*2*len(names),poses=20,modules=list(channels),
                     mode='Parallel CPU, explicit pose edits',accepted=max(errors.values())<=1e-4,
                     meaning='Expanded workload geometry gate, separate from clean GPU timings.')
            if variant=='direct' and wrinkles:
                row['wrinkles_actual_max_displacement']=wrinkle_displacement
                write('final_wrinkles_displacement.json',{'max_displacement':wrinkle_displacement,'poses':20,'workload':'F2 audit_cases; direct OFF versus ON, world points'})
            write(label+'.json',row);rows.append(row)
    return rows

def cache_quality(wrinkles=None):
    import numpy as np
    if wrinkles is None:wrinkles=bool(ARGS.get('wrinkles',False))
    names=routing.meshes();captures={};diagnostics={}
    order=(1,8,16,24,32,40,48,40,24,8,1)
    for cached in (False,True):
        with animated(wrinkles=wrinkles) as workload:
            configure('D' if cached else 'C')
            rb._play_once((1,48))
            if cached:cmds.cacheEvaluator(waitForCache=10.)
            progress(stage='cache_quality_playback',cached=cached)
            for index,frame in enumerate(order):
                cmds.currentTime(frame);cmds.refresh(force=True)
                captures[(cached,'play',index)]={n:routing.points(n) for n in names}
            # Edit both a facial and a body animation channel after warm fill.
            # Source curves are owned by this experiment and deleted on exit.
            for index,(plug,value) in enumerate((('C_jaw_CTL.rotateX',30),('L_shoulderFk_CTL.rotateZ',70))):
                cmds.setKeyframe(plug,time=24,value=value)
                cmds.currentTime(24);cmds.refresh(force=True)
                captures[(cached,'edit',index)]={n:routing.points(n) for n in names}
            diagnostics[str(cached)]=rb.diagnostics()
    errors={};maximum=0.
    for phase,count in (('play',len(order)),('edit',2)):
        per={n:0. for n in names}
        for index in range(count):
            for n in names:
                per[n]=max(per[n],float(np.linalg.norm(captures[(False,phase,index)][n]-captures[(True,phase,index)][n],axis=1).max()))
        errors[phase]=per;maximum=max(maximum,max(per.values()))
    row=dict(accepted=maximum<=1e-4,max_error=maximum,errors=errors,diagnostics=diagnostics,
             scope='Original con wrinkles '+('ON' if wrinkles else 'OFF')+', 11 saltos ida/vuelta y 2 ediciones de claves (mandíbula y hombro), 26 salidas de malla',
             tolerance=1e-4)
    write('final_cache_quality_w1.json' if wrinkles else 'final_cache_quality.json',row)
    return row

def weight_thresholds():
    import numpy as np
    from maya.api import OpenMaya as om, OpenMayaAnim as oma
    from maya_tools.scripts.tools import bifrost_wrinkles as bw
    routing.load('original')
    catalog=json.loads((FOLDER/'catalog.json').read_text());rows=[]
    with bw.primary_inputs_for_skin_export():
        for s in catalog['skins']:
            if not any('|cabeza_high|' in g['shape'] or '|cabeza_low|' in g['shape'] for g in s['geometry']):continue
            selection=om.MSelectionList();selection.add(s['name']);fn=oma.MFnSkinCluster(selection.getDependNode(0))
            paths=[om.MDagPath.getAPathTo(o) for o in fn.getOutputGeometry()]
            path=next(p for p in paths if p.node().hasFn(om.MFn.kMesh))
            comp,count=audit['component'](path);weights,ninf=fn.getWeights(path,comp)
            a=np.asarray(weights).reshape((count,ninf));absolute=np.abs(a);thresholds=[]
            for threshold in (0,1e-8,1e-6,1e-4,1e-3):
                per=np.count_nonzero(absolute>threshold,axis=1)
                thresholds.append(dict(threshold=threshold,nonzero=int(per.sum()),maximum_per_vertex=int(per.max()),mean_per_vertex=float(per.mean()),
                                       maximum_discarded_absolute_sum_per_vertex=float(np.where(absolute<=threshold,absolute,0).sum(axis=1).max())))
            rows.append(dict(skin=s['name'],thresholds=thresholds,minimum_nonzero_absolute_weight=float(absolute[absolute>0].min())))
    write('final_weight_thresholds.json',rows)
    return rows

def gpu_quality():
    import numpy as np
    results=[];direct={}
    for wrinkles in (False,True):
        for variant in ('original','direct','face_driver'):
            with animated(variant,wrinkles):
                cpu={};errors={n:0. for n in routing.meshes()};route_errors=dict(errors)
                for state in ('B','C'):
                    progress(stage='gpu_quality',variant=variant,wrinkles=wrinkles,state=state)
                    configure(state);rb._play_once((1,48))
                    for frame in (1,8,16,24,32,40,48):
                        cmds.currentTime(frame);cmds.refresh(force=True)
                        for n in errors:
                            pts=routing.points(n)
                            if state=='B':cpu[(frame,n)]=pts
                            else:errors[n]=max(errors[n],float(np.linalg.norm(pts-cpu[(frame,n)],axis=1).max()))
                            key=(wrinkles,state,frame,n)
                            if variant=='direct':direct[key]=pts
                            elif variant=='face_driver':route_errors[n]=max(route_errors[n],float(np.linalg.norm(pts-direct[key],axis=1).max()))
                maximum=max(max(errors.values()),max(route_errors.values()))
                row=dict(variant=variant,wrinkles=wrinkles,cpu_vs_gpu=errors,
                         face_driver_vs_direct=route_errors if variant=='face_driver' else None,
                         max_error=maximum,accepted=maximum<=1e-4,frames=[1,8,16,24,32,40,48],
                         samples_per_comparison=182,scope='Native animated F2 workload; Parallel CPU versus warmed GPU, all 26 display outputs. Geometry reads outside timing.',
                         diagnostics_after_reads=rb.diagnostics())
                write('final_gpu_quality_%s_w%d.json'%(variant,wrinkles),row);results.append(row)
    return results

def wrinkle_cache():
    rows=[]
    with animated(wrinkles=True) as workload:
        env=rb.environment('Edward')
        for label,state in (('C','C'),('D','D'),('C_bookend','C')):
            rows.append(timed('final_states_wrinkles1_'+label,env,workload,state=state)['timing'])
    return {'timing':rows,'quality':cache_quality(True)}

action=ARGS.get('action','profiles')
if action=='definitions':result={'definitions_loaded':True}
elif action=='components':result=components()
elif action=='profiles':result=profiles()
elif action=='routing_repeat':result=routing_repeat()
elif action=='states':result=states()
elif action=='display':result=display_tests()
elif action=='quality':result=quality_extended()
elif action=='cache_quality':result=cache_quality()
elif action=='weight_thresholds':result=weight_thresholds()
elif action=='gpu_quality':result=gpu_quality()
elif action=='post_checks':result={'gpu_quality':gpu_quality(),'wrinkle_cache':wrinkle_cache(),'weights':weight_thresholds()}
else:raise ValueError(action)
progress(complete=True, action=action)
