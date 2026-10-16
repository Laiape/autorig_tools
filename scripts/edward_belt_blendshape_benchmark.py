"""Interleaved, batch DG belt control-latency diagnostic; not viewport FPS."""
import json
import os
import math
from pathlib import Path
import time
import numpy as np
from maya import cmds
from tools import proximity_wrap as pw
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Use the owned trial process'
manifest=json.loads((FOLDER/'manifest.json').read_text())
options=globals().get('TRIAL_ARGUMENTS',{})
axes=manifest['axes'];saved={p:cmds.getAttr(p) for p in axes}
switches={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk') for s in ('L','R') for limb in ('arm','leg')}
outputs={'PRX_reference':list(manifest['joints'])}
outputs.update({k:list(v['meshes'].values()) for k,v in manifest['variants'].items()})
outputs={k:[pw.mesh_shape(mesh)+'.outMesh' for mesh in meshes] for k,meshes in outputs.items()}
channels=('C_spine03_CTL.rotateX','C_spine07_CTL.rotateZ','L_shoulderFk_CTL.rotateY')
workload=[(math.sin(i*2*math.pi/60)*20,math.sin(i*2*math.pi/60+.7)*25,math.sin(i*2*math.pi/60+.3)*35) for i in range(60)]
passes=[]
try:
    cmds.evaluationManager(mode='off');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
    for p in axes:cmds.setAttr(p,0)
    for p in switches:cmds.setAttr(p,1)
    kinds=list(manifest['variants'])
    for repetition in range(3):
        order=['PRX_reference']+kinds[repetition:]+kinds[:repetition]+['PRX_reference']
        for kind in order:
            times=[]
            for i,values in enumerate(workload[-8:]+workload):
                start=time.perf_counter()
                for p,v in zip(channels,values):cmds.setAttr(p,v)
                cmds.dgeval(outputs[kind])
                elapsed=(time.perf_counter()-start)*1000
                if i>=8:times.append(elapsed)
            passes.append({'variant':kind,'repetition':repetition,'samples_ms':times,
                           'median_ms':float(np.median(times)),'p95_ms':float(np.percentile(times,95))})
            (FOLDER/'progress.json').write_text(json.dumps({'phase':'batch_dg_timing','repetition':repetition,'variant':kind}))
    summary={}
    for kind in outputs:
        selected=[p for p in passes if p['variant']==kind]
        samples=[s for p in selected for s in p['samples_ms']]
        summary[kind]={'median_ms':float(np.median(samples)),'p95_ms':float(np.percentile(samples,95)),
                       'max_ms':float(max(samples)),'pass_medians_ms':[p['median_ms'] for p in selected],'samples':len(samples)}
    result={'scope':'Standalone Maya 2026 DG CPU: set three control channels and force only the two belt outMesh outputs. No viewport, frame playback, GPU or full-rig FPS claim.',
            'quality_gate_passed':False,'summary':summary,'passes':passes}
    (FOLDER/options.get('output','batch_dg_timing.json')).write_text(json.dumps(result,indent=2))
    result={k:v for k,v in result.items() if k!='passes'}
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
    for p,v in switches.items():cmds.setAttr(p,v)
