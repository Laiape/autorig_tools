"""Re-export only refined module ownership in a disposable standalone process."""
import hashlib
import json
from pathlib import Path
import sys
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'autorig_tools'))
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
data=json.loads((FOLDER/'catalog.json').read_text());storage=json.loads((FOLDER/'storage.json').read_text())
cmds.file((FOLDER.parent/'driver_routing_20261015_v001/Edward_baseline.mb').as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
for name,module in data['modules'].items():
    names=module['exclusive_nodes'];cmds.select(names,replace=True,noExpand=True)
    path=FOLDER/'storage_payloads'/('module_'+name+'.mb')
    cmds.file(path.as_posix(),exportSelectedStrict=True,type='mayaBinary',force=True)
    row=next(r for r in storage['payloads'] if r['label']=='module_'+name)
    row.update(nodes=len(names),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
               attribution='Includes upstream SDK curves; stops at global time and foreign DAG/deformation boundaries.')
storage['module_attribution_refined']=True
(FOLDER/'storage.json').write_text(json.dumps(storage,indent=2),encoding='utf-8')
(ROOT/'tmp/edward_module_storage_refined_result.json').write_text(json.dumps({'success':True,'modules':18}))
print('MODULE_STORAGE_REFINED_COMPLETE',flush=True)
