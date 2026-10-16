import json
import os
import sys
from pathlib import Path
root = Path('C:/proyectos/auto-rig/autorig_tools')
sys.path[:0] = [str(root), str(root/'maya_tools/scripts')]
os.environ['AUTORIG_BUILD_CACHE_DIR'] = 'C:/proyectos/auto-rig/tmp/flower_20261016/build_cache'
from maya import cmds
from maya_tools.scripts.tools import mcp_listener
mcp_listener.PORT = 9878
mcp_listener.start()
result = {'pid': os.getpid(), 'port': 9878, 'runtime': mcp_listener.__file__,
          'modules': {name: cmds.moduleInfo(moduleName=name, path=True)
                      for name in (cmds.moduleInfo(listModules=True) or []) if name == 'self_module'}}
Path('C:/proyectos/auto-rig/tmp/flower_20261016/gui_ready.json').write_text(json.dumps(result, indent=2))
