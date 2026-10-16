"""Read-only provenance of the artist Maya session."""
import sys
from maya import cmds

result = {
    "maya_version": cmds.about(version=True),
    "api_version": cmds.about(apiVersion=True),
    "scene": cmds.file(query=True, sceneName=True),
    "modified": cmds.file(query=True, modified=True),
    "selection": cmds.ls(selection=True, long=True),
    "loaded_modules": {
        name: getattr(module, "__file__", None)
        for name, module in list(sys.modules.items())
        if name in (
            "maya_tools", "maya_tools.scripts.ui.skinning_tool_adapters",
            "maya_tools.scripts.ui.skinning_manager_UI", "ngSkinTools2",
            "ngSkinTools2.api.plugin", "ngSkinTools2.ui.mainwindow")
    },
    "self_module": cmds.moduleInfo(moduleName="self_module", path=True),
    "ng_loaded": cmds.pluginInfo("ngSkinTools2", query=True, loaded=True),
}
if result["ng_loaded"]:
    result["ng_plugin"] = cmds.pluginInfo("ngSkinTools2", query=True, path=True)
    result["ng_version"] = cmds.pluginInfo("ngSkinTools2", query=True, version=True)
    result["ng_commands"] = cmds.pluginInfo("ngSkinTools2", query=True, command=True)
    result["ng_nodes"] = cmds.pluginInfo("ngSkinTools2", query=True, dependNode=True)
