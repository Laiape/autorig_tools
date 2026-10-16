import hashlib, json, shutil
from pathlib import Path
root=Path('C:/proyectos/auto-rig/autorig_tools')
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016')
out=root/'maya_tools/docs/validation/chihuahua_shapes_20261016'
out.mkdir(parents=True,exist_ok=True)
for filename in ('adapted.json','validation.json','eye_regression.log'):
    shutil.copyfile(base/filename,out/filename)
paths=['maya_tools/assets/chihuahua/curves/chihuahua_v004.curves',
       'maya_tools/assets/chihuahua/curves/chihuahua_v005.curves',
       'maya_tools/assets/chihuahua/scenes/chihuahua_oriented_v002.mb',
       'maya_tools/scripts/utils/curve_tool.py',
       'maya_tools/scripts/biped/autorig/eyelid_module.py']
manifest={'maya':'2026','date':'2026-10-16','intent':'Rebase artist curve CVs from previous solver frames to authored guide frames, preserving controller and joint transforms and drawing visibility.',
          'reference_frames':'chihuahua_controls_v002.mb','source_curve_preset':'chihuahua_v004.curves',
          'checks':['290 curve controllers; 1197 unchanged joint/control matrices',
                    'Full CREATE RIG matches the adjusted CV positions exactly',
                    'Native save/reopen retains exact world CV positions and shape visibility',
                    'Three primary spine controls and two initially hidden tangents',
                    'Native head/eye deformation regression passes'],
          'files':{p:{'bytes':(root/p).stat().st_size,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest()} for p in paths}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(out)
