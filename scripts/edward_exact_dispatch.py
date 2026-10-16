"""Dispatch a bounded action to the persistent worker in the owned Maya."""
import importlib
import edward_exact_worker
if globals().get('TRIAL_ARGUMENTS',{}).get('reload_module'):
    importlib.reload(edward_exact_worker)
result = edward_exact_worker.run(globals().get('TRIAL_ARGUMENTS',{}))
