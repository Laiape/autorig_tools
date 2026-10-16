"""Editable, stateless contact/lift upgrade for a calibrated dress module.

Authoring and audits run in Python. Saved evaluation uses native DG nodes and
MayaMuscle KeepOut only. Skin weights, bind matrices and existing joints are
never replaced. The old contact branch remains available through solverBlend.
Supported input: a closed skirt with positive uniform character scale.
"""
import ast
import json
import math
from pathlib import Path

from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import dress_keepout_chains as dress
from maya_tools.scripts.tools import muscle_keepout_skirt as core

VERSION = 1
PARAMETERS = {
    'solverBlend': (1.0, 0.0, 1.0),
    'autoLift': (1.0, 0.0, 1.0),
    'maxLift': (24.0, 0.0, 100.0),
    'lengthStiffness': (1.0, 0.0, 1.0),
    'bendStiffness': (1.0, 0.0, 1.0),
    'contactPadding': (0.8, 0.0, 3.0),
    'surfaceContact': (1.0, 0.0, 1.0),
    'surfaceMargin': (0.1, 0.0, 1.0),
    'spreadAround': (0.8, 0.0, 1.0),
    'spreadDown': (0.6, 0.0, 1.0),
}


def _data(module=None):
    """Resolve saved legacy handles under an explicitly selected namespace."""
    if module is None:
        selected = cmds.ls(selection=True, long=True) or []
        matches = []
        for node in selected:
            if cmds.attributeQuery('skirtSource', node=node, exists=True):
                matches += cmds.listConnections(node+'.skirtSource', source=True,
                                                destination=False) or []
            if cmds.attributeQuery('dressRigData', node=node, exists=True):
                matches.append(node)
        if not matches:
            matches = cmds.ls('*.dressRigData', objectsOnly=True) or []
        matches = sorted(set(matches))
        if len(matches) != 1:
            raise ValueError('Select one dress module or one of its skirt controls.')
        module = matches[0]
    if not cmds.objExists(module+'.dressRigData'):
        raise ValueError('Missing dressRigData on '+module)
    data = _resolve_handles(json.loads(cmds.getAttr(module+'.dressRigData')),module)
    data['module'] = module
    return data


def _resolve_handles(value, module):
    namespace = module.rsplit('|',1)[-1].rsplit(':',1)[0]+':' if ':' in module else ''
    bindings = {}
    if cmds.objExists(module+'.skirtBindingNames'):
        for name,index in json.loads(cmds.getAttr(module+'.skirtBindingNames')).items():
            connected = cmds.listConnections(module+'.skirtBindings[{}]'.format(index),
                                              source=True,destination=False) or []
            if connected:
                bindings[name] = connected[0]

    def resolve(item):
        if isinstance(item,dict):
            return {key:resolve(v) for key,v in item.items()}
        if isinstance(item,list):
            return [resolve(v) for v in item]
        if isinstance(item,str):
            node,separator,attribute = item.partition('.')
            if node in bindings:
                return bindings[node]+(separator+attribute if separator else '')
            if namespace and (cmds.objExists(namespace+item) or cmds.objExists(namespace+item+'Rest_GRP')):
                return namespace+item
        return item
    return resolve(value)


def _info(data):
    return _resolve_handles(json.loads(cmds.getAttr(data['module']+'.skirtContactData')),data['module'])


def _bind_handles(module, data, info):
    handles = set()

    def visit(value):
        if isinstance(value,dict):
            for item in value.values(): visit(item)
        elif isinstance(value,list):
            for item in value: visit(item)
        elif isinstance(value,str) and cmds.objExists(value.partition('.')[0]):
            handles.add(value.partition('.')[0])
    visit(data);visit(info)
    cmds.addAttr(module,longName='skirtBindings',attributeType='message',multi=True)
    names = {}
    for i,node in enumerate(sorted(handles)):
        cmds.connectAttr(node+'.message',module+'.skirtBindings[{}]'.format(i))
        names[node] = i
    cmds.addAttr(module,longName='skirtBindingNames',dataType='string')
    cmds.setAttr(module+'.skirtBindingNames',json.dumps(names),type='string')


def _put(value, plug):
    if isinstance(value, str):
        cmds.connectAttr(value, plug)
    else:
        cmds.setAttr(plug, value)


