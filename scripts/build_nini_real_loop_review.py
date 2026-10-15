"""Transfer the validated Nini loop layers onto an existing full production rig."""
import copy
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def influence_name(name):
    name = name.rsplit('|',1)[-1]
    match = re.fullmatch(r'([LR])_Eye_(Upper|Lower)_(\d+)_JNT',name)
    if match:
        side,part,index = match.groups()
        return '{}_{}Eyelid{:02d}_ENV'.format(side,'upper' if part=='Upper' else 'down',int(index))
    match = re.fullmatch(r'([LR])_eyebrow(\d+)_JNT',name)
    if match: return '{}_eyebrowSkinning{}_ENV'.format(*match.groups())
    if 'Lip' in name: return name.removesuffix('_JNT') + '_ENV'
    raise ValueError('No production influence mapping for ' + name)


def build(rig_scene, snapshot, output=None):
    from maya import cmds
    from ngSkinTools2 import api
    from ngSkinTools2.api import target_info
    from maya_tools.scripts.tools import facial_loop_skinning as tool
    if not cmds.about(batch=True): raise RuntimeError('Run in isolated mayapy.')
    source = json.loads(Path(snapshot).read_text(encoding='utf-8'))
    output_dir = ROOT/'maya_tools/assets/Nini/review/loop_rigger'
    if output is None:
        version = 1
        while (output_dir/'Nini_LoopRigger_REAL_v{:03d}.ma'.format(version)).exists(): version+=1
        output = output_dir/'Nini_LoopRigger_REAL_v{:03d}.ma'.format(version)
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    cmds.file(str(rig_scene),open=True,force=True,executeScriptNodes=False)
    cmds.evaluationManager(mode='off');cmds.undoInfo(state=False);cmds.currentTime(1)
    cmds.currentTime(2,update=True);cmds.currentTime(1,update=True)
    cmds.dgdirty(allPlugs=True)
    mesh,topology = tool.read_mesh('c_body_GEO')
    assert topology.signature == source['regions'][0]['topology_hash']
    assert cmds.objExists('C_jaw_CTL') and not cmds.objExists('C_loopBase_JNT')
    skin = 'C_body_SKC'
    influences = {i.path.rsplit('|',1)[-1]:i for i in target_info.list_influences(skin)}
    required = {influence_name(joint) for r in source['regions'] for layer in r['weight_layers'] for joint in layer['joints']}
    missing = required-set(influences)
    assert not missing,sorted(missing)
    joint_count = len(cmds.ls(type='joint'))
    layers = api.init_layers(skin)
    assert not layers.list(), 'The supplied real rig already has NG layers.'
    base = layers.add('Base - Nini_v021 production skin')
    dq = base.get_weights(api.NamedPaintTarget.DUAL_QUATERNION)
    records,anchor_errors = [],{}
    with api.suspend_updates(skin):
        for region in source['regions']:
            record = copy.deepcopy(region)
            record.update(mesh=mesh,skin=skin)
            group = layers.add(region['layer_name'],force_empty=True)
            paired = len(region['weight_layers'])==2
            group.opacity = region.get('group_opacity',1)
            if paired and region.get('group_mask'):group.set_weights(api.NamedPaintTarget.MASK,region['group_mask'])
            descriptions = []
            for desc in region['weight_layers']:
                layer = layers.add(desc['layer_name'],force_empty=True,parent=group) if paired else group
                layer.opacity = desc.get('opacity',1)
                mapped_weights = {}
                for joint,values in desc['weights'].items():
                    actual = influence_name(joint)
                    weights = [0.0]*len(topology.points)
                    for v,w in values.items(): weights[int(v)] = w
                    layer.set_weights(influences[actual].logicalIndex,weights)
                    mapped_weights[actual] = values
                if desc.get('mask'): layer.set_weights(api.NamedPaintTarget.MASK,desc['mask'])
                if dq: layer.set_weights(api.NamedPaintTarget.DUAL_QUATERNION,dq)
                descriptions.append(dict(desc,layer_id=layer.id,parent_name=group.name if paired else None,
                    joints=[influence_name(j) for j in desc['joints']],weights=mapped_weights))
                if paired: layer.index = 1 if desc['kind']=='rotate' else 0
            record.update(layer_id=group.id,weight_layers=descriptions)
            record['joints'] = {v:influence_name(j) for v,j in record['joints'].items()}
            for section in record['sections']:
                section['plan']['mesh'] = mesh
                section['joints'] = [influence_name(j) for j in section['joints']]
                section['non_rotate_joints'] = [influence_name(j) for j in section.get('non_rotate_joints',[])]
            for column in record['assignments']:
                column['joint'] = influence_name(column['joint'])
                if column.get('non_rotate_joint'):column['non_rotate_joint'] = influence_name(column['non_rotate_joint'])
                joint = column['joint']
                anchor_errors[joint] = math.dist(cmds.xform(joint,q=True,ws=True,t=True),topology.points[column['anchor']])
            group.enabled = group.name=='Lips'
            node = cmds.createNode('network',name=group.name+'_loopRegion')
            cmds.addAttr(node,ln='loopRegionData',dt='string');cmds.setAttr(node+'.loopRegionData',json.dumps(record),type='string')
            records.append(record)
    assert len(cmds.ls(type='joint'))==joint_count
    _,after = tool.read_mesh(mesh)
    neutral_error = max(math.dist(a,b) for a,b in zip(topology.points,after.points))
    from maya.api import OpenMaya as om
    identity = list(om.MMatrix())
    residuals = {}
    for name in required:
        if 'Lip' not in name:continue
        index = influences[name].logicalIndex
        matrix = om.MMatrix(cmds.getAttr('{}.bindPreMatrix[{}]'.format(skin,index))) * om.MMatrix(cmds.getAttr(name+'.worldMatrix[0]'))
        residuals[name] = max(abs(a-b) for a,b in zip(list(matrix),identity))
    print('NEUTRAL_TRANSFER='+json.dumps({'error':neutral_error,'bind_residual':max(residuals.values()),
          'lip_anchor_error':max(e for n,e in anchor_errors.items() if 'Lip' in n)}),flush=True)
    assert neutral_error<.005,neutral_error
    # Drive the existing animator controls; no review joints or direct joint keys.
    poses = [('Left corner',12,'L_lipCorner_CTL.ty',.5),('Right corner',24,'R_lipCorner_CTL.ty',.5),
             ('Upper lip',36,'C_upperLip_CTL.ty',.35),('Lower lip',48,'C_lowerLip_CTL.ty',-.35),
             ('Upper lip roll',60,'C_upperLip_CTL.Roll',12),('Lower lip roll',72,'C_lowerLip_CTL.Roll',-12),
             ('Jaw opening',84,'C_jaw_CTL.rx',15),('Main mouth',96,'C_mainMouth_CTL.ty',.5),
             ('Head integration',108,'C_head_CTL.ry',12)]
    for label,frame,plug,value in poses:
        assert cmds.objExists(plug),plug
        for time,number in ((1,0),(frame-5,0),(frame,value),(frame+5,0),(120,0)):
            cmds.setKeyframe(plug,time=time,value=number)
    cmds.playbackOptions(minTime=1,maxTime=120,animationStartTime=1,animationEndTime=120)
    cmds.currentTime(1)
    camera,shape = cmds.camera(name='Nini_RealLoopReview_CAM',orthographic=True)
    cmds.setAttr(camera+'.translate',0,118,65);cmds.setAttr(shape+'.orthographicWidth',25)
    for name in ('c_hood_GEO',):
        if cmds.objExists(name):cmds.setAttr(name+'.visibility',False)
    report = dict(source,prototype=False,production_rig=True,source_rig=str(rig_scene),source_snapshot=str(snapshot),
        mesh=mesh,skin=skin,regions=records,camera=camera,source_skin='Nini_v021.skc',
        ng_layer_count=len(layers.list()),joint_count=joint_count,skin_influence_count=len(influences),
        neutral_transfer_max_error=neutral_error,anchor_errors=anchor_errors,
        neutral_bind_residuals=residuals,
        poses=[dict(label=label,frame=frame,control=plug.split('.')[0],channel=plug.split('.')[1],value=value)
               for label,frame,plug,value in poses],
        note='Full production autorig and production skin. Only animator controls drive the review poses. Full loop masks remain editable.')
    report.pop('validation',None)
    node = cmds.createNode('network',name='Nini_LOOP_REVIEW_INFO')
    cmds.addAttr(node,ln='reviewData',dt='string');cmds.setAttr(node+'.reviewData',json.dumps(report),type='string')
    tool.resolve_layer(skin,records[0]['weight_layers'][0]).set_current()
    cmds.select(mesh,r=True)
    cmds.file(rename=str(output));cmds.file(save=True,type='mayaAscii',force=False)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('REAL_LOOP_REVIEW='+json.dumps({'scene':str(output),'joints':joint_count,'influences':len(influences),
          'max_lip_anchor_error':max(error for joint,error in anchor_errors.items() if 'Lip' in joint),
          'neutral_transfer_error':neutral_error}),flush=True)
    return output


if __name__=='__main__':
    os.environ['MAYA_SKIP_USERSETUP_PY']='1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    try:
        from maya import cmds
        ng = Path('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents')
        sys.path.insert(0,str(ng/'scripts'))
        cmds.loadPlugin(str(ng/'plug-ins'/str(cmds.about(version=True))/'ngSkinTools2.mll'),quiet=True)
        build(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
    finally:maya.standalone.uninitialize()
