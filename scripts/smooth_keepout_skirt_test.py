"""Validate smoother weights against the user's current pose and IK test poses.

This edits only an isolated copy. Apply the accepted profile to the live Maya
scene afterwards so the user's current pose, selection and edits are retained.
"""
import json
import os
from pathlib import Path
import sys
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DIRECTORY=ROOT/'maya_tools/assets/KeepOutSkirt/experiments'


def main():
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya_tools.scripts.tools import muscle_keepout_skirt as tool
    snapshot=DIRECTORY/'Before_SmoothWeights_working.ma'
    cmds.file(str(snapshot),open=True,force=True)
    data=json.loads(cmds.getAttr('KOskirt_RIG_GRP.demoData'))
    working_pose={side:cmds.xform(data['legs'][side]['ik'],q=True,ws=True,m=True) for side in ('L','R')}
    for frame,pose in ((1,working_pose),(25,{'L':(8,38,32),'R':(-8,8,0)}),
                       (49,{'L':(8,8,0),'R':(-8,38,32)}),
                       (73,{'L':(8,36,32),'R':(-8,36,32)}),
                       (97,{'L':(26,13,0),'R':(-26,13,0)})):
        for side,target in pose.items():
            ctl=data['legs'][side]['ik']
            if len(target)==16: cmds.xform(ctl,ws=True,m=target)
            else: cmds.xform(ctl,ws=True,t=target)
            cmds.setKeyframe(ctl,at=['translateX','translateY','translateZ'],t=frame)
    cmds.currentTime(1)
    report={}
    original_margin=cmds.getAttr(data['waist']+'.collisionMargin')
    for strength,margin in ((.85,original_margin+.7),(.85,original_margin+1.0),(.65,original_margin+.7)):
        cmds.setAttr(data['waist']+'.collisionMargin',min(4.0,margin))
        profile=tool.smooth_skin_weights(data,strength=strength)
        tested=tool.validate_demo(data,frames=[1,25,49,73,97],repeats=1)
        tested.pop('scheduling_graph',None)
        # Blended weights may use the cushion; contact is tested against full
        # body triangles instead of requiring every vertex to stay outside it.
        geometric_pass=(tested['surface_contact']['penetrating_triangle_capsule_pairs']==0
                        and all(v.get('dg_max_error',0)<1e-5 and v['random_access_max_error']<1e-5
                                and not v.get('fallback',False) for v in tested['modes'].values())
                        and tested['disabled_rest_error_cm']<1e-5 and not tested['cycle_clusters']
                        and not tested['dg_cycle_plugs'] and profile['normalization_error']<1e-10
                        and profile['pinned_waist_vertices']==data['columns'])
        tested['passed']=geometric_pass
        tested['weight_profile']=profile
        tested['original_collision_margin_cm']=original_margin
        tested['collision_margin_cm']=cmds.getAttr(data['waist']+'.collisionMargin')
        print('SMOOTH_TRIAL='+json.dumps({'profile':profile,'surface':tested['surface_contact'],
                                          'passed':geometric_pass}),flush=True)
        report=tested
        if geometric_pass: break
    curves=cmds.ls(type='animCurve') or []
    if curves: cmds.delete(curves)
    for side,matrix in working_pose.items(): cmds.xform(data['legs'][side]['ik'],ws=True,m=matrix)
    cmds.evaluationManager(mode='parallel');cmds.currentTime(1)
    report['tested_snapshot']=str(snapshot)
    (DIRECTORY/'smooth_weights_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    maya.standalone.uninitialize()
    if not report['passed']: raise SystemExit(2)


if __name__=='__main__': main()
