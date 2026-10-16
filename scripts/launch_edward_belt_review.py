"""Launch the two Maya windows explicitly requested for artist validation."""
import json
import os
from pathlib import Path
import socket
import subprocess
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001'
manifest=json.loads((FOLDER/'manifest.json').read_text())
launched=[]
for index,label in enumerate(('BLENDSHAPE','SKIN')):
    record=manifest['artist_comparison_scenes'][label]
    settings_path=FOLDER/('artist_window_'+label+'_launch.json')
    assert not settings_path.exists(), 'Inspect an existing review window before launching again'
    port=7282+10*index
    with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    selected=record['variants'][0]
    settings={'root':str(ROOT),'folder':str(FOLDER),'scene':record['path'],'label':label,'index':index,'port':port,
              'meshes':list(manifest['variants'][selected]['meshes'].values())}
    environment=os.environ.copy()
    environment['MAYA_APP_DIR']=str(ROOT/('tmp/edward_belt_review_preferences_'+label))
    environment['MAYA_SKIP_USERSETUP_PY']='1'
    environment['EDWARD_BELT_REVIEW_SETTINGS']=str(settings_path)
    code='import maya.utils;maya.utils.executeDeferred(lambda:__import__("runpy").run_path(%r))'%str(ROOT/'scripts/edward_belt_review_bootstrap.py')
    log=(FOLDER/('artist_window_'+label+'_startup.log')).open('x')
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
    process=subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\maya.exe','-noAutoloadPlugins',
                              '-command','python('+json.dumps(code)+')'],env=environment,stdout=log,
                              stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,startupinfo=startup)
    settings['pid']=process.pid
    settings_path.write_text(json.dumps(settings,indent=2))
    launched.append(settings)
print(json.dumps(launched,indent=2))
