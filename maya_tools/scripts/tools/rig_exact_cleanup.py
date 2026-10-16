"""Explicit, undoable cleanup candidates with separate quality/timing gates.

Use a saved copy. Exact-zero binding removal can slow the post-edit Maya graph
until native reopen; it is not an automatic live-scene/build optimization.
"""
import re
from maya import cmds


def bake_static_point_curves(meshes, apply=False):
    """Replace one-key, un-driven point curves by the same native tweak values.

    Only explicitly supplied mesh shapes are eligible. Time-driven curves,
    referenced data, multiple consumers and custom outgoing connections stay.
    This is data cleanup, not a claim of faster deformation or playback.
    """
    allowed = set()
    for mesh in meshes:
        matches = cmds.ls(mesh, long=True) or []
        if len(matches) != 1:
            raise ValueError('Choose unambiguous mesh data for constant point cleanup.')
        node = matches[0]
        shapes = [node] if cmds.nodeType(node) == 'mesh' else cmds.listRelatives(
            node, shapes=True, noIntermediate=True, type='mesh', fullPath=True) or []
        allowed.update(shapes)
    if not allowed:
        raise ValueError('No polygon mesh was supplied.')
    planned = []
    for shape in sorted(allowed):
        if cmds.referenceQuery(shape, isNodeReferenced=True):
            continue
        nodes = cmds.listConnections(shape+'.pnts', source=True, destination=False,
                                     type='animCurveTL') or []
        for node in sorted(set(nodes)):
            if cmds.referenceQuery(node, isNodeReferenced=True):
                continue
            if cmds.listAttr(node,userDefined=True) or any(cmds.lockNode(node,query=True,lock=True)):
                continue
            if cmds.listConnections(node, source=True, destination=False):
                continue
            if cmds.keyframe(node, query=True, keyframeCount=True) != 1:
                continue
            targets = cmds.listConnections(node, source=False, destination=True, plugs=True) or []
            outputs = cmds.listConnections(node+'.output', source=False, destination=True, plugs=True) or []
            if len(targets) != 1 or outputs != targets:
                continue
            destination = outputs[0]
            target, attribute = destination.split('.',1)
            paths = cmds.ls(target,long=True) or []
            if paths != [shape] or not re.fullmatch(r'(pnts\[\d+\]\.pnt[xyz]|pt\[\d+\]\.p[xyz])', attribute):
                continue
            if cmds.getAttr(destination,lock=True):
                continue
            planned.append({'curve':node,'destination':destination,'value':cmds.getAttr(destination)})
    result = {'applied':False,'planned':planned,'count':len(planned),
              'meaning':'Static point data cleanup only; no measured playback saving is implied.'}
    if not apply or not planned:
        return result
    undo = cmds.undoInfo(query=True,state=True)
    cmds.undoInfo(stateWithoutFlush=True)
    cmds.undoInfo(openChunk=True,chunkName='Bake static mesh point data')
    try:
        for row in planned:
            cmds.disconnectAttr(row['curve']+'.output',row['destination'])
            cmds.setAttr(row['destination'],row['value'])
        cmds.delete([row['curve'] for row in planned])
    except BaseException:
        cmds.undoInfo(closeChunk=True)
        cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)
        result['applied']=True
    finally:
        cmds.undoInfo(stateWithoutFlush=undo)
    return result


