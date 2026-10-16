import maya.cmds as cmds
from maya_tools.scripts.utils import rig_manager
asset=rig_manager.get_character_name_from_build()
if str(asset).lower()!='chihuahua' or not cmds.objExists('C_guides_GRP.spine_controllers'):
 raise RuntimeError('The open scene is not the Chihuahua guide setup: %s'%asset)
node='C_guides_GRP'
before={a:cmds.getAttr(node+'.'+a) if cmds.objExists(node+'.'+a) else None for a in ('spine_controllers','spine_tangents')}
selection=cmds.ls(sl=True,long=True) or []
cmds.undoInfo(openChunk=True,chunkName='Chihuahua Spine Settings')
try:
 if not cmds.objExists(node+'.spine_tangents'):
  cmds.addAttr(node,longName='spine_tangents',attributeType='enum',enumName='off:on',defaultValue=0,keyable=True)
 cmds.setAttr(node+'.spine_controllers',3)
 cmds.setAttr(node+'.spine_tangents',1)
finally:
 cmds.undoInfo(closeChunk=True)
result={'asset':asset,'before':before,'after':{a:cmds.getAttr(node+'.'+a) for a in ('spine_controllers','spine_tangents')},'selection_preserved':selection==(cmds.ls(sl=True,long=True) or []),'scene':cmds.file(q=True,sn=True),'scope':'Guide build settings only; current guides and geometry retained. Hidden tangents are created on CREATE RIG.'}
