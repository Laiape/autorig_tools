"""Native detail switching and measured interactive viewport updates."""
import json,time,statistics,math
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import rig_validation as qa,pose_blendshapes as poses

@poses.undoable
def create_detail_modes(root, high, low, wrinkle_settings=None):
    root=cmds.ls(root,long=True)[0]
    high=[poses.mesh_transform(m) for m in high];low=[poses.mesh_transform(m) for m in low]
    if not high or not low or set(high).intersection(low) or cmds.attributeQuery('detailMode',node=root,exists=True):
        raise ValueError('Use separate high/low meshes and a root without a detail setup.')
    settings=list(wrinkle_settings or [])
    plugs=[m+'.visibility' for m in high+low]+[s+'.Envelope' for s in settings]
    if any(not cmds.getAttr(p,settable=True) for p in plugs):
        raise ValueError('Detail visibility or wrinkle envelope already has a driver.')
    data={'version':1,'root':root,'high':high,'low':low,'wrinkle_settings':settings,
          'original_values':{p:cmds.getAttr(p) for p in plugs}}
    cmds.addAttr(root,ln='detailMode',at='enum',enumName='Animation:Review:Export',defaultValue=1,k=True)
    record=cmds.createNode('network',name=root.rsplit('|',1)[-1]+'_detailModes')
    poses._string(record,'detailData',json.dumps(data));poses._message(root,record,'characterRoot')
    for label,operation in (('high',1),('low',0)):
        condition=cmds.createNode('condition',name=record+'_'+label)
        cmds.setAttr(condition+'.operation',operation)
        cmds.setAttr(condition+'.secondTerm',0)
        cmds.setAttr(condition+'.colorIfTrueR',1);cmds.setAttr(condition+'.colorIfFalseR',0)
        cmds.connectAttr(root+'.detailMode',condition+'.firstTerm')
        for mesh in data[label]:cmds.connectAttr(condition+'.outColorR',mesh+'.visibility')
        if label=='high':
            for setting in settings:
                multiply=cmds.createNode('multiplyDivide',name=record+'_wrinkleEnvelope')
                cmds.setAttr(multiply+'.input1X',data['original_values'][setting+'.Envelope'])
                cmds.connectAttr(condition+'.outColorR',multiply+'.input2X')
                cmds.connectAttr(multiply+'.outputX',setting+'.Envelope')
    return record

def export_detail_modes():
    return [json.loads(cmds.getAttr(n+'.detailData')) for n in cmds.ls(type='network') or []
            if cmds.attributeQuery('detailData',node=n,exists=True)]

