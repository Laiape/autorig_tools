import os,runpy,sys,json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
sys.path[:]=[p for p in sys.path if 'auto-rig' not in p.lower()]
sys.path.insert(0,'C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts')
installer=runpy.run_path('C:/proyectos/auto-rig/autorig_tools/dist/install_ng_nurbs_bridge.py')
result=installer['install'](False,str(Path(__file__).with_name('gui_portable_preferences')))
print(json.dumps(result),flush=True)
maya.standalone.uninitialize()
