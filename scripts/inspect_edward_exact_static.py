"""Inspect static dependencies in an isolated standalone process; no FPS claim."""
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'autorig_tools'),str(ROOT/'autorig_tools/maya_tools/scripts'),str(ROOT/'scripts')]
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
for plugin in ('matrixNodes','quatNodes','lookdevKit','deformerEvaluator','bifrostGraph'):
    cmds.loadPlugin(plugin,quiet=True)
import edward_exact_worker as worker
try:
    result=worker.static_opportunities()
    worker.write('static_inspection_receipt.json',{'success':True,'result':result})
    print(json.dumps(result),flush=True)
    # All evidence files are closed. Avoid the observed Bifrost/Arnold Python
    # finalization crash in this disposable, read-only inspection process.
    os._exit(0)
except BaseException:
    worker.write('static_inspection_receipt.json',{'success':False,'traceback':traceback.format_exc()})
    raise
