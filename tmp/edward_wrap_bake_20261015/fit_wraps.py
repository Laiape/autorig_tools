import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
import json,sys,time
from pathlib import Path
import numpy as np
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_wrap_bake_20261015')
sys.path.insert(0,r'C:/proyectos/auto-rig/maya_tools/scripts')
from tools import proximity_bake as pb
pb.check_cancel=lambda:None
plan=json.loads((WORK/'wrap_sample_plan.json').read_text())
data=np.load(str(WORK/'wrap_samples.npz'))
nfit=len(plan['fit']);allworld=data['matrices'];globalj=plan['joints']
records=[];arrays={};t0=time.time()
for w,p in plan['targets'].items():
    idx=[globalj.index(j) for j in p['joints']]
    matrices=allworld[:,idx].transpose(1,0,2,3)
    sample=data[w]
    weights=pb.fit_weights(sample[:nfit],matrices[:,:nfit],min(8,len(idx)))
    h=np.column_stack((sample[0],np.ones(len(sample[0]))))
    rel=np.linalg.inv(matrices[:,0])[:,None]@matrices
    pred=np.einsum('vk,kfab,vb->fva',weights,rel.transpose(0,1,3,2)[:,:,:3,:],h,optimize=True)
    errors=np.linalg.norm(pred-sample,axis=2)
    rms=np.sqrt(np.mean(errors**2,axis=1))
    record={'wrap':w,'shape':p['shape'],'joints':p['joints'],'vertices':len(weights),'max_influences':int((weights>1e-8).sum(axis=1).max()),'fit_max_cm':float(errors[:nfit].max()),'held_out_max_cm':float(errors[nfit:].max()),'worst_rms_cm':float(rms.max()),'worst_max_cm':float(errors.max()),'accepted_offline':bool(errors.max()<=.1 and rms.max()<=.025),'worst_case':(plan['fit']+plan['held_out'])[int(np.unravel_index(np.argmax(errors),errors.shape)[0])]['name']}
    records.append(record);arrays[w]=weights
    (WORK/'fit_progress.json').write_text(json.dumps({'completed':len(records),'total':len(plan['targets']),'seconds':time.time()-t0,'last':record},indent=2))
    (WORK/'fit_results.json').write_text(json.dumps(records,indent=2))
    np.savez_compressed(str(WORK/'fit_weights.npz'),**arrays)
    print(w,record['worst_max_cm'],record['worst_rms_cm'],record['accepted_offline'],flush=True)
print('FIT_COMPLETE',round(time.time()-t0,1),flush=True)