class Graph:
    """Small explicit scalar graph builder; no runtime Python evaluation."""
    def __init__(self, prefix):
        self.prefix = prefix
        self.nodes = []

    def node(self, kind, label, parent=None):
        kwargs = {'name': self.prefix+label, 'skipSelect': True}
        if parent is not None:
            kwargs['parent'] = parent
        node = cmds.createNode(kind, **kwargs)
        self.nodes.append(node)
        return node

    def add(self, label, *inputs):
        node = self.node('plusMinusAverage', label+'_PMA')
        for i, value in enumerate(inputs):
            _put(value, node+'.input1D[{}]'.format(i))
        return node+'.output1D'

    def sub(self, label, a, b):
        node = self.node('plusMinusAverage', label+'_PMA')
        cmds.setAttr(node+'.operation', 2)
        _put(a, node+'.input1D[0]'); _put(b, node+'.input1D[1]')
        return node+'.output1D'

    def mul(self, label, a, b):
        node = self.node('multDL', label+'_MDL')
        _put(a, node+'.input1'); _put(b, node+'.input2')
        return node+'.output'

    def divide(self, label, a, b):
        node = self.node('multiplyDivide', label+'_MDV')
        cmds.setAttr(node+'.operation', 2)
        _put(a, node+'.input1X'); _put(b, node+'.input2X')
        return node+'.outputX'

    def power(self, label, a, exponent):
        node = self.node('multiplyDivide', label+'_MDV')
        cmds.setAttr(node+'.operation', 3)
        _put(a, node+'.input1X'); _put(exponent, node+'.input2X')
        return node+'.outputX'

    def maximum(self, label, a, b):
        node = self.node('condition', label+'_CON')
        cmds.setAttr(node+'.operation', 2)
        _put(a, node+'.firstTerm'); _put(b, node+'.secondTerm')
        _put(a, node+'.colorIfTrueR'); _put(b, node+'.colorIfFalseR')
        return node+'.outColorR'

    def clamp(self, label, value, low, high):
        node = self.node('clamp', label+'_CLP')
        _put(value, node+'.inputR'); _put(low, node+'.minR'); _put(high, node+'.maxR')
        return node+'.outputR'

    def lerp(self, label, a, b, weight):
        return self.add(label, a, self.mul(label+'Delta', self.sub(label+'Sub', b, a), weight))

    def matrix(self, label, xyz, frame=None):
        if frame is not None:
            node = self.node('fourByFourMatrix', label+'_FBF')
            for row in range(3):
                for column in range(3):
                    cmds.setAttr(node+'.in{}{}'.format(row,column), frame[row*4+column])
            for column, value in enumerate(xyz):
                _put(value, node+'.in3{}'.format(column))
            cmds.setAttr(node+'.in33', 1)
            return node+'.output'
        node = self.node('composeMatrix', label+'_CMT')
        for axis, value in zip('XYZ', xyz):
            _put(value, node+'.inputTranslate'+axis)
        return node+'.outputMatrix'

    def world(self, label, local, waist):
        node = self.node('multMatrix', label+'_MMT')
        cmds.connectAttr(local, node+'.matrixIn[0]')
        cmds.connectAttr(waist+'.worldMatrix[0]', node+'.matrixIn[1]')
        return node+'.matrixSum'


def _link(source, node, attr):
    cmds.addAttr(node, longName=attr, attributeType='message')
    cmds.connectAttr(source+'.message', node+'.'+attr)


def _rest_guard(data):
    if not data.get('rest_contacts') or not data.get('rest_orientations'):
        raise ValueError('Calibrate the original dress in its approved neutral pose first.')
    settings = data['settings']
    if not cmds.getAttr(settings+'.collisionEnable') or abs(cmds.getAttr(settings+'.collisionBlend')-1) > 1e-6:
        raise ValueError('Enable full collision before upgrading at neutral.')
    for row in data['rest_contacts']:
        raw = cmds.getAttr(row['subtract']+'.input1D[0]')
        baseline = cmds.getAttr(row['subtract']+'.input1D[1]')
        if abs(raw-baseline) > 1e-4:
            raise ValueError('The legs differ from calibrated rest. Return to neutral first.')
    matrix = om.MTransformationMatrix(om.MMatrix(cmds.getAttr(data['waist']+'.worldMatrix[0]')))
    scale = matrix.scale(om.MSpace.kWorld)
    if min(scale) <= 0 or max(scale)-min(scale) > 1e-5:
        raise ValueError('Positive uniform character scale is required.')


def _macro_controls(data, group, prefix):
    top = data['top_local']
    bottom = min(data['hems_local'])
    radius = max(math.hypot(*[p[k] for k in (0, 2)])
                 for chain in data['stations_local'] for p in chain)+4
    controls = {}
    for label, angle in (('Right', 0), ('Front', math.pi/2),
                         ('Left', math.pi), ('Back', 3*math.pi/2), ('Hem', None)):
        position = (0, bottom-3, 0) if angle is None else (
            radius*math.cos(angle), (top+bottom)/2, radius*math.sin(angle))
        offset = core._follow(prefix+label+'_GRP', position,
                              data['waist']+'.worldMatrix[0]', group)
        ctl = core._control(prefix+label+'_CTL', offset, 2.5, (.9, .65, .2))
        for attr in ('rotateX', 'rotateY', 'rotateZ', 'scaleX', 'scaleY', 'scaleZ', 'visibility'):
            cmds.setAttr(ctl+'.'+attr, lock=True, keyable=False, channelBox=False)
        _link(data['module'], ctl, 'skirtSource')
        controls[label] = ctl
    return controls


