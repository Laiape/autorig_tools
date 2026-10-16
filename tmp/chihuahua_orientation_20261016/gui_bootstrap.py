import sys,runpy,json,os
from pathlib import Path
sys.path[:0]=['C:/proyectos/auto-rig/autorig_tools','C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts']
import maya.cmds as cmds
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016')
cmds.commandPort(name='127.0.0.1:7102',sourceType='python',echoOutput=False)
(base/'ready.json').write_text(json.dumps({'pid':os.getpid(),'port':7102}))
runpy.run_path(str(base/'build_gui.py'),run_name='__main__')
