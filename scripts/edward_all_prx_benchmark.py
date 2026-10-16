"""Interleaved all-garment CPU DG edit latency, separate from viewport FPS."""
import json
import math
import os
from pathlib import Path
import time
import numpy as np
from maya import cmds
from tools import proximity_wrap as pw
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid']
manifest=json.loads((FOLDER/'manifest.json').read_text())
outputs={'PRX':[item['source'] for item in manifest['items'].values()],
         'BLENDSHAPE':[r['mesh'] for r in manifest['blendshape']['outputs'].values()],
         'SKIN':[r['mesh'] for r in manifest['skin'].values()]}
outputs={k:[pw.mesh_shape(m)+'.outMesh' for m in meshes] for k,meshes in outputs.items()}
axes=manifest['axes'];saved={p:cmds.getAttr(p) for p in axes}
switches={s+'_'+limb+'Settings_CTL.Ik_Fk':cmds.getAttr(s+'_'+limb+'Settings_CTL.Ik_Fk') for s in ('L','R') for limb in ('arm','leg')}
channels={'C_spine03_CTL.rotateX':15,'C_localChest_CTL.rotateY':20,'C_neck_CTL.rotateY':20,
          'L_shoulderFk_CTL.rotateZ':35,'R_shoulderFk_CTL.rotateY':25,'L_hipFk_CTL.rotateX':20,
          'R_hipFk_CTL.rotateZ':25,'L_ankleFk_CTL.rotateX':20,'R_ankleFk_CTL.rotateZ':25}
channels={p:v for p,v in channels.items() if p in axes}
passes=[]
try:
    cmds.evaluationManager(mode='off');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
    for p in axes:cmds.setAttr(p,0)
    for p in switches:cmds.setAttr(p,1)
    for repetition in range(3):
        for kind in (('PRX','BLENDSHAPE','PRX','SKIN','PRX') if repetition!=1 else ('PRX','SKIN','PRX','BLENDSHAPE','PRX')):
            samples=[]
            for index in range(-8,60):
                phase=index*2*math.pi/60
                start=time.perf_counter()
                for offset,(p,amplitude) in enumerate(channels.items()):cmds.setAttr(p,amplitude*math.sin(phase+offset*.3))
                cmds.dgeval(outputs[kind])
                elapsed=(time.perf_counter()-start)*1000
                if index>=0:samples.append(elapsed)
            passes.append({'variant':kind,'repetition':repetition,'samples_ms':samples,'median_ms':float(np.median(samples))})
            (FOLDER/'progress.json').write_text(json.dumps({'phase':'batch_DG_timing','variant':kind,'repetition':repetition}))
    summary={}
    for kind in outputs:
        selected=[p for p in passes if p['variant']==kind];values=[v for p in selected for v in p['samples_ms']]
        summary[kind]={'median_ms':float(np.median(values)),'p95_ms':float(np.percentile(values,95)),
                       'max_ms':float(max(values)),'samples':len(values),'pass_medians_ms':[p['median_ms'] for p in selected]}
    raw={'scope':'Standalone Maya 2026 DG CPU. Set nine body/limb control channels and force all 23 garment outputs. No viewport or full-rig FPS claim.',
         'channels':channels,'summary':summary,'passes':passes,'quality_gate_approved':False}
    (FOLDER/'batch_DG_timing.json').write_text(json.dumps(raw,indent=2));result={k:v for k,v in raw.items() if k!='passes'}
finally:
    for p,v in saved.items():cmds.setAttr(p,v)
    for p,v in switches.items():cmds.setAttr(p,v)
