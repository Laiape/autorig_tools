import json,sys
from pathlib import Path
root=Path('C:/proyectos/auto-rig')
sys.path.insert(0,str(root/'autorig_tools'))
sys.path.insert(0,str(root/'scripts'))
import maya.standalone
maya.standalone.initialize(name='python')
import edward_rig_audit as audit
result=audit.storage()
(root/'tmp/edward_storage_worker_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
