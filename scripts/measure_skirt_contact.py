"""Bounded batch-demand timings; deliberately makes no viewport FPS claim."""
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import dress_keepout_chains as dress, rig_benchmark as bench

folder = ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
manifest = next(json.loads(p.read_text()) for p in sorted(folder.glob('final_delivery_v*.json'),reverse=True)
                if json.loads(p.read_text()).get('passed'))
version = Path(manifest['delivery']).stem.rsplit('_',1)[1]
target = folder/('batch_timings_'+version+'.json')
assert not target.exists()
report = {'passed':False,'measurement':'Owned batch Maya: currentTime or paired control edits plus dgeval of three worldMesh outputs; no viewport refresh, no FPS claim.',
          'repeats':3,'warmup':'One full 17-frame pass per mode; first eight timed frames discarded.',
          'prior_attempt':'The longer seven-reopen/49-frame trial was stopped after the candidate cohort had not completed in about five minutes. Its incomplete report is retained; no candidate timing is inferred from it.',
          'cohorts':[],'gpu_cache':'Not accepted or timed: interactive VP2 required for a comparable delivery claim.'}
meshes = ('c_tunic_GEO','c_embroider_GEO','c_body_GEO')
poses = [((0,0,0),(0,0,0)),((0,15,18),(0,0,0)),((0,0,0),(0,15,18)),
         ((-9,5,7),(2,0,0)),((14,4,0),(-14,4,0)),((0,9,12),(0,0,0)),((0,0,0),(0,0,0))]

def stats(samples):
    result = bench.statistics_ms(samples)
    result.pop('derived_fps')
    result['raw_ms'] = samples
    return result

try:
    # Interleave independent native reopens. Each receives the same curves,
    # sample count, CPU evaluator, units and demanded visible outputs.
    for label in ('baseline','candidate','baseline'):
        scene = manifest['source'] if label=='baseline' else manifest['delivery']
        start = time.perf_counter()
        cmds.file(scene,open=True,force=True)
        load_seconds = time.perf_counter()-start
        cmds.undoInfo(stateWithoutFlush=False)
        for evaluator in ('cache','deformer'):
            if evaluator in (cmds.evaluator(query=True) or []):
                cmds.evaluator(name=evaluator,enable=False)
        cmds.evaluationManager(mode='off')
        rest = {s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
        resolved = []
        for i,pose in enumerate(poses):
            values = {}
            for side,delta in zip(('L','R'),pose):
                ctl = side+'_ankleIk_CTL'
                cmds.xform(ctl,ws=True,t=[a+b for a,b in zip(rest[side],delta)])
                values.update({ctl+'.translate'+axis:cmds.getAttr(ctl+'.translate'+axis) for axis in 'XYZ'})
            resolved.append({'name':str(i),'values':values})
        for p,v in resolved[0]['values'].items():cmds.setAttr(p,v)
        outputs = [dress.mesh_path(m).fullPathName()+'.worldMesh[0]' for m in meshes]
        entry = {'label':label,'scene':scene,'scene_sha256':hashlib.sha256(Path(scene).read_bytes()).hexdigest(),
                 'native_load_seconds':load_seconds,'nodes':len(cmds.ls()),'states':{}}
        if 'environment' not in report:
            # The interactive benchmark's viewport inventory is deliberately
            # unavailable in standalone Maya; reuse its workload/statistics.
            report['environment'] = {'maya':cmds.about(version=True),'api':cmds.about(apiVersion=True),
                'units':cmds.currentUnit(q=True,linear=True),'time_unit':cmds.currentUnit(q=True,time=True),
                'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),
                'plugins':{n:cmds.pluginInfo(n,q=True,version=True) for n in cmds.pluginInfo(q=True,listPlugins=True) or []},
                'code_sha256':manifest['code_sha256'],'viewport':'unavailable in batch',
                'output_meshes':{m:{'shape':dress.mesh_path(m).fullPathName(),
                    'smooth_preview':cmds.getAttr(dress.mesh_path(m).fullPathName()+'.displaySmoothMesh')}
                    for m in meshes}}
        with bench.temporal_workload(resolved,(1,17)) as workload:
            entry['workload'] = workload
            cmds.currentTime(1)
            beginning = dress.mesh_points(meshes[0])
            cmds.currentTime(6)
            entry['motion_cm'] = max(math.dist(a,b) for a,b in zip(beginning,dress.mesh_points(meshes[0])))
            assert entry['motion_cm'] > .1
            for mode in ('off','parallel'):
                cmds.evaluationManager(mode=mode)
                for frame in range(1,18):
                    cmds.currentTime(frame);cmds.dgeval(outputs)
                print('SKIRT_TIMING_WARM='+json.dumps({'label':label,'mode':mode}),flush=True)
                passes = []
                for _ in range(3):
                    samples = []
                    for frame in range(1,18):
                        start = time.perf_counter()
                        cmds.currentTime(frame);cmds.dgeval(outputs)
                        elapsed = (time.perf_counter()-start)*1000
                        if frame>8:samples.append(elapsed)
                    passes.append(stats(samples))
                    print('SKIRT_TIMING_PASS='+json.dumps({'label':label,'mode':mode,'median_ms':passes[-1]['median_ms']}),flush=True)
                entry['states'][mode] = {'temporal':passes,'fallback':bool(cmds.evaluationManager(q=True,fallbackTriggered=True))}
        # Manual edits are separate from playback and use both leg controls.
        for mode in ('off','parallel'):
            cmds.evaluationManager(mode=mode)
            passes = []
            values = {side:cmds.getAttr(side+'_ankleIk_CTL.translateY') for side in ('L','R')}
            for repetition in range(4):
                samples = []
                for i in range(8):
                    start = time.perf_counter()
                    for side in ('L','R'):
                        cmds.setAttr(side+'_ankleIk_CTL.translateY',values[side]+(i%8)*.5)
                    cmds.dgeval(outputs)
                    samples.append((time.perf_counter()-start)*1000)
                if repetition:passes.append(stats(samples))
            entry['states'][mode]['control_edit'] = passes
        report['cohorts'].append(entry)
        target.write_text(json.dumps(report,indent=2),encoding='ascii')
        print('SKIRT_TIMING='+json.dumps({'label':label,'iteration':len(report['cohorts']),
            'states':{mode:{kind:statistics.median(p['median_ms'] for p in passes[kind]) for kind in ('temporal','control_edit')}
                      for mode,passes in entry['states'].items()}}),flush=True)
    report['summary'] = {}
    for mode in ('off','parallel'):
        for kind in ('temporal','control_edit'):
            rows = {}
            for label in ('baseline','candidate'):
                entries = [e for e in report['cohorts'] if e['label']==label]
                medians = [statistics.median(p['median_ms'] for p in e['states'][mode][kind]) for e in entries]
                all_samples = [v for e in entries for p in e['states'][mode][kind] for v in p['raw_ms']]
                rows[label] = {**stats(all_samples),'cohort_medians_ms':medians,
                    'reference_drift_percent':(max(medians)-min(medians))/statistics.median(medians)*100}
                rows[label].pop('raw_ms')
            rows['candidate_to_baseline_ratio'] = rows['candidate']['median_ms']/rows['baseline']['median_ms']
            report['summary'][mode+'_'+kind] = rows
    report['decision'] = 'Functional contact/lift addition; measured CPU cost only, no performance improvement claim. Viewport playback budget remains unverified.'
    report['passed'] = True
except BaseException:
    import traceback
    report['error'] = traceback.format_exc()
    raise
finally:
    target.write_text(json.dumps(report,indent=2),encoding='ascii')
