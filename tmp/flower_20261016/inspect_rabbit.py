from maya import cmds, mel
from pathlib import Path
from maya_tools.scripts.utils import rig_manager
result={'scene':cmds.file(query=True,sceneName=True),'modified':cmds.file(query=True,modified=True),
        'runtime':rig_manager.__file__,'selection':cmds.ls(selection=True,long=True),
        'modules':{n:cmds.moduleInfo(moduleName=n,path=True) for n in cmds.moduleInfo(listModules=True) if 'smooth' in n.lower() or 'rabbit' in n.lower()},
        'frame':cmds.currentTime(query=True)}
cmds.loadPlugin('brSmoothWeights',quiet=True)
result['plugin_path']=cmds.pluginInfo('brSmoothWeights',query=True,path=True)
result['commands']=cmds.pluginInfo('brSmoothWeights',query=True,command=True)
for command in result['commands']:
    try:
        result[command+'_help']=cmds.help(command)
    except Exception as error:
        result[command+'_help']=str(error)
