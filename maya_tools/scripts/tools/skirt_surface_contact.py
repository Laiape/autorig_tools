"""Sparse native surface contact after skin, without modifying skin data.

An upstream intermediate mesh is read explicitly. Edge endpoints provide exact
evaluated vertex positions; closest-point normals generate outward-only tweaks
on a separate output shape. No output geometry feeds its own driver graph.
This local normal projection is intended for the convex waist transition. It is
not a general closed-mesh containment or self-collision solver.
"""
import math
from maya import cmds
from maya.api import OpenMaya as om


def attach(data, graph, settings, body, depth=None):
    """Append an owned contact output to each garment; preserve appearance."""
    from maya_tools.scripts.tools import dress_keepout_chains as dress
    target = dress.mesh_path(body).fullPathName()
    inverse = om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
    scale = graph.node('decomposeMatrix','SurfaceScale_DCM')
    cmds.connectAttr(data['waist']+'.worldMatrix[0]',scale+'.inputMatrix')
    margin = graph.mul('SurfaceWorldMargin',settings+'.surfaceMargin',scale+'.outputScaleX')
    if depth is None:
        depth = (data['top_local']-min(data['hems_local']))*.55
    strength = graph.mul('SurfaceBlend',settings+'.solverBlend',settings+'.collisionBlend')
    strength = graph.mul('SurfaceEnable',strength,settings+'.collisionEnable')
    strength = graph.mul('SurfaceContact',strength,settings+'.surfaceContact')
    result = []
    for garment_index, garment in enumerate(data['garments']):
        mesh = garment['mesh']
        path = dress.mesh_path(mesh)
        source = path.fullPathName()
        fn = om.MFnMesh(path)
        points = fn.getPoints(om.MSpace.kWorld)
        indices = [v for v in garment['region'] if garment['alpha'][v]>0
                   and (points[v]*inverse).y >= data['top_local']-depth]
        if not indices:
            continue
        shaders,shader_ids = fn.getConnectedShaders(path.instanceNumber())
        groups = {}
        for face,index in enumerate(shader_ids):
            if index >= 0:
                groups.setdefault(om.MFnDependencyNode(shaders[index]).name(),[]).append(face)
        iterator = om.MItMeshVertex(path)
        edge_ids = {}
        edge = om.MItMeshEdge(path)
        for vertex in indices:
            iterator.setIndex(vertex)
            edge_id = iterator.getConnectedEdges()[0]
            edge.setIndex(edge_id)
            edge_ids[vertex] = (edge_id,edge.vertexId(0),edge.vertexId(1))
        output = cmds.createNode('mesh',name=graph.prefix+'Surface{:02d}Shape'.format(garment_index),parent=mesh,skipSelect=True)
        cmds.connectAttr(source+'.outMesh',output+'.inMesh')
        for attr in ('displaySmoothMesh','smoothLevel','renderSmoothLevel','useSmoothPreviewForRender',
                     'castsShadows','receiveShadows','doubleSided','opposite'):
            if cmds.objExists(source+'.'+attr) and cmds.objExists(output+'.'+attr):
                cmds.setAttr(output+'.'+attr,cmds.getAttr(source+'.'+attr))
        cmds.setAttr(source+'.intermediateObject',True)
        for sg,faces in groups.items():
            cmds.sets([output+'.f[{}]'.format(v) for v in faces],edit=True,forceElement=sg)
        for vertex in indices:
            label = 'g{:02d}_v{:04d}'.format(garment_index,vertex)
            edge_node = graph.node('curveFromMeshEdge',label+'Edge_CME')
            cmds.connectAttr(source+'.worldMesh[0]',edge_node+'.inputMesh')
            cmds.setAttr(edge_node+'.edgeIndex[0]',edge_ids[vertex][0])
            point = graph.node('pointOnCurveInfo',label+'Point_PCI')
            cmds.connectAttr(edge_node+'.outputCurve',point+'.inputCurve')
            cmds.setAttr(point+'.turnOnPercentage',True)
            first = cmds.getAttr(point+'.position')[0]
            cmds.setAttr(point+'.parameter',1)
            last = cmds.getAttr(point+'.position')[0]
            if math.dist(tuple(points[vertex])[:3],first) <= math.dist(tuple(points[vertex])[:3],last):
                cmds.setAttr(point+'.parameter',0)
            closest = graph.node('closestPointOnMesh',label+'Closest_CPM')
            cmds.connectAttr(target+'.worldMesh[0]',closest+'.inMesh')
            cmds.connectAttr(point+'.position',closest+'.inPosition')
            difference = graph.node('plusMinusAverage',label+'Difference_PMA')
            cmds.setAttr(difference+'.operation',2)
            cmds.connectAttr(point+'.position',difference+'.input3D[0]')
            cmds.connectAttr(closest+'.position',difference+'.input3D[1]')
            dot = graph.node('vectorProduct',label+'Signed_VPR')
            cmds.setAttr(dot+'.operation',1)
            cmds.connectAttr(difference+'.output3D',dot+'.input1')
            cmds.connectAttr(closest+'.normal',dot+'.input2')
            distance = graph.maximum(label+'Positive',graph.sub(label+'Depth',margin,dot+'.outputX'),0)
            distance = graph.mul(label+'Enabled',distance,strength)
            push = graph.node('multiplyDivide',label+'WorldPush_MDV')
            cmds.connectAttr(closest+'.normal',push+'.input1')
            for axis in 'XYZ':cmds.connectAttr(distance,push+'.input2'+axis)
            local = graph.node('vectorProduct',label+'LocalPush_VPR')
            cmds.setAttr(local+'.operation',3)
            cmds.connectAttr(push+'.output',local+'.input1')
            cmds.connectAttr(mesh+'.worldInverseMatrix[0]',local+'.matrix')
            cmds.connectAttr(local+'.output',output+'.pnts[{}]'.format(vertex))
        result.append({'mesh':mesh,'source_shape':source,'output_shape':output,
                       'vertices':indices,'target':body})
    return result