def _calibration_indicator(graph, data, settings, rows):
    valid = 1.0
    checks = [(settings+'.'+key, value) for key, value in data['rest_collision_settings'].items()]
    for i, (source, baseline) in enumerate(checks):
        difference = graph.sub('Calibration{:02d}'.format(i), source, baseline)
        square = graph.mul('CalibrationSquare{:02d}'.format(i), difference, difference)
        node = graph.node('condition', 'CalibrationValid{:02d}_CON'.format(i))
        cmds.setAttr(node+'.operation', 5)  # <=
        _put(square, node+'.firstTerm'); cmds.setAttr(node+'.secondTerm', 1e-12)
        _put(valid, node+'.colorIfTrueR'); cmds.setAttr(node+'.colorIfFalseR', 0)
        valid = node+'.outColorR'
        rows.append({'source': source, 'baseline_node': difference.split('.')[0], 'baseline': baseline})
    cmds.addAttr(settings, longName='calibrationValid', attributeType='bool', keyable=False)
    cmds.connectAttr(valid, settings+'.calibrationValid')
    cmds.setAttr(settings+'.calibrationValid', channelBox=True)


def _upgrade(module=None, auto_lift=1.0, spread_around=.8, spread_down=.6, collision_mesh=None):
    """Upgrade a neutral calibrated dress, in one undo transaction.

    Return existing data when already upgraded. Namespaces are supported.
    No mesh/skin/bind editing occurs. Use a versioned native copy for delivery.
    """
    data = _data(module)
    module, settings = data['module'], data['settings']
    if cmds.objExists(module+'.skirtContactData'):
        return _info(data)
    _rest_guard(data)
    namespace = module.rsplit('|',1)[-1].rsplit(':',1)[0]+':' if ':' in module else ''
    body = collision_mesh or namespace+'c_body_GEO'
    if not cmds.objExists(body) or body in [g['mesh'] for g in data['garments']]:
        raise ValueError('Pass an independent body collision_mesh.')
    prefix = module.rsplit('|', 1)[-1].removesuffix('Module_GRP')+'Contact_'
    if cmds.objExists(prefix+'Module_GRP'):
        raise ValueError('Contact prefix is already in use.')
    old_selection = cmds.ls(selection=True, long=True) or []
    old_dirty = cmds.file(q=True, modified=True)
    old_undo = cmds.undoInfo(q=True, state=True)
    if not old_undo:
        cmds.undoInfo(stateWithoutFlush=True)
    from maya_tools.scripts.utils import scene_evaluation
    previous_evaluation = scene_evaluation.capture()
    refresh_suspended = cmds.refresh(query=True,suspend=True)
    cmds.undoInfo(openChunk=True, chunkName='Upgrade Skirt Contact')
    failure = False
    try:
        scene_evaluation.suspend_for_build()
        cmds.refresh(suspend=True)
        initial_nodes = set(cmds.ls(long=True))
        group = core._node('transform', prefix+'Module_GRP', module)
        control_parent = cmds.listRelatives(cmds.listRelatives(settings, parent=True)[0], parent=True)[0]
        controls_group = core._node('transform', prefix+'Controllers_GRP', control_parent)
        controls = _macro_controls(data, controls_group, prefix)
        _link(module, settings, 'skirtSource')
        for name, (value, low, high) in PARAMETERS.items():
            if name == 'autoLift': value = auto_lift
            if name == 'spreadAround': value = spread_around
            if name == 'spreadDown': value = spread_down
            core._attribute(settings, name, value, low, high)
        show = core._attribute(settings, 'showSkirtControls', True, kind='bool')
        cmds.setAttr(show,keyable=False,channelBox=True)
        cmds.connectAttr(show, controls_group+'.visibility')
        graph = Graph(prefix)
        inverse = om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
        frames = {j: list(om.MMatrix(cmds.getAttr(j+'.worldMatrix[0]'))*inverse)
                  for j in data['joints']}
        stiffness = graph.mul('LiftStrength', settings+'.autoLift', settings+'.lengthStiffness')
        raw = {}
        for row in data['rest_contacts']:
            key = next((key for key, value in data['goals'].items()
                        if value.split('Contact_BMT')[0] == row['station']), None)
            if key is None:
                raise ValueError('Cannot resolve contact station '+row['station'])
            raw[ast.literal_eval(key)] = row['clamp']+'.outputR'
        count, levels = data['chain_count'], data['levels']
        rest = data['stations_local']
        targets, reroutes, calibrations, outputs = {}, [], [], []
        rest_matrices = {row['joint']: row['blend'] for row in data['rest_orientations']}
        contact_checks = []
        for chain in range(count):
            angle = chain*2*math.pi/count
            direction = (math.cos(angle), 0, math.sin(angle))
            weights = [max(0, math.cos(angle-a))**2 for a in (0, math.pi/2, math.pi, 3*math.pi/2)]
            total = sum(weights)
            previous = rest[chain][0]
            previous_push = 0.0
            for level in range(levels):
                name = 'c{:02d}_j{:02d}'.format(chain, level)
                position = rest[chain][level]
                if not level:
                    targets[chain, level] = tuple(position)
                    joint = data['chains'][chain][level]
                    matrix = graph.world(name+'RootWorld',graph.matrix(name+'Root',position,frames[joint]),data['waist'])
                    destination = rest_matrices[joint]+'.target[0].targetMatrix'
                    source = cmds.connectionInfo(destination,sourceFromDestination=True)
                    blended = graph.node('blendMatrix',name+'SolverBlend_BMT')
                    cmds.connectAttr(source,blended+'.inputMatrix')
                    cmds.connectAttr(matrix,blended+'.target[0].targetMatrix')
                    cmds.connectAttr(settings+'.solverBlend',blended+'.target[0].weight')
                    for attr in ('scale','shear'):
                        cmds.setAttr(blended+'.target[0].'+attr+'Weight',0)
                    reroutes.append({'destination':destination,'source':source})
                    cmds.disconnectAttr(source,destination)
                    cmds.connectAttr(blended+'.outputMatrix',destination)
                    outputs.append({'chain':chain,'level':0,'matrix':matrix,'blend':blended,'rest_length':0})
                    continue
                push = raw[chain, level]
                for offset in (-1, 1):
                    neighbor = graph.mul(name+'Across'+str(offset), raw[(chain+offset)%count, level], settings+'.spreadAround')
                    push = graph.maximum(name+'AcrossMax'+str(offset), push, neighbor)
                for neighbor_level in (level-1, level+1):
                    if (chain, neighbor_level) in raw:
                        neighbor = graph.mul(name+'Down'+str(neighbor_level), raw[chain, neighbor_level], settings+'.spreadDown')
                        push = graph.maximum(name+'DownMax'+str(neighbor_level), push, neighbor)
                relaxed = graph.mul(name+'RelaxedPush',graph.add(name+'RelaxedSum',push,previous_push),.5)
                push = graph.lerp(name+'BendFilter',relaxed,push,settings+'.bendStiffness')
                previous_push = push
                activation = graph.clamp(name+'ContactActivation',push,0,1)
                push = graph.add(name+'PaddedPush',push,graph.mul(name+'ContactPadding',activation,settings+'.contactPadding'))
                fraction = level/float(levels-1)
                manual = []
                for axis in 'XYZ':
                    offsets = [graph.mul(name+label+axis, controls[label]+'.translate'+axis,
                                         weight/total*dress._smoothstep(fraction))
                               for label, weight in zip(('Right','Front','Left','Back'), weights) if weight > 1e-8]
                    offsets.append(graph.mul(name+'Hem'+axis, controls['Hem']+'.translate'+axis, fraction**3))
                    manual.append(graph.add(name+'Manual'+axis, *offsets))
                xyz = [graph.add(name+'Target'+axis, position[i], manual[i],
                                 graph.mul(name+'Radial'+axis, push, direction[i]))
                       for i, axis in enumerate('XYZ')]
                delta = [graph.sub(name+'Span'+axis, xyz[i], previous[i]) for i, axis in ((0,'X'),(2,'Z'))]
                horizontal2 = graph.add(name+'HorizontalSquared', *[
                    graph.mul(name+'Square'+str(i), value, value) for i, value in enumerate(delta)])
                length = math.dist(rest[chain][level-1], position)
                horizontal = graph.power(name+'HorizontalLength', graph.maximum(name+'SafeHorizontal',horizontal2,1e-12),.5)
                inverse_ratio = graph.divide(name+'HorizontalRatio',length*.98,horizontal)
                cap = graph.clamp(name+'HorizontalCap',inverse_ratio,0,1)
                for i, component in zip((0,2),delta):
                    projected = graph.add(name+'Projected'+str(i),previous[i],graph.mul(name+'Capped'+str(i),component,cap))
                    xyz[i] = graph.lerp(name+'LengthHorizontal'+str(i),xyz[i],projected,stiffness)
                spans = [graph.sub(name+'CappedSpan'+str(i),xyz[i],previous[i]) for i in (0,2)]
                horizontal2 = graph.add(name+'CappedHorizontalSquared', *[
                    graph.mul(name+'CappedSquare'+str(i),value,value) for i,value in enumerate(spans)])
                vertical2 = graph.maximum(name+'VerticalSquared',
                                           graph.sub(name+'LengthBudget', length*length, horizontal2), 0)
                y = graph.sub(name+'LengthY', previous[1], graph.power(name+'Sqrt', vertical2, .5))
                lift = graph.clamp(name+'Lift', graph.sub(name+'LiftDelta', y, xyz[1]), 0,
                                   graph.mul(name+'LiftLimit', settings+'.maxLift', fraction))
                xyz[1] = graph.add(name+'LiftedY', xyz[1], graph.mul(name+'LiftApplied', lift, stiffness))
                local = graph.matrix(name+'Candidate', xyz)
                world = graph.world(name+'CandidateWorld', local, data['waist'])
                holder = graph.node('transform', name+'Sample_GRP')
                cmds.parent(holder, group)
                cmds.setAttr(holder+'.inheritsTransform', False)
                cmds.connectAttr(world, holder+'.offsetParentMatrix')
                ko = graph.node('cMuscleKeepOut', name+'FinalKeepOutShape', holder)
                cmds.setAttr(ko+'.draw', False)
                cmds.connectAttr(world, ko+'.worldMatrixAim')
                cmds.connectAttr(settings+'.collisionEnable', ko+'.enable')
                for axis, value in zip('XYZ', direction):
                    cmds.setAttr(ko+'.inDirection'+axis, value)
                for i, capsule in enumerate(data['capsules']):
                    cmds.connectAttr(capsule['shape']+'.muscleData', ko+'.muscleData[{}]'.format(i))
                dot = graph.node('vectorProduct', name+'ContactDot_VPR')
                cmds.setAttr(dot+'.operation', 1)
                cmds.connectAttr(ko+'.outTranslateLocal', dot+'.input1')
                cmds.setAttr(dot+'.input2', *direction, type='double3')
                baseline = cmds.getAttr(dot+'.outputX')
                difference = graph.sub(name+'ContactRestDelta', dot+'.outputX', baseline)
                correction = graph.maximum(name+'ContactPositive', difference, 0)
                correction = graph.mul(name+'ContactBlend', correction, settings+'.collisionBlend')
                final = [graph.add(name+'Final'+axis, value, graph.mul(name+'Correction'+axis, correction, direction[i]))
                         for i, (axis, value) in enumerate(zip('XYZ', xyz))]
                targets[chain, level] = tuple(final)
                previous = final
                joint = data['chains'][chain][level]
                matrix = graph.world(name+'FinalWorld', graph.matrix(name+'Final', final,frames[joint]), data['waist'])
                destination = rest_matrices[joint]+'.target[0].targetMatrix'
                source = cmds.connectionInfo(destination, sourceFromDestination=True)
                blended = graph.node('blendMatrix', name+'SolverBlend_BMT')
                cmds.connectAttr(source, blended+'.inputMatrix')
                cmds.connectAttr(matrix, blended+'.target[0].targetMatrix')
                cmds.connectAttr(settings+'.solverBlend', blended+'.target[0].weight')
                for attr in ('scale', 'shear'):
                    cmds.setAttr(blended+'.target[0].'+attr+'Weight', 0)
                reroutes.append({'destination': destination, 'source': source})
                cmds.disconnectAttr(source, destination)
                cmds.connectAttr(blended+'.outputMatrix', destination)
                calibrations.append({'source': dot+'.outputX', 'subtract': difference.split('.')[0], 'baseline': baseline})
                outputs.append({'chain': chain, 'level': level, 'matrix': matrix,
                                'blend': blended, 'rest_length': length})
        output_map = {(row['chain'],row['level']):row for row in outputs}
        orientations = {}
        for row in outputs:
            chain,level = row['chain'],row['level']
            name = 'c{:02d}_j{:02d}'.format(chain,level)
            if level < levels-1:
                aim = graph.node('aimMatrix',name+'Tangent_AMX')
                cmds.connectAttr(row['matrix'],aim+'.inputMatrix')
                cmds.connectAttr(output_map[chain,level+1]['matrix'],aim+'.primaryTargetMatrix')
                angle = chain*2*math.pi/count
                radial = (math.cos(angle),0,math.sin(angle))
                cmds.setAttr(aim+'.primaryInputAxis',0,-1,0,type='double3')
                cmds.setAttr(aim+'.secondaryInputAxis',*radial,type='double3')
                cmds.setAttr(aim+'.secondaryTargetVector',*radial,type='double3')
                cmds.setAttr(aim+'.secondaryMode',2)
                cmds.connectAttr(data['waist']+'.worldMatrix[0]',aim+'.secondaryTargetMatrix')
                orientation = aim+'.outputMatrix'
            else:
                tip = graph.node('blendMatrix',name+'TipOrientation_BMT')
                cmds.connectAttr(row['matrix'],tip+'.inputMatrix')
                cmds.connectAttr(orientations[chain,level-1],tip+'.target[0].targetMatrix')
                for attr in ('translate','scale','shear'):
                    cmds.setAttr(tip+'.target[0].'+attr+'Weight',0)
                orientation = tip+'.outputMatrix'
            orientations[chain,level] = orientation
            destination = row['blend']+'.target[0].targetMatrix'
            cmds.disconnectAttr(row['matrix'],destination)
            cmds.connectAttr(orientation,destination)
            rotation_destination = rest_matrices[data['chains'][chain][level]]+'.target[0].rotateWeight'
            old_rotation = cmds.getAttr(rotation_destination)
            rotation_weight = graph.mul(name+'RotationWeight',settings+'.solverBlend',settings+'.bendStiffness')
            cmds.connectAttr(rotation_weight,rotation_destination)
            row['rotation_destination'] = rotation_destination
            row['previous_rotation_weight'] = old_rotation
        from maya_tools.scripts.tools import skirt_surface_contact
        surface_outputs = skirt_surface_contact.attach(data,graph,settings,body)
        rest_settings = dict(data['rest_collision_settings'])
        _calibration_indicator(graph,dict(data,rest_collision_settings=rest_settings),settings,contact_checks)
        result = {'version': VERSION, 'module': module, 'group': group,
                  'settings': settings, 'controls_group': controls_group, 'controls': controls,
                  'reroutes': reroutes, 'final_contacts': calibrations,
                  'calibration_checks': contact_checks, 'outputs': outputs,
                  'supported_scale': 'positive uniform', 'closed_skirt': True,
                  'dependency': 'MayaMuscle', 'rest_settings': rest_settings,
                  'surface_outputs': surface_outputs,
                  'rest_driver_matrices': [{'node':node,'matrix':list(om.MMatrix(cmds.getAttr(node+'.worldMatrix[0]'))*inverse)}
                      for node in sorted({cap[key] for cap in data['capsules'] for key in ('start','end')})]}
        _bind_handles(module,data,result)
        cmds.addAttr(module, longName='skirtContactData', dataType='string')
        cmds.setAttr(module+'.skirtContactData', json.dumps(result), type='string')
        result['owned_node_count'] = len(set(cmds.ls(long=True))-initial_nodes)
        cmds.setAttr(module+'.skirtContactData', json.dumps(result), type='string')
        character_root = cmds.ls(data['waist'],long=True)[0].split('|')[1]
        result['validation_profile'] = _publish_validation_profile(character_root,data,result,body)
        cmds.setAttr(module+'.skirtContactData',json.dumps(result),type='string')
        scene_evaluation.register(character_root)
        scene_evaluation.apply()
        return result
    except BaseException:
        failure = True
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
        if failure:
            cmds.undo()
            cmds.file(modified=old_dirty)
            scene_evaluation.restore(previous_evaluation)
        cmds.refresh(suspend=refresh_suspended)
        if old_selection:
            cmds.select(old_selection, replace=True)
        else:
            cmds.select(clear=True)
        if not old_undo:
            cmds.undoInfo(stateWithoutFlush=False)


