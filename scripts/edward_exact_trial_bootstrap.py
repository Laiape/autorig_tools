"""Initialize only the owned trial session; never opens the artist's session."""
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
settings = json.loads((FOLDER / 'launch_settings.json').read_text())
sys.path[:0] = [str(ROOT / 'autorig_tools'), str(ROOT / 'autorig_tools/maya_tools/scripts'), str(ROOT / 'scripts')]
from maya import cmds, mel

try:
    for plugin in ('matrixNodes', 'quatNodes', 'lookdevKit', 'deformerEvaluator', 'bifrostGraph'):
        try:
            cmds.loadPlugin(plugin, quiet=True)
        except Exception as error:
            print('TRIAL_PLUGIN ' + plugin + ': ' + str(error), flush=True)
    cmds.evaluator(name='cache', enable=False)
    cmds.evaluator(name='deformer', enable=False)
    cmds.evaluationManager(mode='off')
    cmds.file((FOLDER / 'Edward_artist_baseline.mb').as_posix(), open=True, force=True,
              prompt=False, executeScriptNodes=False)
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.window('MayaWindow', edit=True, widthHeight=(1480, 950))
    cmds.modelEditor('modelPanel4', edit=True, displayAppearance='smoothShaded', displayTextures=False,
                     shadows=False, selectionHiliteDisplay=False, rendererName='vp2Renderer')
    cmds.evaluationManager(mode='parallel')
    cmds.commandPort(name='127.0.0.1:' + str(settings['port']), sourceType='python', echoOutput=False)
    from maya.api import OpenMayaUI as omui
    view = omui.M3dView.active3dView()
    ready = {'success': True, 'pid': os.getpid(), 'port': settings['port'],
             'scene': cmds.file(query=True, sceneName=True), 'nodes': len(cmds.ls()),
             'viewport': [view.portWidth(), view.portHeight()],
             'bifrost_loaded_from': __import__('maya_tools.scripts.tools.bifrost_wrinkles', fromlist=['']).__file__}
    (FOLDER / 'owned_maya_ready.json').write_text(json.dumps(ready, indent=2), encoding='utf-8')
except BaseException:
    (FOLDER / 'owned_maya_ready.json').write_text(json.dumps({'success': False, 'traceback': traceback.format_exc()}), encoding='utf-8')
    raise
