"""Offline exact moving-parameter cubic De Boor prototype.

Compile spline/linear-skin coefficient functions as native animCurveUU cubic
Hermite segments. Native point/vector math evaluates weighted skin moments;
no live NURBS curve, curve skin, blendShape or motionPath is demanded. This
is a cost experiment, not a default builder or an assertion of a speedup.
The 2026-10-16 trial rejects it for Parallel/native reopen failures. Do not
install it on an artist rig; see docs/eyelid_setup_evaluation_20261016.md.
"""
import math
from maya import cmds
from maya.api import OpenMaya as om
from maya.api import OpenMayaAnim as oma
from maya_tools.scripts.utils import de_boor_core


def basis_derivative(count,degree,u,knots):
    """One-sided endpoint derivative of the literal B-spline basis."""
    value=min(max(u,1e-10),1-1e-10)
    lower=de_boor_core.de_boor(count+1,degree-1,value,knots,tol=0)
    result=[]
    for i in range(count):
        a=knots[i+degree]-knots[i]
        b=knots[i+degree+1]-knots[i+1]
        result.append((degree*lower[i]/a if a else 0)-(degree*lower[i+1]/b if b else 0))
    return result


def coefficient(destination,driver,coefficients,degree,knots,name):
    """Emit one exact piecewise-cubic scalar function, or a literal constant."""
    if all(value==coefficients[0] for value in coefficients):
        cmds.setAttr(destination,coefficients[0])
        return
    count=len(coefficients)
    node=cmds.createNode('animCurveUU',name=name)
    selection=om.MSelectionList();selection.add(node)
    function=oma.MFnAnimCurve(selection.getDependNode(0))
    function.setIsWeighted(False)
    derivatives=[]
    for u in sorted(set(knots)):
        basis=([0.]*(count-1)+[1.]) if u==1 else de_boor_core.de_boor(count,degree,u,knots,tol=0)
        slope=basis_derivative(count,degree,u,knots)
        value=sum(a*b for a,b in zip(coefficients,basis))
        derivative=sum(a*b for a,b in zip(coefficients,slope))
        function.addKey(u,value,oma.MFnAnimCurve.kTangentFixed,oma.MFnAnimCurve.kTangentFixed)
        derivatives.append(derivative)
    for index,derivative in enumerate(derivatives):
        function.setTangentsLocked(index,False)
        function.setInTangentType(index,oma.MFnAnimCurve.kTangentFixed)
        function.setOutTangentType(index,oma.MFnAnimCurve.kTangentFixed)
        # cmds.keyTangent angles convert X by scene FPS even for animCurveUU.
        # Raw API tangent vectors explicitly retain dimensionless spline U.
        function.setTangent(index,1.,derivative,True,convertUnits=False)
        function.setTangent(index,1.,derivative,False,convertUnits=False)
    cmds.connectAttr(driver,node+'.input')
    cmds.connectAttr(node+'.output',destination)


