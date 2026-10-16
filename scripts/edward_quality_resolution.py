"""Resolve GPU/cached collar differences against a Parallel CPU reference.

One bounded hybrid candidate: keep collar2/3 PRX on CPU using Autodesk's native
gpuBlockPolicy, leaving the remainder eligible for GPU. No geometry algorithm,
weights, driver topology or corrective targets are removed.
"""
import json
from pathlib import Path
import runpy
import numpy as np
from maya import cmds

ROOT=Path(__file__).resolve().parents[1]
a=runpy.run_path(str(ROOT/'scripts/edward_final_audit.py'),init_globals={'TRIAL_ARGUMENTS':{'action':'definitions'}})
FOLDER=a['FOLDER'];rb=a['rb'];routing=a['routing'];rows=[]
order=(1,8,16,24,32,40,48,40,24,8,1)
policies={}
for wrinkles in (False,True):
    baseline={}
    for state,blocked in (('B',False),('D',False),('C',True),('D',True)):
        label='cpu_reference_w%d_%s_%s'%(wrinkles,state,'collars_cpu' if blocked else 'normal')
        with a['animated'](wrinkles=wrinkles) as workload:
            if blocked:
                cmds.select(['collar2_PRX','collar3_PRX'],r=True)
                cmds.deformerEvaluator(gpuBlockPolicy='on')
                policies[label]=rb._query(lambda:cmds.deformerEvaluator(q=True,gpuBlockPolicy=True))
            # Clean timing comes before any geometry read. The normal D time
            # already exists; B ON and the hybrid are new measured options.
            if blocked or (state=='B' and wrinkles):
                a['timed']('final_hybrid_'+label,rb.environment('Edward'),workload,state=state,
                           intervention={'collars_cpu':blocked,'wrinkles':wrinkles,'gpu_policy':policies.get(label)})
            a['configure'](state);rb._play_once((1,48))
            if state=='D':cmds.cacheEvaluator(waitForCache=10.)
            errors={'play':{n:0. for n in routing.meshes()},'edit':{n:0. for n in routing.meshes()}}
            def capture(phase,index):
                for n in errors[phase]:
                    points=routing.points(n);key=(phase,index,n)
                    if state=='B':baseline[key]=points
                    else:errors[phase][n]=max(errors[phase][n],float(np.linalg.norm(points-baseline[key],axis=1).max()))
            a['progress'](stage='cpu_reference_geometry',label=label)
            for index,frame in enumerate(order):
                cmds.currentTime(frame);cmds.refresh(force=True);capture('play',index)
            for index,(plug,value) in enumerate((('C_jaw_CTL.rotateX',30),('L_shoulderFk_CTL.rotateZ',70))):
                cmds.setKeyframe(plug,time=24,value=value);cmds.currentTime(24);cmds.refresh(force=True);capture('edit',index)
            maximum=max(max(v.values()) for v in errors.values())
            row=dict(label=label,state=state,blocked_collars=blocked,wrinkles=wrinkles,reference='Parallel CPU B',
                     errors=errors,max_error=maximum,accepted=maximum<=1e-4,
                     policy=policies.get(label),scope='11 frame jumps forward/reverse + jaw and shoulder key edits; 26 mesh outputs; native F2 workload.',
                     diagnostics=rb.diagnostics())
            a['write']('final_'+label+'.quality.json',row);rows.append(row)
    a['write']('final_cpu_reference_w%d.json'%wrinkles,{'wrinkles':wrinkles,'candidates':rows[-4:]})
a['write']('final_quality_resolution.json',{'candidates':rows,'reference':'Parallel CPU, native full deformation',
                                         'mechanism':'Select collar2_PRX and collar3_PRX; deformerEvaluator(gpuBlockPolicy="on") in versioned snapshots only.'})
result={'candidates':[{k:r[k] for k in ('label','max_error','accepted')} for r in rows]}