def restore_detail_modes(records):
    for record in records:
        if not cmds.attributeQuery('detailMode',node=record['root'],exists=True):
            create_detail_modes(record['root'],record['high'],record['low'],record['wrinkle_settings'])
        root = cmds.ls(record['root'], long=True)[0]
        networks = [n for n in cmds.listConnections(root + '.message', source=False, destination=True, type='network') or []
                    if cmds.attributeQuery('detailData', node=n, exists=True)]
        if len(networks) > 1:
            raise ValueError('Ambiguous detail ownership on ' + root)
        if networks:
            network = networks[0]
        else:
            network = cmds.createNode('network', name=root.rsplit('|', 1)[-1] + '_detailModes')
            poses._message(root, network, 'characterRoot')
            poses._string(network, 'detailData', json.dumps(record))
        conditions = cmds.listConnections(root + '.detailMode', source=False, destination=True, type='condition') or []
        for kind, operation in (('high', 1), ('low', 0)):
            matches = [c for c in conditions if cmds.getAttr(c + '.operation') == operation
                       and c.startswith(network + '_' + kind)]
            if len(matches) > 1:
                raise ValueError('Ambiguous owned detail conditions.')
            condition = matches[0] if matches else cmds.createNode('condition', name=network + '_' + kind)
            cmds.setAttr(condition + '.operation', operation)
            cmds.setAttr(condition + '.secondTerm', 0)
            cmds.setAttr(condition + '.colorIfTrueR', 1)
            cmds.setAttr(condition + '.colorIfFalseR', 0)
            cmds.connectAttr(root + '.detailMode', condition + '.firstTerm', force=True)
            for mesh in record[kind]:
                cmds.connectAttr(condition + '.outColorR', mesh + '.visibility', force=True)
            if kind == 'high':
                for setting in record['wrinkle_settings']:
                    plug = setting + '.Envelope'
                    existing = cmds.connectionInfo(plug, sourceFromDestination=True).split('.')[0]
                    valid = (existing and cmds.nodeType(existing) == 'multiplyDivide'
                             and cmds.connectionInfo(existing + '.input2X', sourceFromDestination=True) == condition + '.outColorR')
                    if existing and not valid:
                        raise ValueError('Wrinkle Envelope has an unrelated driver: ' + plug)
                    multiply = existing if valid else cmds.createNode('multiplyDivide', name=network + '_wrinkleEnvelope')
                    cmds.setAttr(multiply + '.input1X', record['original_values'][plug])
                    cmds.connectAttr(condition + '.outColorR', multiply + '.input2X', force=True)
                    cmds.connectAttr(multiply + '.outputX', plug, force=True)
        record = dict(record, root=root)
        cmds.setAttr(network + '.detailData', json.dumps(record), type='string')
        if record.get('compute_bypass'):
            install_compute_bypass(root)


@poses.undoable
def install_compute_bypass(root):
    """Route output at workflow boundaries, leaving unused detail unconsumed."""
    from maya_tools.scripts.tools import bifrost_wrinkles
    root = cmds.ls(root, long=True)[0]
    data = next((r for r in export_detail_modes() if cmds.ls(r['root'], long=True) == [root]), None)
    if not data:
        raise ValueError('Create detail modes before installing compute bypass.')
    network = next(n for n in cmds.listConnections(root + '.message', source=False, destination=True, type='network') or []
                   if cmds.attributeQuery('detailData', node=n, exists=True))
    owned, routes = [], []
    for record in bifrost_wrinkles.export_setups():
        settings = record['prefix'] + '_Settings'
        if settings not in data['wrinkle_settings']:
            continue
        graph, converter = record['prefix'] + 'GraphShape', record['prefix'] + '_ToMaya'
        source_shape = bifrost_wrinkles._mesh_fn(record['source'])[0]
        output_shape = source_shape if record.get('in_place') else bifrost_wrinkles._mesh_fn(record['prefix'] + '_Face')[0]
        primary = cmds.connectionInfo(graph + '.AnimatedFace', sourceFromDestination=True)
        if not primary:
            raise ValueError('Primary wrinkle input is missing.')
        routes.append({'destination': output_shape + '.inMesh', 'primary': primary,
                       'detail': converter + '.mayaMesh[0]'})
        owned.extend([graph, converter])
    if not owned:
        raise ValueError('The detail record has no owned wrinkle setup.')
    data['compute_bypass'] = {'nodes': owned, 'routes': routes,
                              'mechanism': 'primary mesh routing at workflow boundaries'}
    cmds.setAttr(network + '.detailData', json.dumps(data), type='string')
    cmds.setAttr(root + '.detailMode', keyable=False, channelBox=False)
    set_detail_mode(root, cmds.getAttr(root + '.detailMode'))
    return data['compute_bypass']


