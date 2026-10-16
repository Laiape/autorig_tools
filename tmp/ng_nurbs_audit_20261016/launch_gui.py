import json,os,subprocess,sys
from pathlib import Path
folder=Path(__file__).resolve().parent
env=os.environ.copy()
portable=len(sys.argv)>1
env['MAYA_APP_DIR']=str(folder/('gui_portable_preferences' if portable else 'gui_preferences'))
if len(sys.argv)>1 and sys.argv[1]=='restart':
 env.pop('MAYA_SKIP_USERSETUP_PY',None)
else:
 env['MAYA_SKIP_USERSETUP_PY']='1'
if portable:env['NG_NURBS_PORTABLE_RESTART']='1' if sys.argv[1]=='restart' else '0'
startup=subprocess.STARTUPINFO()
startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow=0
code='import maya.utils;maya.utils.executeDeferred(lambda:__import__("runpy").run_path(%r))'%str(folder/('gui_bootstrap_portable.py' if portable else 'gui_bootstrap.py'))
log=(folder/'gui_startup.log').open('w')
process=subprocess.Popen(['C:/Program Files/Autodesk/Maya2026/bin/maya.exe','-noAutoloadPlugins','-command','python('+json.dumps(code)+')'],env=env,stdout=log,stderr=subprocess.STDOUT,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
(folder/'gui_launch.json').write_text(json.dumps({'pid':process.pid}))
print(process.pid)
