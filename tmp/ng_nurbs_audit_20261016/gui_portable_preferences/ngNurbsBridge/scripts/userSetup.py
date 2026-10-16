def _ng_nurbs_startup():
    try:
        from ng_nurbs_bridge import attach
        attach()
    except Exception as error:
        from maya import cmds
        cmds.warning('NURBS Skin: ' + str(error))
from maya import utils as _ng_nurbs_utils
_ng_nurbs_utils.executeDeferred(_ng_nurbs_startup)