class SkirtContactModule(object):
    """Adapt a calibrated module inside its existing shared rig hierarchy.

    Chains, skin groups and the populated ENV hierarchy belong to the existing
    AutoRig build. This opt-in adapter reuses them rather than rebuilding the
    character or consulting another character's active global build cache.
    """
    def __init__(self,module=None):
        self.data = _data(module)
        self.module_trn = self.data['module']
        self.modules = cmds.listRelatives(self.module_trn,parent=True)[0]
        self.skeleton_grp = self.data['chains_group']
        self.skel_grp = cmds.listRelatives(self.skeleton_grp,parent=True)[0]
        self.controllers_grp = None
        self.guides = self.data['stations_local']

    def make(self,**options):
        result = _upgrade(self.module_trn,**options)
        self.controllers_grp = result['controls_group']
        return result


def upgrade(module=None,auto_lift=1.0,spread_around=.8,spread_down=.6,collision_mesh=None):
    """Apply the opt-in module adapter to an existing calibrated closed skirt."""
    return SkirtContactModule(module).make(auto_lift=auto_lift,spread_around=spread_around,
                                          spread_down=spread_down,collision_mesh=collision_mesh)


def reset_controls(module=None):
    data = _data(module)
    info = _info(data)
    plugs = [ctl+'.translate'+axis for ctl in info['controls'].values() for axis in 'XYZ']
    if any(not cmds.getAttr(plug,settable=True) for plug in plugs):
        raise ValueError('A skirt control channel is locked or driven.')
    cmds.undoInfo(openChunk=True, chunkName='Reset Skirt Controls')
    try:
        for ctl in info['controls'].values():
            for axis in 'XYZ':
                cmds.setAttr(ctl+'.translate'+axis, 0)
    finally:
        cmds.undoInfo(closeChunk=True)


