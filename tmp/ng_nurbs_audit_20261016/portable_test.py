"""Validate installer without any AutoRig import path."""
import json,os,runpy,sys,traceback
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
sys.path[:]=[p for p in sys.path if 'auto-rig' not in p.lower()]
sys.path.insert(0,'C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts')
result={}
try:
 installer=runpy.run_path('C:/proyectos/auto-rig/autorig_tools/dist/install_ng_nurbs_bridge.py')
 destination=Path(__file__).with_name('portable_maya')
 first=installer['install'](open_window=False,maya_directory=str(destination))
 second=installer['install'](open_window=False,maya_directory=str(destination))
 import ng_nurbs_bridge
 result['package']=ng_nurbs_bridge.__file__
 result['no_autorig_imports']=not any(n=='maya_tools' or n.startswith('maya_tools.') for n in sys.modules)
 result['source_path_removed']=not any('auto-rig' in p.lower() for p in sys.path if 'portable_maya' not in p)
 result['repeat_install']=first==second
 cmds.loadPlugin('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/plug-ins/2026/ngSkinTools2.mll')
 from ng_nurbs_bridge import core,brush
 surface=cmds.nurbsPlane(patchesU=2,patchesV=3,ch=False)[0]
 js=[cmds.createNode('joint') for _ in range(2)]
 skin=cmds.skinCluster(js,surface,tsb=True)[0]
 from ng_nurbs_bridge import topology
 for row in core.membership(topology.surface_shape(surface),skin):
  cmds.setAttr(skin+'.weightList[%s].weights[0]'%row,.5)
  cmds.setAttr(skin+'.weightList[%s].weights[1]'%row,.5)
 cmds.undoInfo(state=True)
 b=core.create(surface)
 result['before_values']=core.sparse_weights(skin)['0']
 brush.Controller(b,b.layers().list()[0].id,0,intensity=1,value=.25).flood()
 result['after_values']=core.sparse_weights(skin)['0']
 result['connected_leaf']=cmds.getAttr(skin+'.weightList[0].weights[0]')
 b.detach()
 result['baked_values']=core.sparse_weights(skin)['0']
 result['baked_leaf']=cmds.getAttr(skin+'.weightList[0].weights[0]')
 result['independent_authoring']=abs(cmds.getAttr(skin+'.weightList[0].weights[0]')-.25)<1e-8
 installer['uninstall'](maya_directory=str(destination))
 result['startup_removed']=not (destination/'modules/ng_nurbs_bridge.mod').exists()
 result['runtime_retained_for_undo']=(destination/'ngNurbsBridge/scripts/ng_nurbs_bridge/core.py').is_file()
 assert all(result[k] for k in ['no_autorig_imports','source_path_removed','repeat_install','independent_authoring','startup_removed','runtime_retained_for_undo']),result
except Exception:result['traceback']=traceback.format_exc()
Path(__file__).with_name('portable_test.json').write_text(json.dumps(result,indent=2))
print(result,flush=True)
maya.standalone.uninitialize()
