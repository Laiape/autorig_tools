"""Portable semantic pose banks and sampled forward/reverse transition checks."""
import copy
import math
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_roles as roles, rig_validation as qa, pose_blendshapes as poses


def channel(role, attribute, value, side='C', module=None, index=0, kind='control'):
    return dict(role=role, attribute=attribute, value=value, side=side, module=module, index=index, kind=kind)


def preset(name):
    cases = [{'name': 'neutral', 'channels': []}]
    if name == 'body':
        for side in ('L', 'R'):
            cases += [dict(name=side + '_arm_raise', channels=[channel('arm.settings', 'Ik_Fk', 1, side, 'arm'), channel('arm.upper.fk', 'rotateZ', 90, side, 'arm')]),
                      dict(name=side + '_leg_bend', channels=[channel('leg.settings', 'Ik_Fk', 1, side, 'leg'), channel('leg.upper.fk', 'rotateZ', 60, side, 'leg'),
                                                            channel('leg.lower.fk', 'rotateZ', 90, side, 'leg')])]
    elif name == 'face':
        cases += [dict(name='jaw_open', channels=[channel('face.jaw', 'rotateX', 30, module='face')]),
                  dict(name='smile', channels=[channel('face.lip.corner', 'translateX', 2.5, s, 'face') for s in ('L', 'R')]),
                  dict(name='blink', channels=[channel('face.eye', 'Upper_Blink', 1, s, 'face') for s in ('L', 'R')])]
    elif name == 'hands':
        for side in ('L', 'R'):
            cases += [dict(name=side + '_digit_%d' % i, channels=[channel('hand.digit.fk', 'rotateZ', 60, side, 'hand', i)]) for i in range(5)]
    elif name != 'custom':
        raise ValueError('Choose body, face, hands or custom.')
    return {'format': 'autorig-validation-profile', 'version': 1, 'name': name,
            'comparison_tolerance': 1e-4, 'cases': cases, 'transitions': []}


def validate(profile):
    if profile.get('format') != 'autorig-validation-profile' or profile.get('version') != 1:
        raise ValueError('Unsupported rig validation profile.')
    tolerance = profile.get('comparison_tolerance', 1e-4)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Comparison tolerance must be finite and nonnegative.')
    names = set()
    for case in profile['cases']:
        name = case['name']
        if not name or name in names or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
            raise ValueError('Use unique ASCII pose names.')
        names.add(name)
        seen = set()
        for item in case['channels']:
            roles._validate({**item, 'module': item.get('module') or 'custom'})
            if not math.isfinite(item['value']) or not item['attribute'].replace('_', '').isalnum():
                raise ValueError('Use finite values and simple attribute names.')
            identity = (item['role'], item['side'], item.get('module'), item['index'], item['kind'], item['attribute'])
            if identity in seen:
                raise ValueError('Duplicate channel in pose: ' + name)
            seen.add(identity)
    for t in profile.get('transitions', []):
        if t['start'] not in names or t['end'] not in names or type(t.get('samples', 21)) is not int or t.get('samples', 21) < 3:
            raise ValueError('Transition needs existing pose names and at least three samples.')
        for field in ('max_step', 'max_step_change', 'reverse_tolerance'):
            value = t.get(field, 1e-4 if field == 'reverse_tolerance' else None)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError('Transition limits must be finite and nonnegative.')
    for check in profile.get('checks',[]):
        if check.get('type') not in ('distance','matrix_match','channel_range'):
            raise ValueError('Checks support distance, matrix_match and channel_range.')
        if any(name not in names for name in check.get('poses',[])):
            raise ValueError('A check references an unknown pose.')
        for field in ('min','max','position_tolerance','angle_tolerance','scale_tolerance'):
            if field in check and not math.isfinite(check[field]):raise ValueError('Check bounds must be finite.')
        if check.get('min',-math.inf)>check.get('max',math.inf):raise ValueError('Minimum check bound exceeds maximum.')
    return profile


def _reference(root,spec):
    return roles.resolve(root,spec.get('role'),spec.get('side','C'),spec.get('module'),spec.get('index',0),spec.get('kind','control'),spec.get('binding'))


def checks(root,profile,pose_name):
    """Read-only assertions allow module-specific IK/FK, space and landmark tests."""
    result=[]
    for spec in profile.get('checks',[]):
        if spec.get('poses') and pose_name not in spec['poses']:continue
        item={'name':spec.get('name',spec['type']),'type':spec['type']}
        try:
            a=_reference(root,spec['a'])
            if spec['type']=='channel_range':
                value=cmds.getAttr(a+'.'+spec['attribute'])
                item.update(value=value,**{'pass':isinstance(value,(int,float)) and math.isfinite(value) and spec.get('min',-math.inf)<=value<=spec.get('max',math.inf)})
            else:
                b=_reference(root,spec['b'])
                ma=om.MMatrix(cmds.xform(a,q=True,worldSpace=True,matrix=True))
                mb=om.MMatrix(cmds.xform(b,q=True,worldSpace=True,matrix=True))
                ta,tb=om.MTransformationMatrix(ma),om.MTransformationMatrix(mb)
                position=(ta.translation(om.MSpace.kWorld)-tb.translation(om.MSpace.kWorld)).length()
                if spec['type']=='distance':
                    item.update(distance=position,**{'pass':spec.get('min',0)<=position<=spec.get('max',math.inf)})
                else:
                    qa_,qb_=ta.rotation(asQuaternion=True),tb.rotation(asQuaternion=True)
                    dot=abs(sum(x*y for x,y in zip((qa_.x,qa_.y,qa_.z,qa_.w),(qb_.x,qb_.y,qb_.z,qb_.w))))
                    angle=math.degrees(2*math.acos(min(1,max(0,dot))))
                    scale=max(abs(x-y) for x,y in zip(ta.scale(om.MSpace.kWorld),tb.scale(om.MSpace.kWorld)))
                    item.update(position_difference=position,angle_difference_degrees=angle,scale_difference=scale,
                        **{'pass':position<=spec.get('position_tolerance',1e-4) and angle<=spec.get('angle_tolerance',.001) and scale<=spec.get('scale_tolerance',1e-5)})
        except (ValueError,RuntimeError) as exc:item.update(error=str(exc),**{'pass':False})
        result.append(item)
    return result