def recalibrate(module=None):
    """Explicitly update contact offsets at the recorded rest pose, undoably.

    Skin/bind data is untouched. Posed legs or nonzero manual offsets fail
    before mutation. Global rigid transforms/uniform scale may differ.
    """
    data = _data(module)
    info = _info(data)
    settings = data['settings']
    if not cmds.getAttr(settings+'.collisionEnable') or abs(cmds.getAttr(settings+'.collisionBlend')-1)>1e-6:
        raise ValueError('Enable full collision before rest calibration.')
    inverse = om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
    scale = om.MTransformationMatrix(inverse.inverse()).scale(om.MSpace.kWorld)
    if min(scale)<=0 or max(scale)-min(scale)>1e-5:
        raise ValueError('Positive uniform scale is required.')
    for record in info['rest_driver_matrices']:
        matrix = list(om.MMatrix(cmds.getAttr(record['node']+'.worldMatrix[0]'))*inverse)
        if max(abs(a-b) for a,b in zip(matrix,record['matrix']))>1e-4:
            raise ValueError('Return all leg drivers to their recorded rest pose.')
    if any(abs(v)>1e-6 for ctl in info['controls'].values() for v in cmds.getAttr(ctl+'.translate')[0]):
        raise ValueError('Reset manual skirt offsets before recalibrating.')
    old_dirty = cmds.file(q=True,modified=True)
    old_undo = cmds.undoInfo(q=True,state=True)
    if not old_undo:cmds.undoInfo(stateWithoutFlush=True)
    cmds.undoInfo(openChunk=True,chunkName='Calibrate Skirt Rest')
    failed = False
    try:
        original_values = [(row,cmds.getAttr(row['subtract']+'.input1D[0]')) for row in data['rest_contacts']]
        for row,value in original_values:
            cmds.setAttr(row['subtract']+'.input1D[1]',value)
            row['baseline'] = value
        # These stations depend on the preceding corrected station. Re-sample
        # in topological order after updating each predecessor's neutral.
        for row in info['final_contacts']:
            value = cmds.getAttr(row['source'])
            cmds.setAttr(row['subtract']+'.input1D[1]',value)
            row['baseline'] = value
        for row in info['calibration_checks']:
            value = cmds.getAttr(row['source'])
            cmds.setAttr(row['baseline_node']+'.input1D[1]',value)
            row['baseline'] = value
            info['rest_settings'][row['source'].rsplit('.',1)[1]] = value
        data['rest_collision_settings'] = {key:cmds.getAttr(settings+'.'+key) for key in data['rest_collision_settings']}
        cmds.setAttr(data['module']+'.dressRigData',json.dumps(data),type='string')
        cmds.setAttr(data['module']+'.skirtContactData',json.dumps(info),type='string')
    except BaseException:
        failed = True
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
        if failed:
            cmds.undo();cmds.file(modified=old_dirty)
        if not old_undo:cmds.undoInfo(stateWithoutFlush=False)
    return info


