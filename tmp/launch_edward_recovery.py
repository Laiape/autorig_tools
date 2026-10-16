from pathlib import Path
import json
import subprocess
root=Path(__file__).resolve().parents[1]
code="import maya.utils; maya.utils.executeDeferred(lambda: __import__('runpy').run_path(%r))" % str(root/'tmp/recover_edward_benchmark.py')
log=(root/'tmp/edward_recovery_start.log').open('w')
p=subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\maya.exe','-command','python('+json.dumps(code)+')'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
print(p.pid)
