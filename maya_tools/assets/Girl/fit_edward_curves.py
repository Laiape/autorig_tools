"""Fit Edward's controller drawings to Girl's authored guide proportions."""
import copy
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'maya_tools/assets'
OUT = ASSETS / 'Girl/curves/Girl_v002.curves'
REPORT = ASSETS / 'Girl/validation/edward_curves_v002.json'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

edward = read(ASSETS / 'Edward/guides/Edward_v013.guides')['Edward']
girl = read(ASSETS / 'Girl/guides/Girl_v007.guides')['Girl']

def point(data, name):
    return data[name]['joint_matrix'][12:15]

def distance(data, a, b):
    return math.dist(point(data, a), point(data, b))

def ratio(a, b):
    return distance(girl, a, b) / distance(edward, a, b)

scales = {
    'global': ratio('C_spine00_JNT', 'C_neck04_JNT'),
    'torso': ratio('L_shoulder_JNT', 'R_shoulder_JNT'),
    'hip': ratio('L_hip_JNT', 'R_hip_JNT'),
    'neck': ratio('C_neck00_JNT', 'C_neck04_JNT'),
    'head': ratio('L_ear00_JNT', 'R_ear00_JNT'),
    'arm': ratio('L_shoulder_JNT', 'L_wrist_JNT'),
    'leg': ratio('L_hip_JNT', 'L_ankle_JNT'),
    'foot': ratio('L_ankle_JNT', 'L_tip_JNT'),
    'eye': ratio('L_eye_JNT', 'L_eyeEnd_JNT'),
    'ear': ratio('L_ear00_JNT', 'L_ear02_JNT'),
    'mouth': 1.0,
}
def curve_width(data, name):
    xs = [p[0] for p in data[name]['curve_data']['cvs']]
    return max(xs) - min(xs)
scales['mouth'] = curve_width(girl, 'C_upperLipLinear_CRVShape') / curve_width(edward, 'C_upperLipLinear_CRVShape')
scales['brow'] = curve_width(girl, 'L_eyebrow_CRVShape') / curve_width(edward, 'L_eyebrow_CRVShape')
scales['eyelid'] = curve_width(girl, 'L_eyelidUpperLinear_CRVShape') / curve_width(edward, 'L_eyelidUpperLinear_CRVShape')

def family(name):
    s = name.lower()
    for digit in ('thumb', 'index', 'middle', 'ring', 'pinky'):
        if digit in s:
            return digit
    if any(t in s for t in ('ankle', 'ball', 'toe', 'heel', 'bank')): return 'foot'
    if any(t in s for t in ('leg', 'knee', 'hipfk')): return 'leg'
    if any(t in s for t in ('arm', 'shoulder', 'elbow', 'wrist', 'clavicle', 'fingers')): return 'arm'
    if any(t in s for t in ('lip', 'mouth', 'jaw', 'teeth', 'tongue')): return 'mouth'
    if 'ear' in s: return 'ear'
    if 'eyebrow' in s: return 'brow'
    if 'eyelid' in s or 'socket' in s: return 'eyelid'
    if 'eye' in s: return 'eye'
    if 'neck' in s: return 'neck'
    if 'head' in s or 'face' in s or 'cheek' in s or 'nose' in s: return 'head'
    if 'localhip' in s: return 'hip'
    if 'spine' in s or 'body' in s or 'chest' in s: return 'torso'
    return 'global'

for digit in ('thumb', 'index', 'middle', 'ring', 'pinky'):
    scales[digit] = ratio('L_' + digit + '00_JNT', 'L_' + digit + '02_JNT')

donor = read(ASSETS / 'Edward/curves/Edward_v002.curves')
original = read(ASSETS / 'Girl/curves/Girl_v001.curves')
result = {}
receipt = {}
for value in donor.values():
    row = copy.deepcopy(value)
    name = row['transform']['name']
    if name == 'C_settings_CTL':
        # Girl's own settings drawing avoids carrying Edward's E monogram.
        row = copy.deepcopy(next(v for v in original.values() if v['transform']['name'] == name))
        receipt[name] = {'source': 'Girl_v001.curves', 'scale': 1.0}
    else:
        region = family(name)
        factor = scales[region]
        for shape in row['shapes']:
            shape['curve']['cvs'] = [[x * factor for x in pt] for pt in shape['curve']['cvs']]
        receipt[name] = {'source': 'Edward_v002.curves', 'region': region, 'scale': factor}
    result['|' + name] = row

# Edward's long finger-root boxes need an explicit target length: their donor
# drawing extends well beyond the donor guide span, so a span ratio alone is
# insufficient. Fit the same box drawing to Girl's complete finger chain.
for name, row in [(v['transform']['name'],v) for v in result.values()]:
    digit = next((d for d in ('thumb','index','middle','ring','pinky') if d in name.lower()),None)
    if not digit: continue
    side=name[0]
    root=side+'_'+digit+'00_JNT'
    ends=[n for n in girl if n.startswith(side+'_'+digit) and 'End_JNT' in n]
    endpoint=max(ends,key=lambda n:distance(girl,root,n))
    length=distance(girl,root,endpoint)
    points=[p for sh in row['shapes'] for p in sh['curve']['cvs']]
    extents=[max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
    if name.endswith('00_CTL'):
        axis_scale=[length*1.05/extents[0],1.0,1.0]
        width=max(extents[1:])
        axis_scale[1]=axis_scale[2]=min(1.0,length*0.18/width)
    else:
        factor=min(1.0,length*0.15/max(extents))
        axis_scale=[factor]*3
    for sh in row['shapes']:
        sh['curve']['cvs']=[[p[i]*axis_scale[i] for i in range(3)] for p in sh['curve']['cvs']]
    receipt[name]['drawing_axis_fit']=axis_scale
    receipt[name]['target_finger_length']=length

# Girl has two more eyelid samples per arc and terminal finger controls.
# Reuse the nearest donor drawing while keeping Girl's generated transforms.
for side in ('L', 'R'):
    pairs = []
    for arc in ('upperEyelid', 'downEyelid'):
        pairs.extend((side+'_'+arc+'0'+str(i)+'_CTL', side+'_'+arc+'020_CTL') for i in (21,22))
    pairs.extend((side+'_'+digit+'03_CTL',side+'_'+digit+'02_CTL') for digit in ('middle','ring','pinky'))
    for name, source in pairs:
        row = copy.deepcopy(result['|'+source])
        row['transform']['name'] = name
        for shape in row['shapes']:
            shape['name'] = shape['name'].replace(source.removesuffix('_CTL'),name.removesuffix('_CTL'))
        result['|'+name] = row
        receipt[name] = dict(receipt[source], equivalent_donor_control=source)

OUT.write_text(json.dumps(result, indent=4) + '\n', encoding='utf-8')
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps({'donor': 'Edward/curves/Edward_v002.curves',
    'guide_sources': ['Edward_v013.guides', 'Girl_v007.guides'],
    'method': 'Uniform object-space CV scaling per anatomical guide-span; native rig supplies target transforms.',
    'scales': scales, 'controls': receipt}, indent=2) + '\n', encoding='utf-8')
print(json.dumps(scales, indent=2))
print('Wrote', len(result), 'control templates:', OUT)
