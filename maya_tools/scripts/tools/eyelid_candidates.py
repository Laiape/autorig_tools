"""Explicit offline eyelid experiments. Never called by normal CREATE RIG.

deboor: compile curve-skin moments at rest/contact samples into matrix sums.
The interpolation of basis weights between those samples is approximate in
partial blinks. Keep the 1e-4 equivalence gate; reject rather than relax it.
aim: use a horizontal aim in normalized eye space and a latitude offset on
an authored affine ellipsoid. Preserve the existing spherical output away
from the poles, while clamping extreme Y edits to the actual eye surface.
"""
import math
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import de_boor_core


def _shape(curve):
    return cmds.listRelatives(curve, shapes=True, noIntermediate=True, fullPath=True)[0]


def _paths(prefix):
    return sorted(cmds.ls(prefix+'_*Eyelid*_MTP', type='motionPath'))


def aim(prefix, radii=None, eye_matrix=None):
    """Aim-based latitude surface position, old orientation and detail edits.

    radii are positive eye-local ellipsoid axes. eye_matrix is its world rest
    frame; defaults are resolved from the existing setup, never asset names.
    Arbitrary orientation, position, side and positive affine scales work in
    this frame. The final character/head deformation remains downstream.
    """
    paths = _paths(prefix)
    if not paths:
        raise ValueError('No eyelid paths: '+prefix)
    first = paths[0][:-4]
    if eye_matrix is None:
        eye_matrix = list(om.MMatrix(cmds.getAttr(first+'Local_MMX.matrixIn[1]')).inverse())
    if radii is None:
        radius = math.sqrt(cmds.getAttr(first+'Horizsq_SUB.input1'))
        radii = (radius, radius, radius)
    radii = tuple(float(r) for r in radii)
    if len(radii) != 3 or any(not math.isfinite(r) or r <= 0 for r in radii):
        raise ValueError('Positive finite XYZ globe radii are required')
    scale = om.MMatrix([radii[0],0,0,0,0,radii[1],0,0,0,0,radii[2],0,0,0,0,1])
    globe = scale*om.MMatrix(eye_matrix)
    for path in paths:
        stem = path[:-4]
        local = cmds.createNode('multMatrix', name=stem+'RadialLocal_MMX')
        cmds.connectAttr(stem+'Skinning_MMT.matrixSum', local+'.matrixIn[0]')
        cmds.setAttr(local+'.matrixIn[1]', list(globe.inverse()), type='matrix')
        row=cmds.createNode('rowFromMatrix',name=stem+'RadialLocal_ROW')
        cmds.setAttr(row+'.input',3)
        cmds.connectAttr(local+'.matrixSum',row+'.matrix')
        horizontal=cmds.createNode('composeMatrix',name=stem+'RadialHorizontal_CMX')
        cmds.connectAttr(row+'.outputX',horizontal+'.inputTranslateX')
        cmds.connectAttr(row+'.outputZ',horizontal+'.inputTranslateZ')
        direction = cmds.createNode('aimMatrix', name=stem+'Radial_AIM')
        cmds.connectAttr(horizontal+'.outputMatrix', direction+'.primaryTargetMatrix')
        cmds.setAttr(direction+'.primaryInputAxis',0,0,1)
        latitude=cmds.createNode('clamp',name=stem+'RadialLatitude_CLP')
        cmds.setAttr(latitude+'.minR',-1);cmds.setAttr(latitude+'.maxR',1)
        cmds.connectAttr(row+'.outputY',latitude+'.inputR')
        squared=cmds.createNode('multiply',name=stem+'RadialLatitudeSquared_MUL')
        cmds.connectAttr(latitude+'.outputR',squared+'.input[0]')
        cmds.connectAttr(latitude+'.outputR',squared+'.input[1]')
        remaining=cmds.createNode('subtract',name=stem+'RadialRemaining_SUB')
        cmds.setAttr(remaining+'.input1',1)
        cmds.connectAttr(squared+'.output',remaining+'.input2')
        root=cmds.createNode('power',name=stem+'RadialRadius_POW')
        cmds.connectAttr(remaining+'.output',root+'.input')
        cmds.setAttr(root+'.exponent',.5)
        offset=cmds.createNode('composeMatrix',name=stem+'RadialOffset_CMX')
        cmds.connectAttr(latitude+'.outputR',offset+'.inputTranslateY')
        cmds.connectAttr(root+'.output',offset+'.inputTranslateZ')
        world = cmds.createNode('multMatrix', name=stem+'RadialWorld_MMX')
        cmds.connectAttr(offset+'.outputMatrix',world+'.matrixIn[0]')
        cmds.connectAttr(direction+'.outputMatrix',world+'.matrixIn[1]')
        cmds.setAttr(world+'.matrixIn[2]',list(globe),type='matrix')
        position = cmds.createNode('pickMatrix',name=stem+'RadialPosition_PMX')
        cmds.connectAttr(world+'.matrixSum',position+'.inputMatrix')
        for component in ('Rotate','Scale','Shear'):
            cmds.setAttr(position+'.use'+component,0)
        rotation = cmds.createNode('pickMatrix',name=stem+'RadialRotation_PMX')
        cmds.connectAttr(stem+'Skinning_AIM.outputMatrix',rotation+'.inputMatrix')
        cmds.setAttr(rotation+'.useTranslate',0)
        output = cmds.createNode('multMatrix',name=stem+'RadialAttachment_MMX')
        cmds.connectAttr(rotation+'.outputMatrix',output+'.matrixIn[0]')
        cmds.connectAttr(position+'.outputMatrix',output+'.matrixIn[1]')
        cmds.connectAttr(output+'.matrixSum',stem+'ControlRotation_MMX.matrixIn[1]',force=True)
    return {'paths':len(paths),'radii':radii,'eye_matrix':eye_matrix,
            'intent':'Aim longitude plus preserved/clamped eye-local latitude on affine ellipsoid.'}


