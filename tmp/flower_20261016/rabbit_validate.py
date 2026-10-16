import json
from pathlib import Path
from importlib import reload
from maya import cmds
from maya_tools.scripts.tools.tests import test_flower_module
reload(test_flower_module)
base=Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
report=test_flower_module.run('C:/proyectos/auto-rig/tmp/flower_20261016/rabbit_smooth/validation')
(base/'validation/rabbit_rebuild_validation_20261016.json').write_text(json.dumps(report,indent=2))
review=base/'scenes/flower_rabbit_review_v001.mb'
cmds.file(str(review),open=True,force=True,executeScriptNodes=False)
cmds.currentTime(1001)
cmds.select('C_flowerHead_CTL')
result={'passed':report['passed'],'rebuilds':len(report['rebuilds']),'scene':str(review),'curl':cmds.getAttr('C_flowerHead_CTL.petalCurl')}
