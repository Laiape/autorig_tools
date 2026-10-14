"""Preflighted transfer to a fresh rig; source rig remains intact.

Supported: semantic animator controls/time-based curves, one skin per mesh,
matching topology, managed pose/combination/orientation correctives. Other
stacks require an explicit manual migration and block this transaction.
"""
import copy
import json
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_roles as roles, rig_validation as qa, pose_blendshapes as poses
from maya_tools.scripts.tools import combination_correctives as combos, orientation_correctives as orientation
from maya_tools.scripts.tools import corrective_transfer, skinning_volume

TIME_CURVES=('animCurveTA','animCurveTL','animCurveTT','animCurveTU')


def _mapped(node, destination):
    result=roles.counterpart(node,destination_root=destination)
    if not result:raise ValueError('Source node has no semantic binding: '+node)
    return result


def preview(source, destination):
    source,destination=roles.path(source),roles.path(destination)
    if source==destination or source.startswith(destination+'|') or destination.startswith(source+'|'):
        raise ValueError('Choose separate source and destination character roots.')
    plan={'format':'autorig-rig-migration','version':1,'source':source,'destination':destination,
          'controls':[],'meshes':[],'orientation_systems':[],'issues':[],
          'limits':'Fresh destination, identical mesh topology, one skin, managed corrective targets; other stacks block migration.'}
    bindings=roles.bindings(source)
    if not bindings:plan['issues'].append('Source rig has no semantic bindings.')
    for binding in bindings:
        node=binding['node']
        if binding['kind']=='control':
            try:
                target=_mapped(node,destination)
                channels=[]
                for attr in cmds.listAttr(node,keyable=True,scalar=True) or []:
                    if attr=='visibility':continue
                    plug=node+'.'+attr;target_plug=target+'.'+attr
                    value=cmds.getAttr(plug)
                    if not isinstance(value,(int,float)):continue
                    connection=cmds.connectionInfo(plug,sourceFromDestination=True)
                    if cmds.getAttr(plug,lock=True):continue
                    curve=connection.rsplit('.',1)[0] if connection else None
                    if curve and cmds.nodeType(curve) not in TIME_CURVES:
                        raise ValueError('Unsupported control driver: '+plug)
                    if not cmds.objExists(target_plug) or cmds.getAttr(target_plug,lock=True) or cmds.connectionInfo(target_plug,sourceFromDestination=True):
                        raise ValueError('Destination channel is missing, locked or already driven: '+target_plug)
                    channels.append({'source':plug,'destination':target_plug,'curve':curve,'value':value})
                plan['controls'].append({'binding':binding['key'],'channels':channels})
            except ValueError as exc:plan['issues'].append(str(exc))
        if binding['kind']=='mesh':
            try:
                target=_mapped(node,destination)
                if qa.mesh_data(node)['topology']!=qa.mesh_data(target)['topology']:
                    raise ValueError('Changed topology needs an explicit projection: '+binding['key'])
                history=cmds.listHistory(node) or []
                skins=cmds.ls(history,type='skinCluster') or []
                if len(skins)>1:raise ValueError('Stacked skins require manual migration: '+node)
                if cmds.ls(cmds.listHistory(target) or [],type='geometryFilter'):
                    raise ValueError('Destination mesh already has deformers: '+target)
                unsupported=[n for n in cmds.ls(history,type='geometryFilter') or [] if cmds.nodeType(n) not in ('skinCluster','blendShape')]
                if unsupported:raise ValueError('Unsupported deformer stack: '+', '.join(unsupported))
                influences=[]
                if skins:
                    fn,_,_=skinning_volume.skin_data(node,skins[0])
                    influences=[{'source':p.fullPathName(),'destination':_mapped(p.fullPathName(),destination)} for p in fn.influenceObjects()]
                blendshapes=poses.blendshapes(node)
                for bs in blendshapes:
                    for index,_ in poses.targets(bs):
                        record=poses.pose_record(bs,index)
                        if not record:raise ValueError('Unmanaged blendshape target: %s[%d]'%(bs,index))
                        snapshot=combos.data(record)
                        for c in snapshot['captures'] if snapshot else [{'controller':poses.linked(record,'controller')}]:
                            _mapped(c['controller'],destination)
                        system=orientation.linked(record,'orientationSystem')
                        if system and system not in plan['orientation_systems']:
                            joint,reference=orientation.linked(system,'joint'),orientation.linked(system,'reference')
                            target_joint,target_reference=_mapped(joint,destination),_mapped(reference,destination)
                            for attr in ('jointOrient','rotateAxis'):
                                if cmds.attributeQuery(attr,node=joint,exists=True) and cmds.getAttr(joint+'.'+attr)!=cmds.getAttr(target_joint+'.'+attr):
                                    raise ValueError('Changed orientation convention needs recaptured correctives: '+joint)
                            plan['orientation_systems'].append(system)
                        delta=poses._delta_path(bs,node,index)
                        if cmds.listConnections(delta+'.inputGeomTarget',s=True,d=False):
                            raise ValueError('Save live target sculpts before migration: '+bs)
                plan['meshes'].append({'source':node,'destination':target,'binding':binding['key'],
                                       'skin':skins[0] if skins else None,'influences':influences,'blendshapes':blendshapes})
            except ValueError as exc:plan['issues'].append(str(exc))
    # Unbound animated controls and deformed meshes must not disappear silently.
    known={b['node'] for b in bindings}
    for node in qa._controls(source):
        if node not in known:plan['issues'].append('Unbound animator control: '+node)
    for shape in cmds.listRelatives(source,allDescendents=True,type='mesh',fullPath=True) or []:
        if cmds.getAttr(shape+'.intermediateObject'):continue
        mesh=cmds.listRelatives(shape,parent=True,fullPath=True)[0]
        if mesh not in known and cmds.ls(cmds.listHistory(mesh) or [],type='geometryFilter'):
            plan['issues'].append('Unbound deformed mesh: '+mesh)
    plan['ready']=not plan['issues'] and bool(plan['controls'] or plan['meshes'])
    return plan


