import json
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import rig_benchmark as rb
result={'evaluators':cmds.evaluator(q=True,enable=True),'curve_manager_config':rb._query(lambda:cmds.evaluator(name='curveManager',q=True,configuration=True)),'values':{n:rb._query(lambda n=n:cmds.evaluator(name='curveManager',q=True,valueName=n)) for n in ('forceAnimatedNodes','forceAnimatedCurves','forcedAnimatedAttributeName','skipStaticEvaluation')},'viewport':{p:{'width':cmds.control(p,q=True,width=True),'height':cmds.control(p,q=True,height=True),'camera':cmds.modelEditor(p,q=True,camera=True),'renderer':cmds.modelEditor(p,q=True,rendererName=True),'appearance':cmds.modelEditor(p,q=True,displayAppearance=True),'textures':cmds.modelEditor(p,q=True,displayTextures=True)} for p in cmds.getPanel(type='modelPanel')}}
Path('C:/proyectos/auto-rig/tmp/edward_evaluator_probe.json').write_text(json.dumps(result,indent=2))