def install(prefix):
    data={}
    for label,curve_label in (('upper','Up'),('lower','Down')):
        source=prefix+'_eyelid'+curve_label+'_CRV'
        pose=prefix+'_eyelid'+curve_label+'Pose_CRV'
        shape=cmds.listRelatives(source,shapes=True,noIntermediate=True,fullPath=True)[0]
        selection=om.MSelectionList();selection.add(shape)
        curve=om.MFnNurbsCurve(selection.getDagPath(0))
        if curve.degree!=3 or curve.form!=om.MFnNurbsCurve.kOpen:
            raise ValueError('Prototype requires an open cubic eyelid curve')
        points=list(curve.cvPositions(om.MSpace.kObject))
        knots=list(curve.knots());knots=[knots[0]]+knots+[knots[-1]]
        skin=prefix+'_'+label+'Eyelid_SKIN'
        joints=cmds.skinCluster(skin,q=True,influence=True)
        indices=cmds.getAttr(skin+'.matrix',multiIndices=True)
        bind=[om.MMatrix(cmds.getAttr(skin+'.bindPreMatrix[%d]'%i)) for i in indices]
        geometry=om.MMatrix(cmds.getAttr(skin+'.geomMatrix'))
        weights=[cmds.skinPercent(skin,pose+'.cv[%d]'%i,q=True,value=True) for i in range(len(points))]
        frames=[]
        for j,joint in enumerate(joints):
            stem=prefix+'_'+label+'DeBoorExactJoint%d'%j
            frame=cmds.createNode('multMatrix',name=stem+'_MMX')
            cmds.connectAttr(joint+'.worldMatrix[0]',frame+'.matrixIn[0]')
            cmds.setAttr(frame+'.matrixIn[1]',list(geometry.inverse()),type='matrix')
            cmds.connectAttr(prefix+'_'+label+'LidRoll_MMX.matrixSum',frame+'.matrixIn[2]')
            cmds.connectAttr(pose+'.worldMatrix[0]',frame+'.matrixIn[3]')
            row=cmds.createNode('rowFromMatrix',name=stem+'_ROW')
            cmds.setAttr(row+'.input',3);cmds.connectAttr(frame+'.matrixSum',row+'.matrix')
            local=[p*geometry*bind[j] for p in points]
            coefficients=[[weights[i][j]*list(local[i])[axis] for i in range(len(points))] for axis in range(3)]
            coefficients.append([weights[i][j] for i in range(len(points))])
            frames.append((frame,row,coefficients))
        data[label]=(knots,frames)

    def evaluate(label,driver,stem):
        knots,frames=data[label]
        summed=cmds.createNode('plusMinusAverage',name=stem+'_PMA')
        slot=0
        for j,(frame,row,coefficients) in enumerate(frames):
            if all(w==0 for w in coefficients[3]):continue
            name=stem+'Influence%d'%j
            vector=cmds.createNode('pointMatrixMult',name=name+'_PMM')
            cmds.setAttr(vector+'.vectorMultiply',True)
            cmds.connectAttr(frame+'.matrixSum',vector+'.inMatrix')
            for axis,values in zip('XYZ',coefficients[:3]):
                coefficient(vector+'.inPoint'+axis,driver,values,3,knots,name+axis+'_ACU')
            weighted=cmds.createNode('multiplyDivide',name=name+'_MD')
            for axis in 'XYZ':cmds.connectAttr(row+'.output'+axis,weighted+'.input1'+axis)
            coefficient(weighted+'.input2X',driver,coefficients[3],3,knots,name+'Weight_ACU')
            source=cmds.connectionInfo(weighted+'.input2X',sourceFromDestination=True)
            for axis in 'YZ':
                if source:cmds.connectAttr(source,weighted+'.input2'+axis)
                else:cmds.setAttr(weighted+'.input2'+axis,cmds.getAttr(weighted+'.input2X'))
            for node in (vector,weighted):
                for axis,child in zip('XYZ','xyz'):
                    cmds.connectAttr(node+'.output'+axis,summed+'.input3D[%d].input3D%s'%(slot,child))
                slot+=1
        return summed+'.output3D'

    def blend(a,b,weight,name):
        node=cmds.createNode('blendColors',name=name)
        for source,target in ((a,'color2'),(b,'color1')):
            owner,attribute=source.split('.',1)
            for child,axis in zip(cmds.attributeQuery(attribute,node=owner,listChildren=True),'RGB'):
                cmds.connectAttr(owner+'.'+child,node+'.'+target+axis)
        cmds.connectAttr(weight,node+'.blender')
        return node+'.output'

    paths=cmds.ls(prefix+'_*Eyelid*_MTP',type='motionPath')
    for path in paths:
        stem=path[:-4]
        driver=stem+'ContactU_BTA.output'
        upper=evaluate('upper',driver,stem+'ExactUpper')
        lower=evaluate('lower',driver,stem+'ExactLower')
        contact=blend(lower,upper,prefix+'_eyeDirect_CTL.Blink_Height',stem+'ExactContact_BLC')
        is_upper='_upperEyelid' in path
        output=blend(upper if is_upper else lower,contact,
                     prefix+'_eyeDirect_CTL.'+('Upper_Blink' if is_upper else 'Lower_Blink'),stem+'ExactOutput_BLC')
        for axis,destination in zip('RGB',('in30','in31','in32')):
            cmds.connectAttr(output+axis,stem+'_F4X4.'+destination,force=True)
    return {'paths':len(paths),'intent':'Exact moving-U cubic basis via native unitless animation curves; precision validated separately.'}
