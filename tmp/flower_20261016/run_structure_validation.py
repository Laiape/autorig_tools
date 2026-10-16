import json
from importlib import reload
from pathlib import Path
from maya_tools.scripts.tools.tests import test_flower_module
reload(test_flower_module)
result=test_flower_module.run('C:/proyectos/auto-rig/tmp/flower_20261016/structure_revision/validation')
base=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
(base/'validation/structure_rig_validation_20261016.json').write_text(json.dumps(result,indent=2))
