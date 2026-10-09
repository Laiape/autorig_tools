"""Open the bundled Edward picker from the AutoRig menu or shelf."""
import importlib.util
from pathlib import Path
import sys


def show():
    source = Path(__file__).resolve().parents[2]/"assets/Edward/picker/reference_workflow/edward_maya_picker.py"
    name = "edward_maya_picker"
    existing = sys.modules.get(name)
    if existing is not None and Path(existing.__file__).resolve() == source.resolve():
        return existing.show()
    spec = importlib.util.spec_from_file_location(name,str(source))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.show()
