from maya import cmds
from maya.api import OpenMaya as om
from pathlib import Path
cmds.undoInfo(openChunk=True,chunkName='Temporary calibrated tangent axes')
values={}
try:
    code=Path('C:/proyectos/auto-rig/tmp/trial_eyelid_angular.py').read_text()
    start=code.index('    for side in')
    end=code.index('    code=')
    exec(compile(__import__('textwrap').dedent(code[start:end]),'angular_setup','exec'))
    for side in ('L','R'):
        for ctl in cmds.ls(side+'_*eyelid*CTL')+cmds.ls(side+'_*Eyelid*CTL'):
            for channel in ('tx','ty','tz','rx','ry','rz'):
                plug=ctl+'.'+channel
                if cmds.getAttr(plug,settable=True):values[plug]=cmds.getAttr(plug);cmds.setAttr(plug,0)
        for attr in ('Upper_Blink','Lower_Blink'):
            plug=side+'_eyeDirect_CTL.'+attr;values[plug]=cmds.getAttr(plug);cmds.setAttr(plug,0)
    axes={};infos={}
    for mtp in cmds.ls('*Eyelid*_MTP',type='motionPath'):
        stem=mtp[:-4];aim=stem+'Skinning_AIM'
        info=cmds.createNode('pointOnCurveInfo')
        cmds.connectAttr(cmds.connectionInfo(mtp+'.geometryPath',sourceFromDestination=True),info+'.inputCurve')
        cmds.connectAttr(cmds.connectionInfo(mtp+'.uValue',sourceFromDestination=True),info+'.parameter')
        tangent=om.MVector(*cmds.getAttr(info+'.normalizedTangent')[0])
        orientation=om.MMatrix(cmds.getAttr(aim+'.outputMatrix'))
        axes[stem]=(tangent*orientation.inverse()).normal();infos[stem]=info
    for stem,axis in axes.items():
        side=stem.split('_')[0];upper='_upper' in stem
        index=int(stem.split('Eyelid0')[1]);other=side+('_downEyelid0%d'%(index+21) if upper else '_upperEyelid0%d'%(index-21))
        common=(axis+axes[other]).normal()
        blend=cmds.createNode('blendColors')
        cmds.setAttr(blend+'.color1',common.x,common.y,common.z)
        cmds.setAttr(blend+'.color2',axis.x,axis.y,axis.z)
        cmds.connectAttr(side+('_upperContactAmount_CLP.outputR' if upper else '_lowerContactAmount_CLP.outputR'),blend+'.blender')
        aim=stem+'Skinning_AIM';cmds.setAttr(aim+'.secondaryMode',2)
        cmds.connectAttr(blend+'.output',aim+'.secondaryInputAxis')
        cmds.connectAttr(infos[stem]+'.normalizedTangent',aim+'.secondaryTargetVector')
    for plug,value in values.items():cmds.setAttr(plug,value)
    code=Path('C:/proyectos/auto-rig/tmp/capture_eyelid_corners.py').read_text().replace('eyelid_shared_corners_20261016/visual','eyelid_shared_corners_20261016/tangent_axis_trial')
    exec(compile(code,'capture_tangent_axis','exec'),{})
finally:
    cmds.undoInfo(closeChunk=True);cmds.undo();cmds.refresh(force=True)
result={'restored':True}
