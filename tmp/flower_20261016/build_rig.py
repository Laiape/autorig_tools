import json
from pathlib import Path
from maya import cmds, mel
from maya_tools.scripts.utils import create_rig, curve_tool, guides_manager, data_manager

base = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
cmds.optionVar(sv=('currentAssetRigName', 'flower'))
result = create_rig.AutoRig().build()
data = data_manager.DataExportBiped().get_data('flower_module', 'controls')
if not data:
    raise RuntimeError('Flower modules were not built.')

def ring(ctl, radius, normal):
    if cmds.attributeQuery('autorigTemplateShape', node=ctl, exists=True):
        return
    old = cmds.listRelatives(ctl, shapes=True, fullPath=True) or []
    temp = cmds.circle(radius=radius, normal=normal, constructionHistory=False)[0]
    for shape in cmds.listRelatives(temp, shapes=True, fullPath=True):
        shape = cmds.parent(shape, ctl, shape=True, relative=True)[0]
        cmds.setAttr(shape+'.overrideEnabled', 1)
        cmds.setAttr(shape+'.overrideColor', 17)
        cmds.setAttr(shape+'.lineWidth', 2)
    cmds.delete(temp, *old)

ring('C_masterwalk_CTL', 5.4, (0, 1, 0))
ring('C_character_CTL', 6.2, (0, 1, 0))
ring('C_flowerHead_CTL', 2.8, (0, 1, 0))
# Move only the settings drawing; its locked transform stays neutral.
if not cmds.attributeQuery('autorigTemplateShape', node='C_settings_CTL', exists=True):
    cmds.move(9, 4, 0, 'C_settings_CTL.cv[*]', relative=True, objectSpace=True)

for name, members in [('flower_controls_SET', data+['C_masterwalk_CTL', 'C_settings_CTL']),
                      ('flower_petals_SET', data_manager.DataExportBiped().get_data('flower_module', 'petal_controls')),
                      ('flower_skinJoints_SET', data_manager.DataExportBiped().get_data('flower_module', 'skinning_joints'))]:
    cmds.sets(members, name=name)

guides_manager.load_guides_info(str(base/'guides/flower_v001.guides'), new_scene=False, load_settings=True)
cmds.setAttr('C_guides_GRP.visibility', lock=False)
cmds.setAttr('C_guides_GRP.visibility', 0)
cmds.setAttr('C_guides_GRP.visibility', lock=True)
cmds.select(clear=True)
curve_tool.get_all_ctl_curves_data(path=str(base/'curves/flower_v001.curves'), root_filter='flower')
from maya_tools.scripts.tools.skin_manager_api import SkinManager
SkinManager().export_skins(in_path=str(base/'skin_clusters/flower_v001.skc'))
mel.eval('setNamedPanelLayout "Single Perspective View";')
panel = 'modelPanel4'
cmds.modelEditor(panel, edit=True, displayAppearance='smoothShaded', displayTextures=False,
                 grid=False, joints=False, locators=False, cameras=False, rendererName='vp2Renderer')
cmds.setAttr('persp.translate', 48, 36, 72, type='double3')
cmds.viewPlace('persp', lookAt=(0.5, 17, 0.5))
cmds.setAttr('perspShape.focalLength', 55)
cmds.select('flower')
cmds.viewFit('persp', fitFactor=0.88)
cmds.select(clear=True)
cmds.currentTime(1)
cmds.playbackOptions(minTime=1, maxTime=120, animationStartTime=1, animationEndTime=120)
scene = base/'scenes/flower_rig_v001.mb'
cmds.file(rename=str(scene)); cmds.file(save=True, type='mayaBinary', force=True)
result.update(scene=str(scene), controls=len(data), skins=cmds.ls(type='skinCluster'))
(base/'validation/build_20261016.json').write_text(json.dumps(result, indent=2))