def resolve_cases(root, profile, sides=('L', 'R')):
    validate(profile)
    neutral, skipped = qa._neutral_values(root)
    resolved, missing = [], []
    bound = {b['node']: b['key'] for b in roles.bindings(root)}
    for case in profile['cases']:
        values, omitted = dict(neutral), []
        for item in case['channels']:
            if item['side'] in ('L', 'R') and item['side'] not in sides:
                continue
            try:
                node = roles.resolve(root, item['role'], item['side'], item.get('module'), item['index'], item['kind'])
                plug = node + '.' + item['attribute']
                if plug not in neutral:
                    raise ValueError('Channel is absent, locked or driven.')
                values[plug] = item['value']
            except ValueError as exc:
                omitted.append('%s.%s: %s' % (item['role'], item['attribute'], exc))
        definition = {bound.get(p.rsplit('.', 1)[0], p.rsplit('.', 1)[0]) + '.' + p.rsplit('.', 1)[1]: v for p,v in values.items()}
        missing.extend(omitted)
        # An incomplete stress pose never masquerades as a valid test.
        resolved.append(dict(name=case['name'], values=values, missing=omitted, active=not omitted, definition=definition))
    return resolved, sorted(set(missing)), skipped


def transitions(root, meshes, profile, sides=('L', 'R')):
    resolved, _, _ = resolve_cases(root, profile, sides)
    cases = {c['name']: c for c in resolved}
    result = []
    for spec in profile.get('transitions', []):
        start, end = cases[spec['start']], cases[spec['end']]
        item = {'start': start['name'], 'end': end['name'], 'measurement': 'Sampled object-space vertex displacement; thresholds use scene linear units.'}
        if not start['active'] or not end['active']:
            result.append({**item, 'pass': False, 'status': 'missing_channels'})
            continue
        count = spec.get('samples', 21)
        initial = {p: cmds.getAttr(p) for p in start['values']}
        snapshots, steps, changes, differences, sample_checks = [], [], [], [], []
        with qa._session(), poses._temporary_values(initial):
            previous, old_displacements = None, None
            reference_topology = None
            for position, i in enumerate(list(range(count)) + list(range(count - 2, -1, -1))):
                t = i / float(count - 1)
                for p, a in start['values'].items():
                    cmds.setAttr(p, a + (end['values'][p] - a) * t)
                data = {m: qa.mesh_data(m) for m in meshes}
                from maya_tools.scripts.tools import rig_surface_contact
                contact_results=rig_surface_contact.profile_contacts(root,profile)
                assertions=checks(root,profile,'__transition__')
                sample_checks.append({'t':t,'direction':'forward' if position<count else 'reverse',
                    'checks':assertions,'contacts':[{k:v for k,v in c.items() if k!='samples'} for c in contact_results],
                    'pass':all(c['pass'] for c in contact_results+assertions)})
                topology={m:data[m]['topology'] for m in meshes}
                if reference_topology is None:reference_topology=topology
                if topology!=reference_topology:raise ValueError('Topology changed during transition.')
                flat = [point for m in meshes for point in data[m]['points']]
                if not snapshots or len(snapshots) < count:
                    snapshots.append(copy.deepcopy(data))
                else:
                    original = snapshots[i]
                    if any(data[m]['topology'] != original[m]['topology'] for m in meshes):
                        raise ValueError('Topology changed during transition.')
                    differences.append(max((math.dist(p, q) for m in meshes for p,q in zip(data[m]['points'], original[m]['points'])), default=0))
                if previous is not None:
                    if len(flat) != len(previous):
                        raise ValueError('Topology changed during transition.')
                    displacement = [[a-b for a,b in zip(p,q)] for p,q in zip(flat,previous)]
                    steps.append(max((math.sqrt(sum(v*v for v in d)) for d in displacement), default=0))
                    # Do not count intentional direction reversal as a discontinuity.
                    if old_displacements is not None and position < count:
                        changes.append(max((math.dist(a,b) for a,b in zip(displacement,old_displacements)), default=0))
                    old_displacements = displacement
                previous = flat
        item.update(status='measured', max_step=max(steps, default=0), max_step_change=max(changes, default=0),
                    max_reverse_difference=max(differences, default=0), samples=2*count-1, sample_checks=sample_checks)
        item['pass'] = item['max_reverse_difference'] <= spec.get('reverse_tolerance', 1e-4) and all(s['pass'] for s in sample_checks)
        for metric in ('max_step', 'max_step_change'):
            if spec.get(metric) is not None:
                item['pass'] = item['pass'] and item[metric] <= spec[metric]
        result.append(item)
    return result
