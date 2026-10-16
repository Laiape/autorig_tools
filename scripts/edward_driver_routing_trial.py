"""Versioned routing experiments in the artist's interactive Maya, with snapshots.

Dispatch through maya_trial_client.py; TRIAL_ARGUMENTS selects one bounded action.
No production modules are changed by this experiment.
"""
import json
import hashlib
import time
from pathlib import Path
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_benchmark as rb, rig_validation as qa, pose_blendshapes as pb

FOLDER = Path(__file__).resolve().parents[1] / 'maya_tools/assets/Edward/experiments/driver_routing_20261015_v001'
INVENTORY = json.loads((FOLDER / 'inventory.json').read_text())
BODY='cuerpo_base_poseCorrectives_BLS.outputGeometry[0]'
FACE='cabeza_high_poseCorrectives_BLS.outputGeometry[0]'
FINAL='cabeza_high_Shape.inMesh'
WRINKLE='EdwardWrinkles_ToMaya.mayaMesh[0]'
VARIANTS=('original','direct','shared','shared_wrinkles','body_driver','face_driver')

def source(p): return cmds.connectionInfo(p,sourceFromDestination=True)
def connect(s,d):
    if source(d)!=s: cmds.connectAttr(s,d,force=True)
def disconnect(d):
    s=source(d)
    if s: cmds.disconnectAttr(s,d)
def mesh(name, upstream, parent='deformers_GRP'):
    t=cmds.createNode('transform',name=name,parent=parent)
    s=cmds.createNode('mesh',name=name+'Shape',parent=t)
    cmds.setAttr(t+'.visibility',0)
    connect(upstream,s+'.inMesh')
    return s
