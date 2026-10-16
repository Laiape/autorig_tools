import json
from pathlib import Path
from importlib import reload
from maya import cmds
from maya_tools.scripts.flower.autorig import common
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.framework import registry
base = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
scene = base/'scenes/flower_rig_v001.mb'
cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
config = json.loads((base/'rig_data/flower.json').read_text())
guides = json.loads((base/'guides/flower_v001.guides').read_text())['flower']
reload(common)
for entry in config['petals']+config['leaves']:
    ctl = entry['prefix']+'00_CTL'
    start, end = [guides[n]['joint_matrix'][12:15] for n in (entry['guides'][0], entry['guides'][-1])]
    length = sum((a-b)**2 for a,b in zip(start, end))**0.5
    common.raised_drawing(ctl, length, height=0.9 if entry.get('layer') == 'B' else 0.6)
    for shape in cmds.listRelatives(ctl, shapes=True):
        cmds.setAttr(shape+'.overrideColor', 18 if entry.get('layer') == 'A' else 20 if entry.get('layer') == 'B' else 18)
        cmds.setAttr(shape+'.lineWidth', 2.)
cmds.move(0, 0.5, 0, 'C_flowerHead_CTL.cv[*]', relative=True, objectSpace=True)
for shape in cmds.ls(type='mesh', noIntermediate=True, long=True):
    cmds.setAttr(shape+'.displaySmoothMesh', 2)
cmds.select(clear=True)
curve_tool.get_all_ctl_curves_data(path=str(base/'curves/flower_v001.curves'), root_filter='flower')
reload(registry)
from maya_tools.scripts.ui import auto_rig_UI
auto_rig_UI.create_custom_menu()
cmds.file(save=True, force=True, type='mayaBinary')
cmds.playblast(format='image', completeFilename=str(base/'validation/flower_neutral.png'),
                compression='png', widthHeight=(1100, 1100), showOrnaments=False,
                viewer=False, frame=1, offScreen=True, forceOverwrite=True, percent=100)
result = {'scene': str(scene), 'menu': cmds.menu('autorig_menu', exists=True)}