def _copy_skin(item):
    source,target=item['source'],item['destination']
    source_fn,source_path,component=skinning_volume.skin_data(source,item['skin'])
    weights,stride=source_fn.getWeights(source_path,component)
    blend=list(source_fn.getBlendWeights(source_path,component))
    target_skin=cmds.skinCluster([i['destination'] for i in item['influences']],target,toSelectedBones=True,
                                name=item['skin'].split(':')[-1]+'_Migrated')[0]
    target_fn,target_path,target_comp=skinning_volume.skin_data(target,target_skin)
    mapping={roles.path(i['destination']):col for col,i in enumerate(item['influences'])}
    columns=[mapping[p.fullPathName()] for p in target_fn.influenceObjects()]
    values=[weights[vertex*stride+col] for vertex in range(len(weights)//stride) for col in columns]
    target_fn.setWeights(target_path,target_comp,om.MIntArray(list(range(len(columns)))),om.MDoubleArray(values),False)
    target_fn.setBlendWeights(target_path,target_comp,om.MDoubleArray(blend))
    for attr in ('skinningMethod','normalizeWeights','maintainMaxInfluences','maxInfluences'):
        cmds.setAttr(target_skin+'.'+attr,cmds.getAttr(item['skin']+'.'+attr))
    return target_skin


@poses.undoable
def apply(source,destination):
    """Recompute preflight; no stale preview is trusted. One Maya Undo removes candidate."""
    poses._idle()
    plan=preview(source,destination)
    if not plan['ready']:raise ValueError('Migration needs review: '+'; '.join(plan['issues']))
    neutral={}
    for root in (plan['source'],plan['destination']):neutral.update(qa._neutral_values(root)[0])
    result={'controls':0,'animation_curves':[],'skins':[],'targets':[],'source_preserved':True}
    with poses._temporary_values(neutral):
        systems={}
        for entry in orientation.export_systems():
            if entry['name'] not in plan['orientation_systems']:continue
            copied=copy.deepcopy(entry);copied['name']=entry['name']+'_Migrated'
            def resolve(name):
                return _mapped(name,plan['destination']) if name in (entry['joint'],entry['reference']) else None
            node_map={};warnings=[]
            orientation.import_systems([copied],resolve,node_map,warnings)
            if warnings:raise ValueError('; '.join(warnings))
            systems[entry['name']]=node_map[copied['name']]
        for item in plan['meshes']:
            if item['skin']:result['skins'].append(_copy_skin(item))
            for bs in item['blendshapes']:
                destination_bs=poses.create_blendshape(item['destination'],poses.deformation_order(bs,item['source']))
                mapping={}
                # Every dependency precedes its combination, independent of target index order.
                order=[]
                for index,_ in poses.targets(bs):
                    order.extend(i for i in combos.dependency_order(bs,index) if i not in order)
                for index in order:
                    source_record=poses.pose_record(bs,index)
                    controller=_mapped(poses.linked(source_record,'controller'),plan['destination'])
                    transfer=corrective_transfer.transfer_target(item['source'],bs,index,item['destination'],
                        destination_bs=destination_bs,controller=controller,_single=True)
                    new_index=transfer['index'];mapping[index]=new_index
                    new_record=poses.pose_record(destination_bs,new_index)
                    snapshot=combos.data(source_record)
                    if snapshot:
                        copied=copy.deepcopy(snapshot);copied['drivers']=[mapping[i] for i in snapshot['drivers']]
                        for c in copied['captures']:c['controller']=_mapped(c['controller'],plan['destination'])
                        combos.restore(new_record,destination_bs,new_index,copied)
                    system=orientation.linked(source_record,'orientationSystem')
                    if system:
                        orientation.share_target(systems[system],cmds.getAttr(source_record+'.orientationPose'),destination_bs,new_index,new_record)
                    result['targets'].append({'source':bs+'.weight[%d]'%index,'destination':destination_bs+'.weight[%d]'%new_index})
    # Apply motion after binding and sculpt transfer at neutral.
    for control in plan['controls']:
        for channel in control['channels']:
            if channel['curve']:
                new=cmds.duplicate(channel['curve'],name=channel['curve'].split(':')[-1]+'_Migrated',inputConnections=True)[0]
                cmds.connectAttr(new+'.output',channel['destination'])
                result['animation_curves'].append(new)
            else:cmds.setAttr(channel['destination'],channel['value'])
        result['controls']+=1
    return result
