"""Continuous facial transitions, landmark separation and reversibility."""
import json, math
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_validation as qa, pose_blendshapes as poses

FACIAL_SEQUENCES = [
    ('jaw_smile', {'C_jaw_CTL.rotateX':30, 'L_lipCorner_CTL.translateX':5, 'R_lipCorner_CTL.translateX':5}),
    ('sticky_jaw', {'C_jaw_CTL.rotateX':30, 'C_jaw_CTL.stickyLips':1}),
    ('sticky_smile', {'C_jaw_CTL.stickyLips':1, 'L_lipCorner_CTL.translateX':5, 'R_lipCorner_CTL.translateX':5}),
    ('lip_u', {'L_lipCorner_CTL.translateY':3, 'R_lipCorner_CTL.translateY':3}),
]

def lip_pairs(root):
    result=[]
    for upper in cmds.listRelatives(root,allDescendents=True,fullPath=True,type='joint') or []:
        if 'upperLip' in upper and upper.endswith('NonRot_JNT'):
            lower=upper.replace('upperLip','lowerLip')
            if not cmds.objExists(lower):
                leaf=lower.rsplit('|',1)[-1]
                matches=[n for n in cmds.ls(leaf,long=True) or [] if n.startswith(cmds.ls(root,long=True)[0]+'|')]
                lower=matches[0] if len(matches)==1 else None
            if lower:result.append((upper,lower))
    return sorted(result)

def _point(node):
    return om.MVector(*cmds.xform(node,query=True,worldSpace=True,translation=True))

def run(root, meshes, output, pairs=None, sequences=None, samples=21, contact_tolerance=.001):
    output=Path(output)
    if output.exists() or samples<3 or contact_tolerance<=0:
        raise ValueError('Use a new output, at least three samples and positive contact tolerance.')
    pairs=lip_pairs(root) if pairs is None else list(pairs)
    if not pairs:raise ValueError('No paired lip landmarks were found. Provide explicit pairs.')
    cases,missing,skipped=qa.resolve_cases(root,sequences or FACIAL_SEQUENCES)
    if missing:raise ValueError('Missing facial channels: '+', '.join(missing))
    initial={p:cmds.getAttr(p) for p in cases[0]['values']}
    report={'version':1,'units':cmds.currentUnit(q=True,linear=True),'landmark_pairs':pairs,
            'measurement':'Rig landmark contact, not a complete mesh collision test. Continuous geometry samples exclude viewport drawing.',
            'contact_tolerance':contact_tolerance,'skipped_channels':skipped,'sequences':[]}
    neutral,_=qa._neutral_values(root)
    with qa._session(),poses._temporary_values(initial):
        for plug,value in neutral.items():cmds.setAttr(plug,value)
        axes=[]
        for upper,lower in pairs:
            delta=_point(upper)-_point(lower)
            axes.append(delta.normal() if delta.length()>1e-8 else om.MVector(0,1,0))
        for case in cases:
            forward={};previous=None;previous_step=None;records=[];max_return=0
            for k in list(range(samples))+list(range(samples-2,-1,-1)):
                t=k/(samples-1)
                for plug,end in case['values'].items():
                    start=neutral.get(plug,end);cmds.setAttr(plug,start+(end-start)*t)
                geometry={m:qa.mesh_data(m)['points'] for m in meshes}
                gaps=[(_point(a)-_point(b)).length() for a,b in pairs]
                signed=[(_point(a)-_point(b))*axis for (a,b),axis in zip(pairs,axes)]
                step=None;change=None
                if previous is not None:
                    displacements=[om.MVector(*p)-om.MVector(*q) for m in meshes for p,q in zip(geometry[m],previous[m])]
                    step=max((v.length() for v in displacements),default=0)
                    if previous_step is not None:change=max((a-b).length() for a,b in zip(displacements,previous_step))
                    previous_step=displacements
                if k in forward:
                    max_return=max(max_return,max((om.MVector(*p)-om.MVector(*q)).length() for m in meshes for p,q in zip(geometry[m],forward[k][m])))
                else:forward[k]=geometry
                sticky=[p for p in case['values'] if p.endswith('.stickyLips')]
                fully_closed=bool(sticky) and all(cmds.getAttr(p)>=1-1e-8 for p in sticky)
                records.append({'t':t,'direction':'forward' if len(records)<samples else 'reverse',
                    'max_gap':max(gaps),'min_signed_separation':min(signed),
                    'closed_gap_exceeds_tolerance':fully_closed and max(gaps)>contact_tolerance,
                    'max_vertex_step':step,'max_step_change':change})
                previous=geometry
            report['sequences'].append({'name':case['name'],'channels':case['values'],'samples':records,
                'max_reverse_difference':max_return,'closed_contact_pass':not any(r['closed_gap_exceeds_tolerance'] for r in records)})
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    return report
