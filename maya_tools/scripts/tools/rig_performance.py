"""Native detail switching and measured interactive viewport updates."""
import json,time,statistics
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
        else:
            conditions=cmds.listConnections(record['root']+'.detailMode',source=False,destination=True,type='condition') or []
            for condition in conditions:
                kind='high' if cmds.getAttr(condition+'.operation')==1 else 'low'
                for mesh in record[kind]:
                    cmds.connectAttr(condition+'.outColorR',mesh+'.visibility',force=True)
                if kind=='high':
                    for setting in record['wrinkle_settings']:
                        multiply=cmds.createNode('multiplyDivide',name='detailWrinkleEnvelope')
                        cmds.setAttr(multiply+'.input1X',record['original_values'][setting+'.Envelope'])
                        cmds.connectAttr(condition+'.outColorR',multiply+'.input2X')
                        cmds.connectAttr(multiply+'.outputX',setting+'.Envelope',force=True)

def benchmark(root,output,cases=None,repeats=2,profile=True):
    if cmds.about(batch=True):raise ValueError('Viewport interaction benchmarks require interactive Maya.')
    output=Path(output);profile_path=output.with_suffix('.mayaProfile')
    if output.exists() or profile_path.exists() or repeats<1:raise ValueError('Choose new benchmark files and positive repeats.')
    if not cmds.attributeQuery('detailMode',node=root,exists=True):raise ValueError('Create the native detail modes first.')
    resolved,missing,skipped=qa.resolve_cases(root,cases)
    if missing:raise ValueError('Missing benchmark controls: '+', '.join(missing))
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']};initial[root+'.detailMode']=cmds.getAttr(root+'.detailMode')
    report={'version':1,'maya':cmds.about(version=True),'root':root,'enabled_evaluators':cmds.evaluator(query=True,enable=True) or [],
            'measurement':'Control changes plus forced viewport refresh wall time. Includes redraw submission, not isolated GPU execution or playback FPS.',
            'cached_playback':False,'skipped_channels':skipped,'variants':{},'gpu':qa.audit_deformers([m for r in export_detail_modes() if r['root']==cmds.ls(root,long=True)[0] for m in r['high']+r['low']])}
    if profile and cmds.profiler(query=True,sampling=True):raise ValueError('Stop the existing Profiler recording before starting a new capture.')
    output.parent.mkdir(parents=True,exist_ok=True)
    started=False
    try:
        with qa._session(),poses._temporary_values(initial):
            if profile:cmds.profiler(sampling=True);started=True
            for detail,name in enumerate(('animation','review','export')):
                cmds.setAttr(root+'.detailMode',detail);samples=[]
                for repeat in range(repeats+1):
                    for case in resolved:
                        start=time.perf_counter()
                        for plug,value in case['values'].items():cmds.setAttr(plug,value)
                        cmds.refresh(force=True)
                        if repeat:samples.append((time.perf_counter()-start)*1000)
                report['variants'][name]={'mean_ms':statistics.mean(samples),'p95_ms':sorted(samples)[min(len(samples)-1,int(.95*len(samples)))],'samples':len(samples)}
    finally:
        if started:cmds.profiler(sampling=False)
    if profile:
        cmds.profiler(output=str(profile_path));report['profiler_capture']=str(profile_path)
    with output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    return report
