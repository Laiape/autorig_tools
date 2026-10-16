"""Create a separate animated demo and two native Maya software previews."""
import os,sys,json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import skirt_contact as skirt
from maya_tools.scripts.utils import scene_evaluation

folder=ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
reports=(sorted(folder.glob('final_delivery_v*.json'),reverse=True)+
         sorted(folder.glob('validation_v*.json'),reverse=True))
accepted=next((json.loads(p.read_text()) for p in reports if json.loads(p.read_text()).get('passed')),None)
if not accepted:raise RuntimeError('A fully validated delivery is required.')
source=Path(accepted['delivery'])
demo=source.with_name(source.stem.replace('contact_','contact_demo_')+'.ma')
render_only='--render-only' in sys.argv
camera_only='--camera-only' in sys.argv
if camera_only:render_only=True
if demo.exists() and not render_only:raise FileExistsError(str(demo))
cmds.file(str(demo if render_only else source),open=True,force=True)
data=skirt._data();info=skirt._info(data)
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
frames=[(1,((0,0,0),(0,0,0))), (49,((0,15,18),(0,0,0))),
        (97,((0,0,0),(0,15,18))), (145,((-9,5,7),(2,0,0))),
        (193,((14,4,0),(-14,4,0))), (241,((0,9,12),(0,0,0))),
        (289,((0,0,0),(0,0,0)))]
for frame,pose in frames:
    cmds.currentTime(frame)
    for side,delta in zip(('L','R'),pose):
        ctl=side+'_ankleIk_CTL'
        cmds.xform(ctl,ws=True,t=[a+b for a,b in zip(rest[side],delta)])
        cmds.setKeyframe(ctl,attribute=['translateX','translateY','translateZ'],time=frame)
for frame,value in ((1,0),(241,0),(253,2),(265,0),(289,0)):
    cmds.setKeyframe(info['controls']['Front'],attribute='translateZ',time=frame,value=value)
cmds.keyTangent([s+'_ankleIk_CTL' for s in ('L','R')]+[info['controls']['Front']],
                inTangentType='linear',outTangentType='linear')
cmds.playbackOptions(minTime=1,maxTime=289,animationStartTime=1,animationEndTime=289)
cmds.currentTime(1)
if cmds.objExists('SkirtReel_CAM'):
    camera='SkirtReel_CAM';shape=cmds.listRelatives(camera,shapes=True)[0]
else:
    camera,shape=cmds.camera(name='SkirtReel_CAM')
position=om.MVector(95,100,150);target=om.MVector(0,72,0)
back=(position-target).normal();right=(om.MVector(0,1,0)^back).normal();up=(back^right).normal()
cmds.xform(camera,ws=True,matrix=[right.x,right.y,right.z,0,up.x,up.y,up.z,0,
    back.x,back.y,back.z,0,position.x,position.y,position.z,1])
cmds.setAttr(shape+'.focalLength',65)
cmds.setAttr(shape+'.nearClipPlane',.1)
for camera_shape in cmds.ls(type='camera'):
    cmds.setAttr(camera_shape+'.renderable',camera_shape==shape)
cmds.setAttr('defaultResolution.width',960)
cmds.setAttr('defaultResolution.height',900)
cmds.setAttr('defaultResolution.deviceAspectRatio',960/900)
scene_evaluation.apply()
cmds.select(data['settings'])
if not render_only or camera_only:
    cmds.file(rename=str(demo));cmds.file(save=True,type='mayaAscii')
print('SKIRT_DEMO='+str(demo),flush=True)
if camera_only:raise SystemExit(0)

# Preview shading is confined to this disposable process, after saving the
# editable demo with its original materials. No source or delivery is changed.
def material(name,color):
    shader=cmds.shadingNode('lambert',asShader=True,name=name)
    cmds.setAttr(shader+'.color',*color,type='double3')
    sg=cmds.sets(renderable=True,noSurfaceShader=True,empty=True,name=name+'SG')
    cmds.connectAttr(shader+'.outColor',sg+'.surfaceShader')
    return sg

gray=material('SkirtPreviewBody',(0.45,.43,.4))
blue=material('SkirtPreviewFabric',(.08,.32,.42))
trim=material('SkirtPreviewTrim',(.65,.52,.25))
for transform in cmds.ls(type='transform'):
    shapes=cmds.listRelatives(transform,shapes=True,noIntermediate=True,type='mesh') or []
    if shapes:cmds.sets(transform,edit=True,forceElement=gray)
cmds.sets(data['mesh'],edit=True,forceElement=blue)
for g in data['garments'][1:]:cmds.sets(g['mesh'],edit=True,forceElement=trim)
light=cmds.directionalLight(name='SkirtPreviewKey',intensity=1.2)
cmds.setAttr(cmds.listRelatives(light,parent=True)[0]+'.rotate',-35,-35,0,type='double3')
cmds.ambientLight(name='SkirtPreviewFill',intensity=.5)
cmds.setAttr('defaultRenderGlobals.currentRenderer','mayaSoftware',type='string')
cmds.setAttr('defaultRenderGlobals.imageFormat',32)
cmds.setAttr('defaultResolution.width',960)
cmds.setAttr('defaultResolution.height',900)
cmds.setAttr('defaultResolution.deviceAspectRatio',960/900)
preview=folder/('preview_'+source.stem)
preview.mkdir(parents=True,exist_ok=True)
outputs=[]
for label,frame in (('neutral',1),('left_step',49)):
    cmds.currentTime(frame)
    for camera_shape in cmds.ls(type='camera'):
        cmds.setAttr(camera_shape+'.renderable',camera_shape==shape)
    cmds.setAttr('defaultRenderGlobals.imageFilePrefix',str(preview/label).replace('\\','/'),type='string')
    outputs.append(cmds.render(camera))
    if not Path(outputs[-1]).is_file():
        raise RuntimeError('Renderer did not write '+str(outputs[-1]))
    print('SKIRT_PREVIEW='+str(outputs[-1]),flush=True)
(preview/'manifest.json').write_text(json.dumps({'source':str(source),'demo':str(demo),'images':outputs},indent=2),encoding='ascii')