def deboor(prefix):
    """Compile spline/skin samples to direct native weighted matrix moments.

    No curve, skinCluster, blendShape or motionPath is demanded by the new
    attachment branch. Coefficients come from the literal 7-CV cubic basis,
    skin weights and bind matrices. Partial-blink moving-U interpolation is
    explicitly approximate; open/closed endpoints are exact in position.
    """
    data = {}
    for label, curve_label in (('upper','Up'),('lower','Down')):
        skin = prefix+'_'+label+'Eyelid_SKIN'
        source = prefix+'_eyelid'+curve_label+'_CRV'
        pose = prefix+'_eyelid'+curve_label+'Pose_CRV'
        selection = om.MSelectionList(); selection.add(_shape(source))
        fn = om.MFnNurbsCurve(selection.getDagPath(0))
        points = list(fn.cvPositions(om.MSpace.kObject))
        knots = list(fn.knots())
        knots = [knots[0]]+knots+[knots[-1]]
        degree = fn.degree
        influences = cmds.skinCluster(skin,q=True,influence=True)
        indices = cmds.getAttr(skin+'.matrix',multiIndices=True)
        bind = [om.MMatrix(cmds.getAttr(skin+'.bindPreMatrix[%d]'%i)) for i in indices]
        geometry = om.MMatrix(cmds.getAttr(skin+'.geomMatrix'))
        weights = [cmds.skinPercent(skin,pose+'.cv[%d]'%i,q=True,value=True) for i in range(len(points))]
        frame = cmds.createNode('multMatrix',name=prefix+'_'+label+'DeBoorFrame_MMX')
        cmds.connectAttr(prefix+'_'+label+'LidRoll_MMX.matrixSum',frame+'.matrixIn[0]')
        cmds.connectAttr(pose+'.worldMatrix[0]',frame+'.matrixIn[1]')
        data[label] = (points,knots,degree,influences,bind,geometry,weights,frame)
    samples = {}
    joint_frames = {}

    def evaluate(label,u):
        key = label,round(u,12)
        if key in samples:
            return samples[key]
        points,knots,degree,influences,bind,geometry,weights,frame = data[label]
        basis = de_boor_core.de_boor(len(points),degree,u,knots)
        name = prefix+'_'+label+'DeBoorSample%d'%len(samples)
        summed = cmds.createNode('plusMinusAverage',name=name+'_PMA')
        slot = 0
        for j,joint in enumerate(influences):
            coefficients = [basis[i]*weights[i][j] for i in range(len(points))]
            weight = sum(coefficients)
            if weight == 0:
                continue
            moment = om.MVector()
            for p,w in zip(points,coefficients):
                value = p*geometry*bind[j]
                moment += om.MVector(value.x,value.y,value.z)*w
            frame_key=label,joint
            if frame_key not in joint_frames:
                product=cmds.createNode('multMatrix',name=prefix+'_'+label+'DeBoorJoint%d_MMX'%j)
                cmds.connectAttr(joint+'.worldMatrix[0]',product+'.matrixIn[0]')
                cmds.setAttr(product+'.matrixIn[1]',list(geometry.inverse()),type='matrix')
                cmds.connectAttr(frame+'.matrixSum',product+'.matrixIn[2]')
                joint_frames[frame_key]=product+'.matrixSum'
            point=cmds.createNode('pointMatrixMult',name=name+'Influence%d_PMM'%j)
            cmds.setAttr(point+'.inPoint',moment.x/weight,moment.y/weight,moment.z/weight)
            cmds.connectAttr(joint_frames[frame_key],point+'.inMatrix')
            weighted=cmds.createNode('multiplyDivide',name=name+'Influence%d_MD'%j)
            for axis in 'XYZ':cmds.connectAttr(point+'.output'+axis,weighted+'.input1'+axis)
            cmds.setAttr(weighted+'.input2',weight,weight,weight)
            for axis,child in zip('XYZ','xyz'):
                cmds.connectAttr(weighted+'.output'+axis,summed+'.input3D[%d].input3D%s'%(slot,child))
            slot += 1
        samples[key] = summed+'.output3D'
        return samples[key]

    def blend(a,b,weight,name):
        node = cmds.createNode('blendColors',name=name)
        for source,target in ((a,'color2'),(b,'color1')):
            owner,attribute=source.split('.',1)
            children=cmds.attributeQuery(attribute,node=owner,listChildren=True)
            for child,axis in zip(children,'RGB'):
                cmds.connectAttr(owner+'.'+child,node+'.'+target+axis)
        cmds.connectAttr(weight,node+'.blender')
        return node+'.output'

    for path in _paths(prefix):
        stem = path[:-4]
        parameter = stem+'ContactU_BTA'
        own = cmds.getAttr(parameter+'.input[0]')
        shared = cmds.getAttr(parameter+'.input[1]')
        amount = cmds.connectionInfo(parameter+'.attributesBlender',sourceFromDestination=True)
        lid = 'upper' if '_upperEyelid' in path else 'lower'
        upper = blend(evaluate('upper',own),evaluate('upper',shared),amount,stem+'DeBoorUpper_BLC')
        lower = blend(evaluate('lower',own),evaluate('lower',shared),amount,stem+'DeBoorLower_BLC')
        contact = blend(lower,upper,prefix+'_eyeDirect_CTL.Blink_Height',stem+'DeBoorContact_BLC')
        output = blend(upper if lid=='upper' else lower,contact,
                       prefix+'_eyeDirect_CTL.'+('Upper_Blink' if lid=='upper' else 'Lower_Blink'),
                       stem+'DeBoorOutput_BLC')
        for source_axis,dest_axis in zip('RGB',('in30','in31','in32')):
            cmds.connectAttr(output+source_axis,stem+'_F4X4.'+dest_axis,force=True)
    return {'samples':len(samples),'sampling':[{'lid':key[0],'u':key[1],'plug':plug} for key,plug in samples.items()],
            'intent':'Static De Boor basis with endpoint interpolation; approximate partial-blink U.'}
