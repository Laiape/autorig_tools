import os
from maya import cmds
from maya_tools.scripts.tools import skin_manager_api
from maya_tools.scripts.utils import rig_manager
from maya_tools.scripts.framework import context
s=skin_manager_api.SkinManager()
active=context.service().snapshot()
result={'pid':os.getpid(),'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
 'skin_module':skin_manager_api.__file__,'asset_path':str(active.asset_path),'asset':active.asset,
 'skin_path':s.get_latest_version_path(),'wrinkle_folder':rig_manager.asset_path('Edward','wrinkles')}
