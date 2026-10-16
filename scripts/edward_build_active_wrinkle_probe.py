"""Private nonzero detail probes for saved baseline and integrated builds."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'tmp/edward_build_exact_integration_v002'
for mode in ('baseline','optimized'):
    target=FOLDER/(mode+'_active_probe_v004');target.mkdir(exist_ok=False)
    command=[r'C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe','-u',str(ROOT/'scripts/edward_build_exact_integration.py'),
             '--worker',mode,'--output',str(target),'--reopen-from',str(FOLDER/mode/'built.ma'),'--active-probe']
    with (target/'maya.log').open('wb') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
    data=json.loads((target/'result.json').read_text()) if (target/'result.json').exists() else {'success':False}
    print(json.dumps({'mode':mode,'success':data['success'],'settings':data.get('authored_wrinkle_settings'),'error':data.get('error')}),flush=True)
    assert result.returncode==0 and data['success']
print('ACTIVE_PROBES_COMPLETE',flush=True)
