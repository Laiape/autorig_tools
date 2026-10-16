"""Version the four-expression preset and its build snapshot in the active clone."""
import copy, json
from pathlib import Path

ROOT=Path(r'C:/proyectos/auto-rig')
asset=ROOT/'autorig_tools/maya_tools/assets/Edward'
source=asset/'wrinkles/Edward_v003.wrinkles.json'
output=asset/'wrinkles/Edward_v004.wrinkles.json'
skin_source=asset/'skin_clusters/Edward_v069.skc'
skin_output=asset/'skin_clusters/Edward_v070.skc'
if output.exists() or skin_output.exists():
    raise RuntimeError('Use new asset versions.')
original=json.loads(source.read_text())
preset=copy.deepcopy(original)
setup=preset['setup']
for region in ('Eyes','Chin'):
    setup['patterns'][region]=[0.0]*setup['vertices']
    setup['settings'][region]=0.0
remaining=[]
for field in setup['controls']:
    for region in ('Eyes','Chin'):
        field['masks'].pop(region,None)
    if field['masks']:
        remaining.append(field)
setup['controls']=remaining
setup['preset']=output.as_posix()
approved=json.loads((ROOT/'maya_tools/assets/Edward/wrinkles/Edward_v002.wrinkles.json').read_text())['setup']
assert all(setup['patterns'][r]==approved['patterns'][r] for r in ('Forehead','Nose','Cheeks'))
assert setup['settings']==approved['settings']
assert setup['rest']==original['setup']['rest']
assert len(remaining)==19
with output.open('x',encoding='utf-8') as stream:
    json.dump(preset,stream,separators=(',',':'),allow_nan=False)
original_skin=json.loads(skin_source.read_text())
skin=copy.deepcopy(original_skin)
skin['__wrinkles__']=[setup]
with skin_output.open('x',encoding='utf-8') as stream:
    json.dump(skin,stream,separators=(',',':'),allow_nan=False)
written=json.loads(skin_output.read_text())
assert all(written[k]==original_skin[k] for k in original_skin if k!='__wrinkles__')
assert written['__wrinkles__'][0]==json.loads(output.read_text())['setup']
result={'preset':str(output),'build_snapshot':str(skin_output),'local_controls':19,
        'retained_patterns_match_approved_scene':True,'skin_correctives_and_other_metadata_unchanged':True}
(ROOT/'tmp/edward_wrinkles_20261015/import_assets.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
