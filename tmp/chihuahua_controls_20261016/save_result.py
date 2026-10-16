import json
from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya_tools.scripts.utils import curve_tool

OUT=Path('C:/proyectos/auto-rig/tmp/chihuahua_controls_20261016')
ASSET=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/chihuahua')
base=json.loads((OUT/'baseline.json').read_text())
assert cmds.objExists('chihuahua')
assert 'chihuahua' in cmds.file(q=True,sn=True).lower()

def next_version(folder,prefix,suffix):
    i=1
    while (folder/('%s_v%03d%s'%(prefix,i,suffix))).exists():
        i+=1
    return folder/('%s_v%03d%s'%(prefix,i,suffix))

curves=next_version(ASSET/'curves','chihuahua','.curves')
scene=next_version(ASSET/'scenes','chihuahua_controls','.mb')
links=[]
for s in base['shapes']:
    for attr in ('worldSpace','local'):
        links.extend(cmds.listConnections(s+'.'+attr,s=False,d=True,p=True) or [])
assert not links, 'A controller curve drives scene data: '+repr(links)
curve_tool.get_all_ctl_curves_data(path=str(curves),root_filter='chihuahua')
payload=json.loads(curves.read_text())
assert len(payload)==290, 'Incomplete controller export'
assert all(v['transform']['overrideEnabled'] for v in payload.values())
assert {v['transform']['overrideColor'] for k,v in payload.items() if k.rsplit('|',1)[-1].startswith('L_')}=={6,18}
assert {v['transform']['overrideColor'] for k,v in payload.items() if k.rsplit('|',1)[-1].startswith('R_')}=={13,4}
cmds.file(rename=str(scene))
cmds.file(save=True,type='mayaBinary',force=True)
report=json.loads((OUT/'fit_report.json').read_text())
report.update(scene=str(scene),curves=str(curves),exported_controls=len(payload),
    scene_bytes=scene.stat().st_size,curves_bytes=curves.stat().st_size,
    drawing_only=True,saved=True)
(OUT/'delivery.json').write_text(json.dumps(report,indent=2))
result={k:v for k,v in report.items() if k!='changed'}
