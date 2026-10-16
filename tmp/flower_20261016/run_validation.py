from pathlib import Path
from maya_tools.scripts.tools.tests import test_flower_module
from importlib import reload
reload(test_flower_module)
result = test_flower_module.run('C:/proyectos/auto-rig/tmp/flower_20261016/validation')
folder = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower/validation')
(folder/'rig_validation_20261016.json').write_text(__import__('json').dumps(result, indent=2))