def remove_exact_zero_influences(skins, apply=False):
    """Remove only influence columns that are exactly zero at every vertex.

    The retained native weights and DQ blend masks must remain bit-identical.
    No epsilon pruning, maximum-influence reduction or method change is used.
    Curve/surface skins and animated/locked normalization settings are excluded.
    """
    import numpy as np
    from maya.api import OpenMaya as om, OpenMayaAnim as oma
    from maya_tools.scripts.tools import bifrost_wrinkles
    plans=[]
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for node in dict.fromkeys(skins):
            if cmds.nodeType(node)!='skinCluster' or cmds.referenceQuery(node,isNodeReferenced=True):
                continue
            if cmds.listConnections(node+'.weightList',source=True,destination=False):
                continue
            flags=('normalizeWeights','maintainMaxInfluences')
            if any(not cmds.getAttr(node+'.'+flag,settable=True) for flag in flags):
                continue
            fn=oma.MFnSkinCluster(om.MSelectionList().add(node).getDependNode(0))
            outputs=list(fn.getOutputGeometry())
            if len(outputs)!=1 or not outputs[0].hasFn(om.MFn.kMesh):
                continue
            path=om.MDagPath.getAPathTo(outputs[0])
            component_fn=om.MFnSingleIndexedComponent()
            component=component_fn.create(om.MFn.kMeshVertComponent)
            component_fn.setCompleteData(om.MFnMesh(path).numVertices)
            weights,count=fn.getWeights(path,component)
            weights=np.asarray(weights).reshape((-1,count)).copy()
            names=[p.fullPathName() for p in fn.influenceObjects()]
            keep=np.any(weights!=0.,axis=0)
            if keep.all() or not keep.any():
                continue
            plans.append({'node':node,'path':path,'component':component,'weights':weights,
                          'names':names,'keep':keep,'blend':np.asarray(fn.getBlendWeights(path,component)).copy(),
                          'flags':{flag:cmds.getAttr(node+'.'+flag) for flag in flags}})
        report={'applied':False,'skins':[{'skin':p['node'],'before':len(p['names']),
                  'after':int(p['keep'].sum()),'removed':[n for n,k in zip(p['names'],p['keep']) if not k]}
                  for p in plans], 'retained_weights_exact':True,'dq_masks_exact':True}
        report['removed_count']=sum(len(row['removed']) for row in report['skins'])
        if not apply or not plans:
            return report
        undo=cmds.undoInfo(query=True,state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        cmds.undoInfo(openChunk=True,chunkName='Remove exact zero skin dependencies')
        try:
            for plan in plans:
                node=plan['node']
                cmds.setAttr(node+'.normalizeWeights',0)
                cmds.setAttr(node+'.maintainMaxInfluences',False)
                remove=[name for name,keep in zip(plan['names'],plan['keep']) if not keep]
                cmds.skinCluster(node,edit=True,removeInfluence=remove)
                for flag,value in plan['flags'].items():cmds.setAttr(node+'.'+flag,value)
                fn=oma.MFnSkinCluster(om.MSelectionList().add(node).getDependNode(0))
                names=[p.fullPathName() for p in fn.influenceObjects()]
                expected=[n for n,k in zip(plan['names'],plan['keep']) if k]
                if set(names)!=set(expected):raise RuntimeError('Unexpected influence removal on '+node)
                weights,count=fn.getWeights(plan['path'],plan['component'])
                actual=np.asarray(weights).reshape((-1,count))
                before=plan['weights'][:,[plan['names'].index(name) for name in names]]
                if not np.array_equal(actual,before):raise RuntimeError('Retained weights changed on '+node)
                if not np.array_equal(np.asarray(fn.getBlendWeights(plan['path'],plan['component'])),plan['blend']):
                    raise RuntimeError('DQ blend mask changed on '+node)
        except BaseException:
            cmds.undoInfo(closeChunk=True)
            cmds.undo()
            raise
        else:
            cmds.undoInfo(closeChunk=True)
            report['applied']=True
        finally:
            cmds.undoInfo(stateWithoutFlush=undo)
    return report


def share_identical_lip_math(namespace='', nodes=None):
    """Share identical native calculations, optionally only supplied build nodes."""
    prefix=namespace.rstrip(':')+':' if namespace else ''
    groups={};plans=[]
    candidates=None if nodes is None else list(dict.fromkeys(nodes))
    specs=(('blendMatrix',r'[LR]_(upper|lower)Lip\d+CornerRotation_BMX',
            ('inputMatrix','envelope','target[0].targetMatrix','target[0].weight',
             'target[0].translateWeight','target[0].rotateWeight','target[0].scaleWeight',
             'target[0].shearWeight','target[0].useMatrix'),'outputMatrix'),
           ('multMatrix',r'C_lipCorner\d+Frame_MMX',('matrixIn[0]','matrixIn[1]'),'matrixSum'))
    def signature(node,attributes):
        values=[]
        optional=tuple(attr for attr in ('frozen','rotationInterpolation') if cmds.attributeQuery(attr,node=node,exists=True))
        for attr in attributes+('nodeState','caching')+optional:
            plug=node+'.'+attr
            source=cmds.connectionInfo(plug,sourceFromDestination=True)
            value=cmds.getAttr(plug) if not source else None
            values.append((attr,source,repr(value)))
        return tuple(values)
    for kind,pattern,attributes,output in specs:
        if candidates is None:
            matching=cmds.ls(type=kind) or []
        else:
            matching=(cmds.ls(candidates,type=kind) or []) if candidates else []
        for node in sorted(matching):
            local=node[len(prefix):] if node.startswith(prefix) else ''
            if candidates is not None and not prefix:
                local=node.rsplit(':',1)[-1]
            if not re.fullmatch(pattern,local) or cmds.referenceQuery(node,isNodeReferenced=True):continue
            if cmds.getAttr(node+'.nodeState')!=0 or cmds.listAttr(node,userDefined=True):continue
            if kind=='blendMatrix' and cmds.getAttr(node+'.target',multiIndices=True)!=[0]:continue
            if kind=='multMatrix' and cmds.getAttr(node+'.matrixIn',multiIndices=True)!=[0,1]:continue
            key=(kind,signature(node,attributes))
            if key in groups:plans.append((node,groups[key],output))
            else:groups[key]=node
    result={'removed':[],'rewired':[],'arithmetic':'Identical native node type, exact input sources/values; no compose/aim replacement or zero-weight shortcut.'}
    undo=cmds.undoInfo(query=True,state=True)
    cmds.undoInfo(stateWithoutFlush=True);cmds.undoInfo(openChunk=True,chunkName='Share identical lip math')
    try:
        for old,new,output in plans:
            for destination in cmds.listConnections(old+'.'+output,source=False,destination=True,plugs=True) or []:
                target=re.fullmatch(r'(.+\.target\[\d+\])\.targetMatrix',destination)
                settings={}
                if target and cmds.nodeType(destination.split('.',1)[0])=='blendMatrix':
                    for attr in ('weight','translateWeight','rotateWeight','scaleWeight','shearWeight','useMatrix'):
                        plug=target[1]+'.'+attr
                        settings[plug]=(cmds.connectionInfo(plug,sourceFromDestination=True),cmds.getAttr(plug))
                cmds.connectAttr(new+'.'+output,destination,force=True)
                for plug,(source,value) in settings.items():
                    if source:
                        if not cmds.isConnected(source,plug):cmds.connectAttr(source,plug,force=True)
                    else:cmds.setAttr(plug,value)
                result['rewired'].append((old+'.'+output,new+'.'+output,destination))
            if not cmds.listConnections(old,source=False,destination=True):
                cmds.delete(old);result['removed'].append(old)
    except BaseException:
        cmds.undoInfo(closeChunk=True);cmds.undo();raise
    else:cmds.undoInfo(closeChunk=True)
    finally:cmds.undoInfo(stateWithoutFlush=undo)
    return result