@poses.undoable
def set_detail_mode(root, mode):
    """Explicit workflow transaction; topology and frame evaluation stay stable."""
    if mode not in (0, 1, 2):
        raise ValueError('Choose Animation, Review or Export.')
    data = next((r for r in export_detail_modes() if cmds.ls(r['root'], long=True) == cmds.ls(root, long=True)), None)
    if not data:
        raise ValueError('Create detail modes first.')
    owned = data.get('compute_bypass', {}).get('nodes', [])
    routes = data.get('compute_bypass', {}).get('routes', [])
    if any(not cmds.objExists(n) for n in owned):
        raise ValueError('Owned compute bypass nodes are missing.')
    for route in routes:
        incoming = cmds.connectionInfo(route['destination'], sourceFromDestination=True)
        if incoming not in (route['primary'], route['detail']):
            raise ValueError('Detail output has an unrelated driver: ' + route['destination'])
    if mode == 2:
        cmds.evaluator(name='cache', enable=False)
    cmds.setAttr(root + '.detailMode', mode)
    for route in routes:
        cmds.connectAttr(route['primary'] if mode == 0 else route['detail'], route['destination'], force=True)
    return {'mode': mode, 'unconsumed_detail': list(owned) if mode == 0 else []}

def benchmark(root,output,cases=None,repeats=3,profile=True):
    if cmds.about(batch=True):raise ValueError('Viewport interaction benchmarks require interactive Maya.')
    output=Path(output);profile_path=output.with_suffix('.mayaProfile')
    if output.exists() or profile_path.exists() or repeats<1:raise ValueError('Choose new benchmark files and positive repeats.')
    if not cmds.attributeQuery('detailMode',node=root,exists=True):raise ValueError('Create the native detail modes first.')
    resolved,missing,skipped=qa.resolve_cases(root,cases)
    if missing:raise ValueError('Missing benchmark controls: '+', '.join(missing))
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']};initial[root+'.detailMode']=cmds.getAttr(root+'.detailMode')
    report={'version':2,'maya':cmds.about(version=True),'root':root,'enabled_evaluators':cmds.evaluator(query=True,enable=True) or [],
            'measurement':'Changed control channels plus forced viewport refresh wall time. Neutral setup is warmed; includes redraw submission, not isolated GPU execution or playback FPS.',
            'cached_playback':False,'skipped_channels':skipped,'variants':{},
            'evaluation_state':'Parallel CPU; native GPU diagnostics belong to separate temporal captures'}
    if profile and cmds.profiler(query=True,sampling=True):raise ValueError('Stop the existing Profiler recording before starting a new capture.')
    output.parent.mkdir(parents=True,exist_ok=True)
    started=False
    try:
        from maya_tools.scripts.tools import rig_benchmark
        with rig_benchmark.evaluation_session(),poses._temporary_values(initial):
            cmds.evaluator(name='deformer',enable=False)
            cmds.evaluationManager(mode='parallel')
            for detail,name in enumerate(('animation','review','export')):
                set_detail_mode(root,detail);samples=[];previous={};updates=0
                for repeat in range(repeats+1):
                    for case in resolved:
                        start=time.perf_counter()
                        for plug,value in case['values'].items():
                            if previous.get(plug) != value:
                                cmds.setAttr(plug,value); previous[plug]=value
                                if repeat:updates+=1
                        cmds.refresh(force=True)
                        if repeat:samples.append((time.perf_counter()-start)*1000)
                report['variants'][name]={'mean_ms':statistics.mean(samples), 'median_ms':statistics.median(samples),
                    'p95_ms':sorted(samples)[max(0,math.ceil(.95*len(samples))-1)],
                    'max_ms':max(samples), 'cv_percent':statistics.pstdev(samples)/statistics.mean(samples)*100,
                    'samples':len(samples), 'changed_channel_updates':updates}
            if profile:
                cmds.profiler(sampling=True);started=True
                for detail in range(3):
                    set_detail_mode(root, detail)
                    for case in resolved:
                        for plug,value in case['values'].items():cmds.setAttr(plug,value)
                        cmds.refresh(force=True)
    finally:
        if started:cmds.profiler(sampling=False)
    if profile:
        cmds.profiler(output=str(profile_path));report['profiler_capture']=str(profile_path)
    with output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    return report