def export_preset(path, module=None):
    """Save portable authoring settings; evaluated scene remains self contained."""
    data = _data(module)
    info = _info(data)
    if not cmds.getAttr(data['settings']+'.calibrationValid'):
        raise ValueError('Recalibrate the skirt before exporting a preset.')
    payload = {'schema': 'autorig.skirt-contact', 'version': VERSION,
               'chain_count': data['chain_count'], 'levels': data['levels'],
               'stations_local': data['stations_local'], 'closed_skirt': True,
               'parameters': {name: cmds.getAttr(data['settings']+'.'+name) for name in PARAMETERS},
               'rest_settings': info['rest_settings'],
               'manual_offsets': {name: list(cmds.getAttr(ctl+'.translate')[0]) for name, ctl in info['controls'].items()}}
    target = Path(path)
    if target.exists():
        raise FileExistsError('Refusing to replace '+str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding='ascii')
    return str(target)


def import_preset(path, module=None):
    """Restore settings only on a matching existing calibrated layout."""
    data = _data(module)
    info = _info(data)
    if not cmds.getAttr(data['settings']+'.calibrationValid'):
        raise ValueError('Recalibrate the skirt before importing a preset.')
    payload = json.loads(Path(path).read_text(encoding='ascii'))
    if (payload.get('schema') != 'autorig.skirt-contact' or payload.get('version') != VERSION
            or payload.get('stations_local') != data['stations_local']
            or payload.get('rest_settings') != info['rest_settings']):
        raise ValueError('Preset does not match the calibrated skirt layout.')
    values = []
    for name, value in payload['parameters'].items():
        if name not in PARAMETERS or not math.isfinite(value) or not PARAMETERS[name][1] <= value <= PARAMETERS[name][2]:
            raise ValueError('Invalid skirt parameter '+name)
        if name in info['rest_settings'] and abs(value-info['rest_settings'][name])>1e-6:
            raise ValueError('Preset changes calibrated collider parameter '+name)
        values.append((data['settings']+'.'+name, value))
    for name, xyz in payload['manual_offsets'].items():
        if name not in info['controls'] or len(xyz) != 3 or not all(math.isfinite(v) for v in xyz):
            raise ValueError('Invalid manual skirt offset '+name)
        values.extend((info['controls'][name]+'.translate'+axis, value) for axis, value in zip('XYZ', xyz))
    for plug, _ in values:
        if not cmds.getAttr(plug, settable=True):
            raise ValueError('Preset destination is locked or driven: '+plug)
    cmds.undoInfo(openChunk=True, chunkName='Import Skirt Preset')
    try:
        for plug, value in values:
            cmds.setAttr(plug, value)
    finally:
        cmds.undoInfo(closeChunk=True)
    return info


