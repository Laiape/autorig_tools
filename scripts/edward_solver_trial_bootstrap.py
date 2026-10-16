"""Initialize an owned Maya GUI for comparable VP2 measurements."""
import json
import os
from pathlib import Path
import sys
import traceback

settings = json.loads(Path(os.environ['EDWARD_SOLVER_SETTINGS']).read_text())
assert os.getpid() == settings['pid']
FOLDER = Path(settings['folder']); runtime = Path(settings['runtime'])
sys.path[:0] = [str(runtime), str(runtime / 'maya_tools/scripts'), str(Path(settings['root']) / 'scripts')]
from maya import cmds, mel
try:
    for plugin in ('matrixNodes', 'quatNodes', 'lookdevKit', 'deformerEvaluator', 'bifrostGraph'):
        try:
            cmds.loadPlugin(plugin, quiet=True)
        except Exception:
            pass
    cmds.evaluator(name='cache', enable=False); cmds.evaluator(name='deformer', enable=False)
    cmds.evaluationManager(mode='off')
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.window('MayaWindow', edit=True, widthHeight=(1480, 950))
    cmds.modelEditor('modelPanel4', edit=True, rendererName='vp2Renderer', displayAppearance='smoothShaded',
                     displayTextures=False, shadows=False, grid=False, selectionHiliteDisplay=False)
    cmds.commandPort(name='127.0.0.1:' + str(settings['port']), sourceType='python', echoOutput=False)
    result = {'success': True, 'pid': os.getpid(), 'port': settings['port']}
except BaseException:
    result = {'success': False, 'traceback': traceback.format_exc()}
(FOLDER / 'ready.json').write_text(json.dumps(result, indent=2))
