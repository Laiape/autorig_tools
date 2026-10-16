"""Sample the saved demonstration, including interpolated and manual poses."""
import json
import os
import sys
from pathlib import Path

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import skirt_contact as skirt

folder = ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
manifest = next(json.loads(p.read_text()) for p in sorted(folder.glob('final_delivery_v*.json'),reverse=True)
                if json.loads(p.read_text()).get('passed'))
source = Path(manifest['delivery'])
demo = source.with_name(source.stem.replace('contact_','contact_demo_')+'.ma')
target = folder/('demo_validation_'+source.stem.rsplit('_',1)[1]+'.json')
assert not target.exists()
report = {'passed':False,'demo':str(demo),'samples':[]}
try:
    cmds.file(str(demo),open=True,force=True)
    for evaluator in ('cache','deformer'):
        if evaluator in (cmds.evaluator(query=True) or []):
            cmds.evaluator(name=evaluator,enable=False)
    cmds.evaluationManager(mode='parallel')
    for frame in (1,25,49,73,97,121,145,169,193,217,241,253,265,277,289):
        cmds.currentTime(frame)
        result = skirt.check_contact()
        row = {'frame':frame,'passed':result['passed'],'max_stretch_ratio':result['max_stretch_ratio'],
               'max_lift_cm_local':result['max_lift_cm_local'],
               'contacts':{m:{'inside':r['penetrating_vertices'],'uncertain':r['uncertain_vertices'],
                              'minimum_cm':r['minimum_signed_clearance_cm']} for m,r in result['contacts'].items()}}
        report['samples'].append(row)
        target.write_text(json.dumps(report,indent=2),encoding='ascii')
        print('SKIRT_DEMO_SAMPLE='+json.dumps(row),flush=True)
    assert all(row['passed'] for row in report['samples'])
    report['passed'] = True
except BaseException:
    import traceback
    report['error'] = traceback.format_exc()
    raise
finally:
    target.write_text(json.dumps(report,indent=2),encoding='ascii')
