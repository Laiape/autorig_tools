import json
from pathlib import Path
from importlib import reload
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma

base = Path('C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/flower')
work = Path('C:/proyectos/auto-rig/tmp/flower_20261016/structure_revision')
work.mkdir(exist_ok=True)
before_scene = json.loads(Path('C:/proyectos/auto-rig/tmp/flower_20261016/structure_backup.json').read_text())['backup']
cmds.file(before_scene, open=True, force=True, executeScriptNodes=False)
meshes = ['C_stem_GEO','C_flowerCore_GEO','C_leaves_GEO','C_petalsA_GEO','C_petalsB_GEO']
poses = {
    'neutral': {},
    'stem_head': {'C_stem01_CTL.rz':12.,'C_stem03_CTL.ry':-28.,'C_stem05_CTL.rz':23.,'C_flowerHead_CTL.rx':18.},
    'curl_leaves': {'C_flowerHead_CTL.petalCurl':36.,'C_flowerHead_CTL.petalSpread':-12.,'C_flowerHead_CTL.petalTwist':9.,
                    'C_leaf0100_CTL.curl':31.,'C_leaf0200_CTL.rz':-22.,'C_petalA0101_CTL.ry':20.},
    'combined_scaled': {'C_stem02_CTL.rz':18.,'C_stem04_CTL.ry':-24.,'C_flowerHead_CTL.rz':15.,
                        'C_masterwalk_CTL.tx':3.,'C_masterwalk_CTL.ty':2.,'C_masterwalk_CTL.tz':-4.,
                        'C_masterwalk_CTL.rx':23.,'C_masterwalk_CTL.ry':38.,'C_masterwalk_CTL.rz':-12.,
                        'C_masterwalk_CTL.globalScale':1.6,'C_flowerHead_CTL.petalCurl':23.,'C_leaf0200_CTL.curl':-25.}}
channels = set().union(*(p.keys() for p in poses.values()))

def pose(values):
    for channel in channels:
        cmds.setAttr(channel,1. if channel.endswith('globalScale') else 0.)
    for channel,value in values.items():
        cmds.setAttr(channel,value)

def geometry():
    output = {}
    for mesh in meshes:
        sl=om.MSelectionList();sl.add(mesh);path=sl.getDagPath(0);path.extendToShape();fn=om.MFnMesh(path)
        output[mesh] = {'points':np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)]),
                        'normals':np.array([[p.x,p.y,p.z] for p in fn.getFaceVertexNormals(om.MSpace.kWorld)])}
    return output

def skins():
    output={}
    for skin in cmds.ls(type='skinCluster'):
        sl=om.MSelectionList();sl.add(skin);fn=oma.MFnSkinCluster(sl.getDependNode(0))
        path=om.MDagPath.getAPathTo(fn.getOutputGeometry()[0])
        component=om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
        om.MFnSingleIndexedComponent(component).addElements(range(om.MFnMesh(path).numVertices))
        weights,count=fn.getWeights(path,component)
        names=[p.partialPathName() for p in fn.influenceObjects()]
        order=sorted(range(count),key=lambda i:names[i])
        output[skin]=(np.array(weights).reshape(-1,count)[:,order],{p.partialPathName():cmds.getAttr('%s.bindPreMatrix[%s]'%(skin,fn.indexForInfluenceObject(p))) for p in fn.influenceObjects()})
    return output

skin_reference=skins()
accepted={}
for name,values in poses.items():
    pose(values)
    accepted[name]=geometry()
pose({})
camera=cmds.xform('persp',query=True,worldSpace=True,matrix=True)
focal=cmds.getAttr('perspShape.focalLength')

from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.flower.autorig import common
reload(curve_tool); reload(common)
common.settings_drawing('C_settings_CTL',letter='F',force=True)
cmds.select(clear=True)
preset=base/'curves/flower_v002.curves'
curve_tool.get_all_ctl_curves_data(path=str(preset),root_filter='flower')

from maya_tools.scripts.flower.autorig import stem_module,head_module,leaf_module,petal_module,flower_module
for module in (common,stem_module,head_module,leaf_module,petal_module,flower_module):
    reload(module)
from maya_tools.scripts.utils import create_rig,guides_manager,data_manager,scene_evaluation
reload(create_rig)
cmds.optionVar(stringValue=('currentAssetRigName','flower'))
build_result=create_rig.AutoRig().build()
report={'reference':before_scene,'build':build_result,'poses':{},'skin':{}}
for name,values in poses.items():
    pose(values)
    current=geometry()
    report['poses'][name]={}
    for mesh in meshes:
        displacement=float(np.linalg.norm(current[mesh]['points']-accepted[name][mesh]['points'],axis=1).max())
        normal=float(np.linalg.norm(current[mesh]['normals']-accepted[name][mesh]['normals'],axis=1).max())
        report['poses'][name][mesh]={'max_vertex_error':displacement,'max_normal_error':normal}
        assert displacement <= 1e-4,(name,mesh,displacement)
        assert normal <= 1e-5,(name,mesh,normal)
pose({})
current_skin=skins()
for name,(weights,bind) in skin_reference.items():
    new_weights,new_bind=current_skin[name]
    assert np.array_equal(weights,new_weights),name+' weights'
    error=max(abs(a-b) for joint,values in bind.items() for a,b in zip(values,new_bind[joint]))
    assert error<1e-10,(name,error)
    report['skin'][name]={'weights_exact':True,'bind_matrix_max_error':error}

guides_manager.load_guides_info(str(base/'guides/flower_v001.guides'),new_scene=False,load_settings=True)
cmds.setAttr('C_guides_GRP.visibility',lock=False);cmds.setAttr('C_guides_GRP.visibility',0);cmds.setAttr('C_guides_GRP.visibility',lock=True)
for shape in cmds.ls(type='mesh',noIntermediate=True,long=True):
    cmds.setAttr(shape+'.displaySmoothMesh',2)
for name,members in [('flower_controls_SET',data_manager.DataExportBiped().get_data('flower_module','controls')+['C_masterwalk_CTL','C_settings_CTL']),
                     ('flower_petals_SET',data_manager.DataExportBiped().get_data('flower_module','petal_controls')),
                     ('flower_skinJoints_SET',data_manager.DataExportBiped().get_data('flower_module','skinning_joints'))]:
    cmds.sets(members,name=name)
cmds.xform('persp',worldSpace=True,matrix=camera);cmds.setAttr('perspShape.focalLength',focal)
cmds.modelEditor('modelPanel4',edit=True,displayAppearance='smoothShaded',displayTextures=False,grid=False,joints=False,locators=False,cameras=False)
cmds.select(clear=True)
curve_tool.get_all_ctl_curves_data(path=str(preset),root_filter='flower')
cmds.playbackOptions(minTime=1,maxTime=120,animationStartTime=1,animationEndTime=120)
cmds.currentTime(1);scene_evaluation.apply()
scene=base/'scenes/flower_rig_v002.mb'
cmds.file(rename=str(scene));cmds.file(save=True,type='mayaBinary',force=True)
report.update(scene=str(scene),env_joints=len(cmds.ls('*_ENV',type='joint')),module_groups=len(cmds.listRelatives('modules_GRP',children=True,type='transform') or []),passed=True)
(base/'validation/structure_equivalence_20261016.json').write_text(json.dumps(report,indent=2))
cmds.playblast(format='image',completeFilename=str(base/'validation/flower_structure_v002.png'),compression='png',
               widthHeight=(1100,1100),showOrnaments=False,viewer=False,frame=1,offScreen=True,forceOverwrite=True,percent=100)
result=report
