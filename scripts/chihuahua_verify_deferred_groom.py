"""Check a staged model against visible and hidden native authoring states."""
import ast
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'autorig_tools'
sys.path[:0]=[str(RUNTIME),str(RUNTIME/'maya_tools/scripts')]
FOLDER=ROOT/'tmp/chihuahua_deferred_groom_20261016_release'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import model_cache
tree=ast.parse((ROOT/'scripts/chihuahua_prepare_fast_preview.py').read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='signature')
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(__file__),'exec'),globals())
cmds.evaluationManager(mode='off')
source=RUNTIME/'maya_tools/assets/chihuahua/models/chihuahua_v001.ma'
cmds.file(str(model_cache._cache_record(source)['binary']),open=True,force=True,executeScriptNodes=False)
hidden=signature()
cmds.setAttr('xgen.visibility',True)
visible=signature()
target=source.with_name('chihuahua_v002.mb')
cmds.file(str(target),open=True,force=True,executeScriptNodes=False)
preview=signature()
reference=model_cache.show_groom('chihuahua')
restored=signature()
def differences(a,b):
    result=[]
    for category in a:
        if a[category]==b.get(category):continue
        if isinstance(a[category],dict):
            for name in sorted(set(a[category])|set(b.get(category,{}))):
                if a[category].get(name)!=b.get(category,{}).get(name):
                    av,bv=a[category].get(name),b.get(category,{}).get(name)
                    keys=[k for k in av if av[k]!=bv.get(k)] if isinstance(av,dict) and isinstance(bv,dict) else ['value']
                    result.append({'category':category,'node':name,'keys':keys})
        else:result.append({'category':category,'a':a[category],'b':b.get(category)})
    return result
report={'visible_differences':differences(visible,restored),
        'hidden_visible_differences':differences(hidden,visible),
        'body_preview_exact':preview['meshes']=={n:d for n,d in hidden['meshes'].items() if not n.startswith('|xgen|')},
        'reference':reference}
(FOLDER/'verify.json').write_text(json.dumps(report,indent=2))
(FOLDER/'snapshots.json').write_text(json.dumps({'hidden':hidden,'visible':visible,'preview':preview,'restored':restored}))
print(json.dumps(report),flush=True)
cmds.file(unloadReference=reference)
os._exit(0)