def load(variant):
    cmds.evaluator(name='cache',enable=False)
    cmds.evaluator(name='deformer',enable=False)
    cmds.evaluationManager(mode='off')
    name='baseline' if variant=='original' else variant
    cmds.file((FOLDER/('Edward_'+name+'.mb')).as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
    cmds.evaluator(name='cache',enable=False)

def setup(variant):
    load('original')
    if variant=='original': return
    # Move the existing corrective output into the display chain before sharing it.
    # The original display -> corrective -> driver link would otherwise be cyclic.
    connect('C_body_SKC_COPY_COPY.outputGeometry[0]','cuerpo_base_poseCorrectives_BLS.input[0].inputGeometry')
    connect(BODY,'cuerpo_base_Shape.inMesh')
    if variant in ('direct','face_driver'):
        disconnect('polySurfaceShape1.inMesh')
        connect('cuerpo_base_Shape.worldMesh[0]','cinturon3_PRX.drivers[0].driverGeometry')
    else:
        for node,data in INVENTORY['prx'].items():
            for index,driver in data['drivers'].items():
                if driver['driverBindGeometry']=='cuerpo_base_ShapeOrig.outMesh':
                    connect('polySurfaceShape1.worldMesh[0]',node+'.drivers['+index+'].driverGeometry')
    if variant in ('shared','shared_wrinkles','face_driver'):
        fs=mesh('cabeza_high_poseCorrectives_BLS_driver',FACE)
        connect(fs+'.outMesh','EdwardWrinklesGraphShape.AnimatedFace')
        # Preserve the existing world-space conversion, ownership and metadata.
        connect(fs+'.outMesh','EdwardWrinkles_PrimaryWorld.inputGeometry')
        if variant=='shared_wrinkles':
            ws=mesh('cabeza_high_wrinkles_driver',WRINKLE)
            connect(ws+'.outMesh',FINAL)
    # Make the permanent OFF route use the facial driver for shared variants.
    # Explicit benchmark switches below do not invoke the existing detail-mode router.
    cmds.currentTime(INVENTORY['frame'])
    cmds.file(rename=(FOLDER/('Edward_'+variant+'.mb')).as_posix())
    cmds.file(save=True,type='mayaBinary',force=True)

def wrinkle(enabled,variant):
    if enabled:
        s='cabeza_high_wrinkles_driverShape.outMesh' if variant=='shared_wrinkles' else WRINKLE
    else:
        s='cabeza_high_poseCorrectives_BLS_driverShape.outMesh' if variant in ('shared','shared_wrinkles','face_driver') else FACE
    connect(s,FINAL)

def definitions():
    result=list(qa.COMBINATION_POSES)
    result += [
        ('torso_bend',{'C_spine03_CTL.rotateZ':20,'C_localChest_CTL.rotateY':15}),
        ('neck_turn',{'C_neck_CTL.rotateY':30,'C_head_CTL.rotateZ':12}),
        ('asymmetric_face',{'C_jaw_CTL.rotateX':22,'L_lipCorner_CTL.translateX':4,'R_lipCorner_CTL.translateY':-3}),
        ('frown_wrinkle',{'L_eyebrowIn_CTL.translateY':-2,'R_eyebrowIn_CTL.translateY':-2,'C_eyebrowMid_CTL.wrinkleValue':1}),
        ('neutral_end',{})]
    return result

def meshes():
    result=['cuerpo_base','cabeza_high','cabeza_low']
    for data in INVENTORY['prx'].values():
        for shape in data['geometry']:
            result += cmds.listRelatives(shape,parent=True,fullPath=True) or []
    return list(dict.fromkeys(result))

def points(n):
    sel=om.MSelectionList();sel.add(n);path=sel.getDagPath(0)
    if path.apiType()!=om.MFn.kMesh:path.extendToShape()
    return np.asarray(om.MFnMesh(path).getPoints(om.MSpace.kWorld))[:,:3].copy()

def plug_points(n):
    sel=om.MSelectionList();sel.add(n)
    return np.asarray(om.MFnMesh(sel.getPlug(0).asMObject()).getPoints())[:,:3].copy()

def inspect_body():
    load('original')
    resolved,missing,_=qa.resolve_cases('Edward',definitions())
    if missing:raise RuntimeError(missing)
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']};rows=[]
    with rb.evaluation_session(),pb._temporary_values(initial):
        cmds.evaluationManager(mode='off')
        for case in resolved:
            for p,v in case['values'].items():cmds.setAttr(p,v)
            b=points('cuerpo_base');d=points('cuerpo_base_poseCorrectives_BLS_driver')
            raw=plug_points('C_body_SKC_COPY_COPY.outputGeometry[0]')
            rows.append({'pose':case['name'],'body_vs_corrective_driver_max':float(np.linalg.norm(b-d,axis=1).max()),'body_vs_skin_output_max':float(np.linalg.norm(b-raw,axis=1).max()),'weights':cmds.getAttr('cuerpo_base_poseCorrectives_BLS.weight'),'weight_connections':cmds.listConnections('cuerpo_base_poseCorrectives_BLS.weight',s=True,d=False,p=True)})
    report={'poses':rows,'body_pnts_indices':cmds.getAttr('cuerpo_base_Shape.pnts',multiIndices=True),'driver_pnts_indices':cmds.getAttr('polySurfaceShape1.pnts',multiIndices=True)}
    (FOLDER/'body_stage_audit.json').write_text(json.dumps(report,indent=2))
    return {'max_body_to_driver':max(r['body_vs_corrective_driver_max'] for r in rows),'max_body_to_skin':max(r['body_vs_skin_output_max'] for r in rows),'weights':rows[0]['weights'],'weight_connections':rows[0]['weight_connections']}

def quality(variant,enabled):
    load(variant);wrinkle(enabled,variant)
    resolved,missing,skipped=qa.resolve_cases('Edward',definitions())
    if missing: raise RuntimeError('Missing controls: '+str(missing))
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']}
    names=meshes(); values={}; rows=[]
    with rb.evaluation_session(),pb._temporary_values(initial):
        for mode in ('off','serial','parallel'):
            cmds.evaluationManager(mode=mode)
            for i,case in enumerate(resolved+list(reversed(resolved))):
                if mode!='parallel' and i%5:continue
                (FOLDER/'quality_progress.json').write_text(json.dumps({'variant':variant,'wrinkles':enabled,'mode':mode,'pose_index':i,'pose':case['name']}))
                for p,v in case['values'].items():cmds.setAttr(p,v)
                cmds.refresh(force=True)
                for j,n in enumerate(names):values['%s_%d_%d'%(mode,i,j)]=points(n)
                rows.append({'mode':mode,'index':i,'pose':case['name']})
    prefix='%s_wrinkles%d'%(variant,enabled)
    np.savez_compressed(FOLDER/(prefix+'_quality.npz'),**values)
    metadata={'variant':variant,'wrinkles':enabled,'meshes':names,'rows':rows,'missing':missing,'skipped':skipped,'tolerance_scene_units':1e-4}
    if variant!='original':
        reference='original' if variant=='direct' else 'direct'
        baseline=np.load(FOLDER/('%s_wrinkles%d_quality.npz'%(reference,enabled)))
        errors={n:0. for n in names}; worst={}
        for key,v in values.items():
            delta=float(np.linalg.norm(v-baseline[key],axis=1).max())
            n=names[int(key.rsplit('_',1)[1])]
            if delta>errors[n]:errors[n]=delta;worst[n]=key
        metadata.update(reference_variant=reference,max_error=errors,worst_samples=worst,accepted=max(errors.values())<=1e-4)
    (FOLDER/(prefix+'_quality.json')).write_text(json.dumps(metadata,indent=2))
    return {k:v for k,v in metadata.items() if k not in ('rows','meshes')}

def bench(variant,enabled,state,label):
    load(variant);wrinkle(enabled,variant)
    outfile=FOLDER/('%s_wrinkles%d_%s_%s.performance.json'%(variant,enabled,state,label))
    report=rb.run_state('Edward',outfile,state=state,cases=definitions(),frames=(1,48),repeats=3,allow_unsaved=True)
    # Control latency is a separate workload; no extraction, diagnostics or profiler inside timing.
    resolved,missing,_=qa.resolve_cases('Edward',definitions())
    if missing:raise RuntimeError(missing)
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']}
    runs=[]
    with rb.evaluation_session(),pb._temporary_values(initial):
        cmds.evaluationManager(mode=rb.STATES[state][0])
        cmds.evaluator(name='cache',enable=False)
        cmds.evaluator(name='deformer',enable=rb.STATES[state][1])
        for repeat in range(4 if state=='C' and variant in ('direct','shared','shared_wrinkles') and label=='r1' else 0):
            samples=[]
            for case in resolved+list(reversed(resolved)):
                start=time.perf_counter()
                for p,v in case['values'].items():cmds.setAttr(p,v)
                cmds.refresh(force=True)
                samples.append((time.perf_counter()-start)*1000)
            if repeat:runs.append(samples)
    report['control_interaction']={'cache_enabled':False,'workload':'Apply every resolved pose channel followed by forced refresh; includes multi-channel command overhead.','runs':[rb.statistics_ms(s) for s in runs],'timing':rb.statistics_ms([v for r in runs for v in r]) if runs else None}
    report['routing_variant']=variant;report['wrinkles_enabled']=enabled
    report['routing_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    outfile.write_text(json.dumps(report,indent=2))
    return {'report':str(outfile),'timing':report['timing'],'interaction':report['control_interaction']['timing'],'runs':report['runs']}

def cache_quality(variant,enabled):
    load(variant);wrinkle(enabled,variant)
    resolved,missing,_=qa.resolve_cases('Edward',definitions())
    if missing:raise RuntimeError(missing)
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']}
    captures={};names=meshes()
    for cached in (False,True):
        with rb.evaluation_session(),pb._temporary_values(initial),rb.temporal_workload(resolved,(1,48)):
            cmds.evaluationManager(mode='parallel');cmds.evaluator(name='cache',enable=False)
            cmds.evaluator(name='deformer',enable=False)
            cmds.currentTime(1);cmds.refresh(force=True)
            cmds.evaluator(name='deformer',enable=True)
            if cached:
                cmds.cacheEvaluator(cacheFillMode='syncAsync');cmds.evaluator(name='cache',enable=True)
            rb._play_once((1,48))
            if cached:cmds.cacheEvaluator(waitForCache=10.)
            for frame in (1,8,16,24,32,40,48,40,24,8,1):
                cmds.currentTime(frame);cmds.refresh(force=True)
                captures[(cached,frame)]={n:points(n) for n in names}
    errors={n:0. for n in names}
    for frame in (1,8,16,24,32,40,48):
        for n in names:
            errors[n]=max(errors[n],float(np.linalg.norm(captures[(False,frame)][n]-captures[(True,frame)][n],axis=1).max()))
    report={'variant':variant,'wrinkles':enabled,'frames':[1,8,16,24,32,40,48],'max_error':errors,'accepted':max(errors.values())<=1e-4,'scope':'Warm playback geometry only; control-edit invalidation is not certified.'}
    (FOLDER/('%s_w%d_cache_quality.json'%(variant,enabled))).write_text(json.dumps(report,indent=2))
    return report

args=globals().get('TRIAL_ARGUMENTS',{})
action=args.get('action')
if action=='prepare':
    for v in VARIANTS[1:]:setup(v)
    load('original')
    result={'variants':VARIANTS}
elif action=='prepare_variant':
    if (FOLDER/('Edward_'+args['variant']+'.mb')).exists():raise RuntimeError('Variant already exists')
    setup(args['variant']);result={'variant':args['variant']}
elif action=='quality':result=quality(args['variant'],bool(args['wrinkles']))
elif action=='inspect_body':result=inspect_body()
elif action=='benchmark':result=bench(args['variant'],bool(args['wrinkles']),args['state'],args.get('label','r1'))
elif action=='cache_quality':result=cache_quality(args['variant'],bool(args['wrinkles']))
elif action=='profile':
    load(args['variant']);wrinkle(bool(args['wrinkles']),args['variant'])
    cmds.profiler(reset=True);cmds.profiler(bufferSize=64)
    result=rb.capture_profile('Edward',FOLDER/('%s_w%d.mayaProfile'%(args['variant'],args['wrinkles'])),cases=definitions(),frames=(1,24),state='C')
elif action=='restore':
    load('original');cmds.currentTime(INVENTORY['frame']);cmds.select(INVENTORY['selection'],r=True)
    cmds.file(rename=INVENTORY['scene']);cmds.file(modified=INVENTORY['modified']);cmds.evaluationManager(mode='parallel')
    result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True)}
