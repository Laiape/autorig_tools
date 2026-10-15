"""Run one standalone regression in an isolated process with explicit exit status."""
import os
from pathlib import Path
import runpy
import sys
import traceback
import ctypes

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(sys.argv[1]).resolve().parent))
import maya.standalone

# Bifrost worker teardown can crash Python finalization on this installation.
# Each regression owns this entire disposable process; OS exit releases it.
maya.standalone.uninitialize = lambda: None
status = 1
try:
    runpy.run_path(str(Path(sys.argv[1]).resolve()), run_name='__main__')
    status = 0
except BaseException:
    traceback.print_exc()
finally:
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel.TerminateProcess(kernel.GetCurrentProcess(), status)
    else:
        os._exit(status)
