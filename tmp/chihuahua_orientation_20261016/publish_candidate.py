import json, runpy
from pathlib import Path
import maya.cmds as cmds

base = Path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016')
target = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua/scenes/chihuahua_oriented_v001.mb')
assert not target.exists(), str(target)
build = json.loads((base / 'build_result.json').read_text())
assert build['success']
cmds.file(build['candidate'], open=True, force=True, prompt=False, executeScriptNodes=False)
nodes = sorted(cmds.ls(type='joint') + cmds.ls('*_CTL', type='transform'))
before = {n: cmds.xform(n, query=True, worldSpace=True, matrix=True) for n in nodes}
cmds.evaluationManager(mode='off')
cmds.select(clear=True)
cmds.file(rename=str(target))
cmds.file(save=True, type='mayaBinary', force=True)
cmds.file(str(target), open=True, force=True, prompt=False, executeScriptNodes=False)
error = max(abs(a-b) for n in nodes for a,b in zip(before[n], cmds.xform(n, query=True, worldSpace=True, matrix=True)))
assert error < 1e-4, error
sweep = runpy.run_path('C:/proyectos/auto-rig/tmp/chihuahua_fetlock_flip_20261016/validate_sweep.py')['result']
cmds.file(modified=False)
result = {'passed': True, 'scene': str(target), 'bytes': target.stat().st_size, 'compared_nodes': len(nodes), 'native_reopen_max_matrix_error': error, 'persisted_paw_sweep': sweep}
(base / 'published.json').write_text(json.dumps(result, indent=2))
