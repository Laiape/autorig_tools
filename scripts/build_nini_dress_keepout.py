"""Build/validate a new Nini version using sparse hierarchical dress chains."""
import json
import os
from pathlib import Path
import sys
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DIRECTORY=ROOT/'maya_tools/assets/Nini/experiments/dress_keepout'
SOURCE=ROOT/'maya_tools/assets/Nini/review/loop_rigger/Nini_ManualLoops_v001.ma'


def main():
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya_tools.scripts.tools import dress_keepout_chains as tool
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    cmds.file(str(SOURCE),open=True,force=True)
    baseline_cycles=cmds.cycleCheck(all=True,list=True) or []
    baseline_body=tool.mesh_points('c_body_GEO')
    baseline_cloth=tool.mesh_points('c_tunic_GEO')
    data=tool.build()
    version=1
    while (DIRECTORY/'Nini_dress_chains_v{:03d}.ma'.format(version)).exists(): version+=1
    scene=DIRECTORY/'Nini_dress_chains_v{:03d}.ma'.format(version)
    cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii')
    print('DRESS_CHAINS_BUILT='+json.dumps({'chains':data['chain_count'],'joints':len(data['joints']),
                                           'keepouts':len(data['keepouts']),'garments':[{k:v for k,v in g.items() if k not in ('region','alpha')} for g in data['garments']]}),flush=True)
    rest={side:cmds.xform(side+'_ankleIk_CTL',q=True,ws=True,t=True) for side in ('L','R')}
    frames=[1,25,49,73,97]
    poses=[((0,0,0),(0,0,0)),((0,15,18),(0,0,0)),((0,0,0),(0,15,18)),
           ((0,14,15),(0,14,15)),((14,4,0),(-14,4,0))]
    for frame,pose in zip(frames,poses):
        for side,delta in zip(('L','R'),pose):
            ctl=side+'_ankleIk_CTL'
            cmds.xform(ctl,ws=True,t=[a+b for a,b in zip(rest[side],delta)])
            cmds.setKeyframe(ctl,at=['translateX','translateY','translateZ'],t=frame)
    report={'source':str(SOURCE),'scene':str(scene),'chains':data['chain_count'],
            'joints_per_chain':data['levels'],'dress_joint_count':len(data['joints']),
            'cloth_vertex_count':data['garments'][0]['vertex_count'],'skin':[{k:v for k,v in g.items() if k not in ('region','alpha')} for g in data['garments']],
            'baseline_cycle_plugs':baseline_cycles,'modes':{}}
    snapshots={}
    for mode in ('off','serial','parallel'):
        cmds.evaluationManager(mode=mode)
        snapshots[mode]={};contacts={}
        for frame in frames:
            cmds.currentTime(frame)
            snapshots[mode][frame]=tool.mesh_points('c_tunic_GEO')
            if mode=='off':
                contacts[str(frame)]={target:tool.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],target,closed=target=='c_body_GEO',surface_samples=target=='c_body_GEO')
                                      for target in ('c_body_GEO','c_pants_GEO')}
        info={'actual':cmds.evaluationManager(q=True,mode=True)}
        if mode!='off':
            info['dg_max_error']=max(abs(a-b) for frame in frames for p,q in zip(snapshots['off'][frame],snapshots[mode][frame]) for a,b in zip(p,q))
            info['fallback']=cmds.evaluationManager(q=True,fallbackTriggered=True)
        if contacts: report['contacts']=contacts
        report['modes'][mode]=info
        print('NINI_MODE_CHECKED='+mode,flush=True)
    report['new_cycle_plugs']=sorted(set(cmds.cycleCheck(all=True,list=True) or [])-set(baseline_cycles))
    graph=json.loads(cmds.dbpeek(op='graph',evaluationGraph=True,allObjects=True,argument=['scheduling','verbose']))
    report['scheduling_node_counts']={kind:len(nodes) for kind,nodes in graph['scheduling']['scheduling'].items()}
    report['passed']=(not report['new_cycle_plugs']
                       and all(info.get('dg_max_error',0)<1e-5 and not info.get('fallback',False) for info in report['modes'].values())
                       and all(not values['c_body_GEO']['penetrating_vertices'] and not values['c_body_GEO']['uncertain_vertices'] for values in report['contacts'].values())
                       and all(g['upper_weight_error']<1e-10 and g['normalization_error']<1e-6 for g in data['garments']))
    # Reload the pre-validation save: preserve source animation and neutral pose.
    cmds.file(str(scene),open=True,force=True)
    cmds.evaluationManager(mode='parallel')
    report['untouched_body_error']=max(abs(a-b) for p,q in zip(baseline_body,tool.mesh_points('c_body_GEO')) for a,b in zip(p,q))
    final_cloth=tool.mesh_points('c_tunic_GEO')
    report['neutral_cloth_error_cm']=max(sum((a-b)**2 for a,b in zip(p,q))**.5
                                          for p,q in zip(baseline_cloth,final_cloth))
    report['untouched_upper_cloth_error']=max(abs(a-b) for i,alpha in enumerate(data['garments'][0]['alpha']) if alpha==0 for a,b in zip(baseline_cloth[i],final_cloth[i]))
    report['chain_hierarchy_valid']=all(cmds.listRelatives(chain[level],parent=True)[0]==chain[level-1] for chain in data['chains'] for level in range(1,len(chain)))
    report['passed']=(report['passed'] and report['untouched_body_error']<1e-5
                       and report['untouched_upper_cloth_error']<1e-5
                       and report['neutral_cloth_error_cm']<.005 and report['chain_hierarchy_valid'])
    cmds.select(data['settings']);cmds.file(save=True,type='mayaAscii')
    (DIRECTORY/'nini_dress_report_v{:03d}.json'.format(version)).write_text(json.dumps(report,indent=2),encoding='utf-8')
    brief={k:v for k,v in report.items() if k not in ('contacts','baseline_cycle_plugs')}
    brief['contact_summary']={frame:{target:{'minimum':info['minimum_signed_clearance_cm'],'inside':len(info['penetrating_vertices'])}
                                    for target,info in values.items()} for frame,values in report['contacts'].items()}
    print('NINI_DRESS_RESULT='+json.dumps(brief),flush=True)
    maya.standalone.uninitialize()
    if not report['passed']: raise SystemExit(2)


if __name__=='__main__': main()
