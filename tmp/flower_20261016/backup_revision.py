import json
from pathlib import Path
from maya import cmds
scene = cmds.file(query=True, sceneName=True)
if not cmds.objExists('flower') or 'flower' not in scene.lower():
    raise RuntimeError('The active scene is not the flower rig.')
folder = Path('C:/proyectos/auto-rig/recovery')
folder.mkdir(exist_ok=True)
index = 1
while (folder/('flower_structure_before_20261016_v%03d.mb' % index)).exists():
    index += 1
backup = folder/('flower_structure_before_20261016_v%03d.mb' % index)
controls = cmds.ls('*_CTL', type='transform')
nondefault = {}
for ctl in controls:
    for attr in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
        value = cmds.getAttr(ctl+'.'+attr)
        if abs(value-(1 if attr.startswith('s') else 0)) > 1e-9:
            nondefault[ctl+'.'+attr] = value
cmds.file(rename=str(backup)); cmds.file(save=True, force=True, type='mayaBinary')
cmds.file(rename=scene)
result = {'backup': str(backup), 'nondefault_trs': nondefault, 'anim_curves': cmds.ls(type='animCurve'),
          'cached_rig': __import__('maya_tools.scripts.utils.data_manager', fromlist=['DataExportBiped']).DataExportBiped().build_path}
Path('C:/proyectos/auto-rig/tmp/flower_20261016/structure_backup.json').write_text(json.dumps(result, indent=2))
