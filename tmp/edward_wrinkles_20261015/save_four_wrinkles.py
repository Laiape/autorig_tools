import json, os
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles as bw, wrinkle_presets as wp

ROOT=Path(r'C:/proyectos/auto-rig')
WORK=ROOT/'tmp/edward_wrinkles_20261015'
ASSET=ROOT/'maya_tools/assets/Edward'
scene=ASSET/'scenes/Edward_working_v005.mb'
preset=ASSET/'wrinkles/Edward_v002.wrinkles.json'
snapshot=ASSET/'skin_clusters/Edward_v071.skc'
assert os.getpid()==42096
assert json.loads((WORK/'validation_receipt.json').read_text())['success']
assert cmds.file(q=True,sn=True).endswith('/Edward_working_v004.mb')
if any(p.exists() for p in (scene,preset,snapshot)):
    raise RuntimeError('Choose unused asset versions.')
settings='EdwardWrinkles_Settings'
if not cmds.attributeQuery('wrinklePreset',node=settings,exists=True):
    cmds.addAttr(settings,longName='wrinklePreset',dataType='string')
cmds.setAttr(settings+'.wrinklePreset',preset.as_posix(),type='string')
wp.export_preset(settings,str(preset))
records=bw.export_setups()
(WORK/'final_setups.json').write_text(json.dumps(records),encoding='utf-8')
original=json.loads((ASSET/'skin_clusters/Edward_v070.skc').read_text())
updated=dict(original)
updated['__wrinkles__']=records
snapshot.write_text(json.dumps(updated,separators=(',',':'),allow_nan=False),encoding='utf-8')
reloaded=json.loads(snapshot.read_text())
assert set(reloaded)==set(original)
assert all(reloaded[k]==original[k] for k in original if k!='__wrinkles__')
cmds.file(rename=str(scene))
cmds.file(save=True,type='mayaBinary',force=False)
result={'scene':str(scene),'preset':str(preset),'skin_snapshot':str(snapshot),
 'skin_and_corrective_data_unchanged':True,'modified':cmds.file(q=True,modified=True)}
