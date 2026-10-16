"""Read-only identity check for the artist Maya session."""
import os
import sys
from maya import cmds
result = {
    'pid': os.getpid(), 'scene': cmds.file(q=True, sceneName=True),
    'modified': cmds.file(q=True, modified=True),
    'modules': {name: getattr(module, '__file__', None) for name, module in list(sys.modules.items())
                if name.endswith(('basic_structure', 'create_rig', 'model_cache', 'rig_manager'))},
    'roots': cmds.ls(assemblies=True),
    'panels': cmds.getPanel(type='modelPanel'),
    'api': cmds.about(apiVersion=True),
}