def export_preset_dialog(module=None):
    paths = cmds.fileDialog2(fileMode=0,caption='Export Skirt Preset',fileFilter='Skirt preset (*.json)')
    return export_preset(paths[0],module) if paths else None


def import_preset_dialog(module=None):
    paths = cmds.fileDialog2(fileMode=1,caption='Import Skirt Preset',fileFilter='Skirt preset (*.json)')
    return import_preset(paths[0],module) if paths else None


def _publish_validation_profile(root, data, info, body):
    """Use existing semantic roles and Test Rig's custom profile contract."""
    from maya_tools.scripts.tools import rig_roles,rig_profiles
    bindings = {row['node']:row for row in rig_roles.bindings(root)}

    def bind(node,role,kind='control',index=0):
        path = rig_roles.path(node)
        if path not in bindings:
            rig_roles.bind(root,node,role,module='skirt',kind=kind,index=index)
            bindings.update({row['node']:row for row in rig_roles.bindings(root)})
        return {key:bindings[path][key] for key in ('role','side','module','index','kind')}

    settings = bind(data['settings'],'skirt.settings')
    profile = rig_profiles.preset('custom')
    profile['name'] = 'skirt'
    base = [dict(settings,attribute=key,value=cmds.getAttr(data['settings']+'.'+key))
            for key in ('collisionEnable','collisionBlend','collisionMargin')+tuple(PARAMETERS)]
    profile['cases'][0]['channels'] = list(base)
    for index,(name,ctl) in enumerate(info['controls'].items()):
        spec = bind(ctl,'skirt.panel',index=index)
        axis = 'translateY' if name=='Hem' else ('translateZ' if name in ('Front','Back') else 'translateX')
        value = -2 if name in ('Back','Left') else 2
        case = name.lower()+'_offset'
        profile['cases'].append({'name':case,'channels':list(base)+[dict(spec,attribute=axis,value=value)]})
        profile['transitions'].append({'start':'neutral','end':case,'samples':9,'reverse_tolerance':1e-4})
    collider = bind(body,'skirt.body',kind='mesh')
    profile['contacts'] = []
    for index,g in enumerate(data['garments']):
        source = bind(g['mesh'],'skirt.surface',kind='mesh',index=index)
        profile['contacts'].append({'name':'skirt_surface_'+str(index),'source':source,'target':collider,
                                    'source_vertices':g['region'],'mode':'closed','max_penetration':.01,'tolerance':1e-5})
    rig_profiles.validate(profile)
    cmds.addAttr(data['module'],longName='skirtValidationProfile',dataType='string')
    cmds.setAttr(data['module']+'.skirtValidationProfile',json.dumps(profile),type='string')
    return profile


