import hashlib, json, shutil
from pathlib import Path

root = Path('C:/proyectos/auto-rig')
runtime = root / 'autorig_tools'
trial = root / 'tmp/chihuahua_orientation_20261016'
paw = root / 'tmp/chihuahua_fetlock_flip_20261016'
output = runtime / 'maya_tools/docs/validation/chihuahua_guide_orientation_20261016'
output.mkdir(parents=True, exist_ok=True)
for source, name in ((trial/'validation.json', 'full_character.json'),
                     (trial/'reproducibility.json', 'reproducibility.json'),
                     (trial/'published.json', 'native_persistence.json'),
                     (paw/'validated_sweep.json', 'paw_sweep.json'),
                     (paw/'sweep_receipt.json', 'paw_before_fix.json'),
                     (trial/'horse_regression.log', 'horse_regression.log')):
    shutil.copyfile(source, output/name)

files = [runtime/'maya_tools/assets/chihuahua/guides/chihuahua_v012.guides',
         runtime/'maya_tools/assets/chihuahua/build/chihuahua_v001.build',
         runtime/'maya_tools/assets/chihuahua/scenes/chihuahua_oriented_v001.mb',
         root/'recovery/chihuahua_guides_orientation_before_20261016_v001.mb']
files += list((runtime/'maya_tools/scripts/quadruped/autorig').glob('*module*.py'))
files += [runtime/'maya_tools/scripts/utils'/name for name in
          ('guide_frames.py', 'guides_manager.py', 'rig_manager.py')]
files += [runtime/'maya_tools/scripts/biped/autorig'/name for name in
          ('eyelid_module.py', 'jaw_module_nurbs.py')]
manifest = {'date': '2026-10-16', 'maya': '2026', 'passed': True,
    'source': 'Artist authored guides and neutral model in native recovery snapshot',
    'candidate': 'chihuahua_oriented_v001.mb',
    'intentional_changes': ['Retain authored guide orientations including eyes, jaw and local hip',
                            'Three spine primary controls with two initially hidden tangents',
                            'Paw roll follows the foot instead of lower IK solver twist'],
    'scope': ['13 neutral meshes retain identical world positions',
              '152 directly mapped guide frames, 442 generated joint pose outputs',
              'All four legs IK/FK and PV edits, gaze/head, jaw, body/neck/tail, global scale',
              '4812 forward/reverse paw lift samples from 0 to 10 cm at 0.05 cm steps',
              'DG/Serial/Parallel, native save/reopen and two complete builds'],
    'limits': ['No body skin binding or geometry reshaping added',
               'Middle spine control nonuniform scale retains existing joint-output invariance',
               'No performance, GPU, or cache acceptance claim'],
    'files': {str(path.relative_to(root)).replace('\\','/'): {'bytes': path.stat().st_size,
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in files}}
(output/'manifest.json').write_text(json.dumps(manifest, indent=2))
print(output)
