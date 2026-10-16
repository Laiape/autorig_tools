import json
import sys
from pathlib import Path
from maya import cmds
from maya_tools.scripts.utils import basic_structure, rig_manager, data_manager
base = Path('C:/proyectos/auto-rig/tmp/flower_20261016')
result = {'scene': cmds.file(query=True, sceneName=True), 'modified': cmds.file(query=True, modified=True),
          'roots': cmds.ls(assemblies=True, long=True), 'runtime': rig_manager.__file__,
          'groups': {n: {'parent': cmds.listRelatives(n, parent=True, fullPath=True),
                         'children': cmds.listRelatives(n, children=True, fullPath=True)}
                     for n in ['flower', 'rig_GRP', 'modules_GRP', 'skel_GRP', 'skeletonHierarchy_GRP',
                               'C_stemSkinning_GRP', 'C_stemModule_GRP', 'C_leafModule_GRP', 'C_petalModule_GRP'] if cmds.objExists(n)},
          'env': cmds.ls('*_ENV', type='joint'), 'module_cache': data_manager.DataExportBiped().build_path,
          'settings_matrix': cmds.xform('C_settings_CTL', query=True, worldSpace=True, matrix=True)}
(base/'structure_before.json').write_text(json.dumps(result, indent=2))