def export_validation_profile(path,module=None):
    data = _data(module)
    payload = json.loads(cmds.getAttr(data['module']+'.skirtValidationProfile'))
    target = Path(path)
    if target.exists():raise FileExistsError(str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,indent=2),encoding='ascii')
    return str(target)


def audit(module=None):
    """Offline diagnostics on actual final joint positions; not a frame callback."""
    data = _data(module)
    info = _info(data)
    inverse = om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
    stretches, lifts = [], []
    for c, chain in enumerate(data['chains']):
        points = [om.MPoint(*cmds.xform(j, q=True, ws=True, t=True))*inverse for j in chain]
        for level in range(1, len(chain)):
            length = math.dist(data['stations_local'][c][level-1], data['stations_local'][c][level])
            current = (points[level]-points[level-1]).length()
            stretches.append({'chain': c, 'level': level, 'ratio': current/length})
            lifts.append(points[level].y-data['stations_local'][c][level][1])
    scale = om.MTransformationMatrix(inverse.inverse()).scale(om.MSpace.kWorld)
    return {'max_stretch_ratio': max(row['ratio'] for row in stretches),
            'max_compression_ratio': min(row['ratio'] for row in stretches),
            'max_lift_cm_local': max(lifts), 'segments': stretches,
            'calibration_valid': bool(cmds.getAttr(data['settings']+'.calibrationValid')),
            'scale_supported': min(scale) > 0 and max(scale)-min(scale) < 1e-5,
            'manual_controls': info['controls'],
            'length_gate_passed': max(row['ratio'] for row in stretches) <= 1.05}


def check_contact(module=None):
    """Explicit expensive QA action; never invoked during rig evaluation."""
    data = _data(module)
    info = _info(data)
    result = audit(data['module'])
    body = info['surface_outputs'][0]['target']
    result['contacts'] = {g['mesh']:dress.signed_mesh_clearance(
        g['mesh'],g['region'],body,surface_samples=True,penetration_tolerance=.01)
        for g in data['garments']}
    result['passed'] = (result['length_gate_passed'] and result['calibration_valid']
                        and result['scale_supported'] and all(not row['penetrating_vertices']
                        and not row['uncertain_vertices'] for row in result['contacts'].values()))
    return result
