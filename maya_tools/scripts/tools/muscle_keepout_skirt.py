"""Maya Muscle KeepOut skirt proof of concept (Maya 2026).

Run ``data = build_demo()`` in Maya; this adds a uniquely named rig without
replacing the current scene. All driven transforms use offsetParentMatrix.
KeepOut's native vector output is converted once with composeMatrix and stays
in a matrix chain afterwards. No constraints, expressions, scriptJobs, frame
callbacks, dynamics, custom nodes or scheduling overrides are installed.

The demo is a positional contact rig, not a cloth simulation. KeepOut samples
slide radially; a conservative maximum filter covers fabric between samples.
It does not preserve fabric length or solve self collision.
Use validate_demo() in an isolated scene to
compare animated mesh/joint results in DG, Serial and Parallel evaluation.
"""
import json
import math
import statistics
import time
from maya import cmds
from maya.api import OpenMaya as om


def _node(kind, name, parent=None):
    args = {'name': name, 'skipSelect': True}
    if parent is not None:
        args['parent'] = parent
    return cmds.createNode(kind, **args)


def _matrix(position):
    m = om.MTransformationMatrix()
    m.setTranslation(om.MVector(*position), om.MSpace.kTransform)
    return list(m.asMatrix())


def _set_matrix(plug, value):
    cmds.setAttr(plug, *value, type='matrix')


def _follow(name, position, source, parent):
    """Static local offset * upstream world, with no driven-parent feedback."""
    transform = _node('transform', name, parent)
    cmds.setAttr(transform+'.inheritsTransform', False)
    mult = _node('multMatrix', name.replace('_GRP', '_MMT'))
    _set_matrix(mult+'.matrixIn[0]', _matrix(position))
    cmds.connectAttr(source, mult+'.matrixIn[1]')
    cmds.connectAttr(mult+'.matrixSum', transform+'.offsetParentMatrix')
    return transform


def _control(name, offset, radius, color, normal=(0, 1, 0)):
    control = cmds.circle(name=name, normal=normal, radius=radius,
                          sections=16, degree=3, constructionHistory=False)[0]
    cmds.parent(control, offset, relative=True)
    shape = cmds.listRelatives(control, shapes=True)[0]
    cmds.setAttr(shape+'.overrideEnabled', True)
    cmds.setAttr(shape+'.overrideRGBColors', True)
    cmds.setAttr(shape+'.overrideColorRGB', *color, type='double3')
    return control


def _attribute(node, name, value, minimum=None, maximum=None, kind='double'):
    args = {'longName':name, 'attributeType':kind, 'defaultValue':value, 'keyable':True}
    if minimum is not None: args['minValue'] = minimum
    if maximum is not None: args['maxValue'] = maximum
    cmds.addAttr(node, **args)
    return node+'.'+name


def _mesh(name, points, faces, parent):
    fn = om.MFnMesh()
    fn.create([om.MPoint(*p) for p in points], [len(f) for f in faces],
              [v for f in faces for v in f])
    transform = cmds.rename(om.MFnDagNode(fn.parent(0)).fullPathName(), name)
    cmds.parent(transform, parent, relative=True)
    cmds.sets(transform, edit=True, forceElement='initialShadingGroup')
    return transform


def _material(name, color, transparency=0.0):
    shader = _node('lambert', name+'_MAT')
    sg = cmds.sets(name=name+'_SG', renderable=True, noSurfaceShader=True, empty=True)
    cmds.connectAttr(shader+'.outColor', sg+'.surfaceShader')
    cmds.setAttr(shader+'.color', *color, type='double3')
    cmds.setAttr(shader+'.transparency', transparency, transparency, transparency,
                 type='double3')
    return sg


def _capsule_mesh(name, radius, length, parent, material):
    """Renderable capsule whose center line goes from y=0 to y=-length."""
    sides = 24
    rings = []
    for k in range(7):
        a = math.pi*0.5*k/6
        rings.append((radius*math.sin(a), radius*math.cos(a)))
    for k in range(7):
        a = math.pi*0.5*k/6
        rings.append((radius*math.cos(a), -length-radius*math.sin(a)))
    points = [(r*math.cos(2*math.pi*i/sides), y, r*math.sin(2*math.pi*i/sides))
              for r,y in rings for i in range(sides)]
    faces = [[j*sides+i, j*sides+(i+1)%sides, (j+1)*sides+(i+1)%sides,
              (j+1)*sides+i] for j in range(len(rings)-1) for i in range(sides)]
    mesh = _mesh(name, points, faces, parent)
    cmds.sets(mesh, edit=True, forceElement=material)
    return mesh


def _maximum(name, plugs):
    output=plugs[0]
    for i,plug in enumerate(plugs[1:]):
        node=_node('condition',name+'{:02d}_CON'.format(i))
        cmds.setAttr(node+'.operation',2)
        cmds.connectAttr(output,node+'.firstTerm')
        cmds.connectAttr(plug,node+'.secondTerm')
        cmds.connectAttr(output,node+'.colorIfTrueR')
        cmds.connectAttr(plug,node+'.colorIfFalseR')
        output=node+'.outColorR'
    return output


def _coherent_contact_grid(contacts, columns, rows):
    """Conservative neighborhood dilation of the independent contact samples.

    Taking the maximum (rather than averaging) prevents neighboring samples
    from pulling contacted vertices back into a capsule. Angular and vertical
    filters consume only the preceding pass, so the graph is acyclic. KeepOut
    remains the contact solver; the filter covers the fabric between samples.
    """
    raw={}
    for (row,col),item in contacts.items():
        dot=_node('vectorProduct',item['name']+'Radial_VPR')
        cmds.setAttr(dot+'.operation',1)
        cmds.connectAttr(item['keepout']+'.outTranslateLocal',dot+'.input1')
        cmds.setAttr(dot+'.input2',*item['direction'],type='double3')
        raw[row,col]=dot+'.outputX'
    angular={}
    for (row,col),item in contacts.items():
        angular[row,col]=_maximum(item['name']+'AngularMax',
                        [raw[row,(col+offset)%columns] for offset in (-2,-1,0,1,2)])
    for (row,col),item in contacts.items():
        maximum=_maximum(item['name']+'VerticalMax',
                         [angular[r,col] for r in (row-1,row,row+1) if (r,col) in angular])
        vector=_node('multiplyDivide',item['name']+'CoherentPush_MDV')
        cmds.setAttr(vector+'.input1',*item['direction'],type='double3')
        for axis in 'XYZ': cmds.connectAttr(maximum,vector+'.input2'+axis)
        cmds.disconnectAttr(item['keepout']+'.outTranslateLocal',item['compose']+'.inputTranslate')
        cmds.connectAttr(vector+'.output',item['compose']+'.inputTranslate')


def smooth_skin_weights(data, sigma=5.0, strength=.85, waist_rows=3, undoable=False):
    """Blend nine nearby influences using bind-space distance in centimeters.

    The top ring stays attached to the waist. Smoothing fades in over the next
    three rings, wraps around the seam and normalizes separately at the hem.
    Only skin weights change; the existing bind matrices and pose are retained.
    """
    from maya.api import OpenMayaAnim as oma
    if sigma<=0 or not 0<=strength<=1 or waist_rows<1:
        raise ValueError('sigma > 0, strength in [0,1], waist_rows >= 1 required.')
    columns,rows=data['columns'],data['rows']
    selection=om.MSelectionList();selection.add(data['skin'])
    skin=oma.MFnSkinCluster(selection.getDependNode(0))
    influences=skin.influenceObjects()
    physical={path.partialPathName().split('|')[-1]:i for i,path in enumerate(influences)}
    indices=[physical[joint.split('|')[-1]] for joint in data['joints']]
    bind_positions=[]
    for index in indices:
        logical=skin.indexForInfluenceObject(influences[index])
        inverse=om.MMatrix(cmds.getAttr(data['skin']+'.bindPreMatrix[{}]'.format(logical)))
        bind_positions.append(om.MVector(om.MPoint(0,0,0)*inverse.inverse()))
    selection=om.MSelectionList();selection.add(data['skirt'])
    path=selection.getDagPath(0);path.extendToShape()
    vertex_count=om.MFnMesh(path).numVertices
    if vertex_count!=columns*rows: raise ValueError('Skirt topology differs from its contact grid.')
    profiles=[]
    for row in range(rows):
        fade=min(1.0,row/float(waist_rows))
        fade=fade*fade*(3-2*fade)
        alpha=strength*fade
        for col in range(columns):
            vertex=row*columns+col
            kernel={}
            for neighbor_row in range(max(0,row-1),min(rows,row+2)):
                for offset in (-1,0,1):
                    neighbor=neighbor_row*columns+(col+offset)%columns
                    distance=(bind_positions[neighbor]-bind_positions[vertex]).length()
                    kernel[neighbor]=math.exp(-.5*(distance/sigma)**2)
            total=sum(kernel.values())
            profile={indices[neighbor]:alpha*weight/total for neighbor,weight in kernel.items()}
            profile[indices[vertex]]=profile.get(indices[vertex],0)+1-alpha
            profiles.append(profile)
    weights=om.MDoubleArray([profile.get(index,0.0) for profile in profiles
                            for index in range(len(influences))])
    component=om.MFnSingleIndexedComponent()
    obj=component.create(om.MFn.kMeshVertComponent);component.addElements(range(vertex_count))
    maintain=cmds.getAttr(data['skin']+'.maintainMaxInfluences')
    cmds.setAttr(data['skin']+'.maintainMaxInfluences',False)
    cmds.setAttr(data['skin']+'.maxInfluences',9)
    try:
        if undoable:
            for vertex,profile in enumerate(profiles):
                pairs=[(influences[index].fullPathName(),value) for index,value in profile.items() if value>0]
                cmds.skinPercent(data['skin'],data['skirt']+'.vtx[{}]'.format(vertex),
                                 transformValue=pairs,zeroRemainingInfluences=True,normalize=False)
        else:
            skin.setWeights(path,obj,om.MIntArray(range(len(influences))),weights,False)
    finally:
        cmds.setAttr(data['skin']+'.maintainMaxInfluences',maintain)
    stored,_=skin.getWeights(path,obj)
    row_sums=[sum(stored[i*len(influences):(i+1)*len(influences)]) for i in range(vertex_count)]
    counts=[sum(value>1e-8 for value in stored[i*len(influences):(i+1)*len(influences)])
            for i in range(vertex_count)]
    result={'method':'bind-distance Gaussian 3x3, periodic seam, gradual waist fade',
            'sigma_cm':sigma,'strength':strength,'waist_fade_rows':waist_rows,
            'max_influences':max(counts),'normalization_error':max(abs(value-1) for value in row_sums),
            'pinned_waist_vertices':sum(counts[i]==1 for i in range(columns))}
    data['skin_weight_profile']=result
    cmds.setAttr(data['root']+'.demoData',json.dumps(data),type='string')
    return result


def build_demo(prefix='KOskirt_', columns=24, rows=16, animate=True, coherent=True):
    """Build waist + two FK legs + skinned skirt; returns all validation handles."""
    if columns < 8 or rows < 3: raise ValueError('Use at least 8 columns and 3 rows.')
    if cmds.objExists(prefix+'RIG_GRP'):
        raise ValueError('Prefix already exists: '+prefix)
    if not cmds.pluginInfo('MayaMuscle', query=True, loaded=True):
        cmds.loadPlugin('MayaMuscle')
    root = _node('transform', prefix+'RIG_GRP')
    controls = _node('transform', prefix+'controls_GRP', root)
    technical = _node('transform', prefix+'technical_GRP', root)
    geometry = _node('transform', prefix+'geometry_GRP', root)
    joints_group = _node('transform', prefix+'joints_GRP', technical)
    rest_group = _node('transform', prefix+'samples_GRP', technical)
    cmds.setAttr(joints_group+'.visibility', False)
    global_ctl = _control(prefix+'global_CTL', controls, 32, (1,.8,.15))
    waist_offset = _follow(prefix+'waist_GRP', (0,110,0), global_ctl+'.worldMatrix[0]', controls)
    waist = _control(prefix+'waist_CTL', waist_offset, 17, (1,.65,.1))
    enable = _attribute(waist, 'collisionEnable', True, kind='bool')
    blend = _attribute(waist, 'collisionBlend', 1.0, 0, 1)
    thickness = _attribute(waist, 'collisionMargin', 2.0, 0, 4)
    show = _attribute(waist, 'showColliders', False, kind='bool')
    leg_material = _material(prefix+'legs', (.48,.58,.68))
    skirt_material = _material(prefix+'skirt', (.04,.4,.48), .13)
    capsules = []
    leg_controls = {}
    for side, x, color in (('L',8,(.25,.65,1)), ('R',-8,(1,.25,.25))):
        upper_offset = _follow(prefix+side+'_thigh_GRP', (x,-4,0), waist+'.worldMatrix[0]', controls)
        upper = _control(prefix+side+'_thigh_CTL', upper_offset, 8, color)
        lower_offset = _follow(prefix+side+'_knee_GRP', (0,-38,0), upper+'.worldMatrix[0]', controls)
        lower = _control(prefix+side+'_knee_CTL', lower_offset, 6.5, color)
        leg_controls[side] = {'thigh':upper, 'knee':lower}
        for label, ctl, radius in (('thigh',upper,6.2), ('calf',lower,4.8)):
            holder = _follow(prefix+side+'_'+label+'Collider_GRP', (0,0,0), ctl+'.worldMatrix[0]', technical)
            cap = _node('cMuscleObject', prefix+side+'_'+label+'ColliderShape', holder)
            cmds.setAttr(cap+'.type', 2)
            cmds.setAttr(cap+'.capsuleAxis', 4)  # -Y, FK segment's local axis
            padded_radius = _node('plusMinusAverage', prefix+side+'_'+label+'Radius_PMA')
            cmds.setAttr(padded_radius+'.input1D[0]', radius)
            cmds.connectAttr(thickness, padded_radius+'.input1D[1]')
            cmds.connectAttr(padded_radius+'.output1D', cap+'.radius')
            cmds.setAttr(cap+'.length', 38)
            cmds.setAttr(cap+'.relative', False)
            cmds.connectAttr(holder+'.worldMatrix[0]', cap+'.worldMatrixStart')
            _set_matrix(cap+'.worldMatrixStartBase', cmds.getAttr(holder+'.worldMatrix[0]'))
            # Capsule KeepOut ignores the mesh/NURBS "fat" offset; pad radius.
            cmds.setAttr(cap+'.fat', 0)
            cmds.connectAttr(show, cap+'.draw')
            cmds.setAttr(cap+'.shaded', False)
            mesh_holder = _follow(prefix+side+'_'+label+'Proxy_GRP', (0,0,0), ctl+'.worldMatrix[0]', geometry)
            _capsule_mesh(prefix+side+'_'+label+'_GEO', radius, 38, mesh_holder, leg_material)
            capsules.append({'shape':cap, 'driver':ctl, 'radius':radius, 'length':38})
    points, faces, joints, keepouts, rests = [], [], [], [], []
    contacts={}
    for row in range(rows):
        fraction = row/float(rows-1)
        radius = 16 + 8*fraction
        drop = 55*fraction
        for col in range(columns):
            angle = 2*math.pi*col/columns
            x,z = radius*math.cos(angle), radius*math.sin(angle)
            name = prefix+'r{:02d}_c{:02d}'.format(row,col)
            rest = _follow(name+'Rest_GRP', (x,-drop,z), waist+'.worldMatrix[0]', rest_group)
            rests.append(rest)
            source = rest+'.worldMatrix[0]'
            if row:
                ko = _node('cMuscleKeepOut', name+'KeepOutShape', rest)
                cmds.setAttr(ko+'.draw', 0)
                cmds.connectAttr(source, ko+'.worldMatrixAim')
                # Maya 2026 capsule probe verifies this sign moves OUTWARD.
                for axis,v in zip('XYZ', (math.cos(angle),0,math.sin(angle))):
                    cmds.setAttr(ko+'.inDirection'+axis,v)
                cmds.connectAttr(enable, ko+'.enable')
                for i, cap in enumerate(capsules):
                    cmds.connectAttr(cap['shape']+'.muscleData', ko+'.muscleData[{}]'.format(i))
                delta = _node('composeMatrix', name+'Push_CMT')
                cmds.connectAttr(ko+'.outTranslateLocal', delta+'.inputTranslate')
                contacts[row,col]={'name':name,'keepout':ko,'compose':delta,
                                   'direction':(math.cos(angle),0,math.sin(angle))}
                corrected = _node('multMatrix', name+'Contact_MMT')
                cmds.connectAttr(delta+'.outputMatrix', corrected+'.matrixIn[0]')
                cmds.connectAttr(source, corrected+'.matrixIn[1]')
                mixed = _node('blendMatrix', name+'Contact_BMT')
                cmds.connectAttr(source, mixed+'.inputMatrix')
                cmds.connectAttr(corrected+'.matrixSum', mixed+'.target[0].targetMatrix')
                cmds.connectAttr(blend, mixed+'.target[0].weight')
                cmds.setAttr(mixed+'.target[0].rotateWeight', 0)
                cmds.setAttr(mixed+'.target[0].scaleWeight', 0)
                cmds.setAttr(mixed+'.target[0].shearWeight', 0)
                source = mixed+'.outputMatrix'
                keepouts.append(ko)
            joint = _node('joint', name+'_JNT', joints_group)
            cmds.setAttr(joint+'.inheritsTransform', False)
            cmds.setAttr(joint+'.segmentScaleCompensate', False)
            cmds.setAttr(joint+'.radius', .45)
            cmds.connectAttr(source, joint+'.offsetParentMatrix')
            joints.append(joint)
            points.append((x,110-drop,z))
    if coherent: _coherent_contact_grid(contacts,columns,rows)
    for row in range(rows-1):
        for col in range(columns):
            a=row*columns+col; b=row*columns+(col+1)%columns
            faces.append([a,b,b+columns,a+columns])
    skirt = _mesh(prefix+'skirt_GEO', points, faces, geometry)
    # Bind with collisions temporarily off: neutral bind matrices retain rest.
    cmds.setAttr(enable, False)
    skin = cmds.skinCluster(joints, skirt, name=prefix+'skirt_SKC',
                            toSelectedBones=True, maximumInfluences=1,
                            normalizeWeights=1, skinMethod=0)[0]
    sel = om.MSelectionList(); sel.add(skin)
    from maya.api import OpenMayaAnim as oma
    fn_skin = oma.MFnSkinCluster(sel.getDependNode(0))
    sel = om.MSelectionList(); sel.add(skirt)
    path = sel.getDagPath(0); path.extendToShape()
    comp = om.MFnSingleIndexedComponent()
    obj = comp.create(om.MFn.kMeshVertComponent); comp.addElements(range(len(points)))
    weights = om.MDoubleArray([1.0 if i==j else 0.0
                             for i in range(len(points)) for j in range(len(joints))])
    fn_skin.setWeights(path, obj, om.MIntArray(range(len(joints))), weights, False)
    cmds.setAttr(enable, True)
    cmds.sets(skirt, edit=True, forceElement=skirt_material)
    cmds.polySoftEdge(skirt, angle=180, constructionHistory=False)
    data = {'root':root, 'prefix':prefix, 'global':global_ctl, 'waist':waist,
            'legs':leg_controls, 'capsules':capsules, 'joints':joints,
            'keepouts':keepouts, 'rests':rests, 'skirt':skirt, 'skin':skin,
            'columns':columns, 'rows':rows, 'coherent_contact':coherent}
    if animate: animate_demo(data)
    cmds.addAttr(root, longName='demoData', dataType='string')
    cmds.setAttr(root+'.demoData', json.dumps(data), type='string')
    cmds.addAttr(root, longName='rigNotes', dataType='string')
    cmds.setAttr(root+'.rigNotes', 'Frame 1 neutral; 25 left step; 49 right step; '
                 '73 squat; 97 leg spread; 121 global transform; 145 neutral. '
                 'Waist: collisionEnable, collisionBlend, collisionMargin, showColliders. '
                 'Positional collision only; no cloth length or self collision. '
                 'Native scheduling is retained; see evaluation_report_v*.json.', type='string')
    cmds.select(waist)
    return data


def animate_demo(data):
    """Animation includes a non-identity global transform to exercise matrix spaces."""
    left, right = data['legs']['L'], data['legs']['R']
    poses = [(1,0,0,0,0,0,0), (25,-58,70,12,12,0,0),
             (49,12,12,-58,70,0,0), (73,-58,105,-58,105,0,0),
             (97,0,15,0,15,-32,32), (121,-45,65,10,15,-12,12),
             (145,0,0,0,0,0,0)]
    for frame,lx,lk,rx,rk,lz,rz in poses:
        for ctl,attr,value in ((left['thigh'],'rotateX',lx),(left['knee'],'rotateX',lk),
                               (right['thigh'],'rotateX',rx),(right['knee'],'rotateX',rk),
                               (left['thigh'],'rotateZ',lz),(right['thigh'],'rotateZ',rz)):
            cmds.setKeyframe(ctl, attribute=attr, time=frame, value=value)
    for frame, tx, ry, scale in ((1,0,0,1),(97,0,0,1),(121,28,37,1.25),(145,0,0,1)):
        cmds.setKeyframe(data['global'], attribute='translateX', time=frame, value=tx)
        cmds.setKeyframe(data['global'], attribute='rotateY', time=frame, value=ry)
        for axis in 'XYZ': cmds.setKeyframe(data['global'], attribute='scale'+axis, time=frame, value=scale)
    cmds.keyTangent(data['global'], left['thigh'], left['knee'], right['thigh'], right['knee'],
                    inTangentType='linear', outTangentType='linear')
    cmds.playbackOptions(minTime=1, maxTime=145, animationStartTime=1, animationEndTime=145)
    cmds.currentTime(1)


def _snapshot(data):
    sel=om.MSelectionList(); sel.add(data['skirt'])
    path=sel.getDagPath(0); path.extendToShape()
    points=[(p.x,p.y,p.z) for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]
    matrices=[cmds.getAttr(j+'.worldMatrix[0]') for j in data['joints']]
    return {'points':points, 'matrices':matrices}


def _max_error(a, b):
    return max(abs(x-y) for key in ('points','matrices')
               for av,bv in zip(a[key],b[key]) for x,y in zip(av,bv))


def _capsule_clearances(data, points, padded=True):
    """Independent distance-to-segment check of EVERY skinned mesh vertex."""
    caps=[]
    margin=cmds.getAttr(data['waist']+'.collisionMargin') if padded else 0.0
    for cap in data['capsules']:
        wm=om.MMatrix(cmds.getAttr(cap['driver']+'.worldMatrix[0]'))
        length=cmds.getAttr(cap['shape']+'.length')
        a=om.MPoint(0,0,0)*wm; b=om.MPoint(0,-length,0)*wm
        scale=om.MVector(1,0,0)*wm
        caps.append((om.MVector(a), om.MVector(b), (cap['radius']+margin)*scale.length()))
    distances=[]
    for point in points:
        p=om.MVector(*point)
        for a,b,r in caps:
            segment=b-a
            t=max(0.0,min(1.0,((p-a)*segment)/(segment*segment)))
            distances.append((p-(a+segment*t)).length()-r)
    return min(distances), sum(d < -1e-4 for d in distances)


def _surface_probe_points(data, points):
    """Probe edges and both triangle interiors, not just collision vertices."""
    samples=[]
    columns=data['columns']
    for row in range(data['rows']-1):
        for col in range(columns):
            a=row*columns+col; b=row*columns+(col+1)%columns
            quad=[points[i] for i in (a,a+columns,b+columns,b)]
            for tri in ((0,1,2),(0,2,3)):
                samples.append(tuple(sum(quad[i][axis] for i in tri)/3 for axis in range(3)))
            for i in range(4):
                samples.append(tuple((quad[i][axis]+quad[(i+1)%4][axis])/2 for axis in range(3)))
    return samples


def _point_triangle_distance(p,a,b,c):
    ab=b-a; ac=c-a; ap=p-a
    d1=ab*ap; d2=ac*ap
    if d1<=0 and d2<=0: return ap.length()
    bp=p-b; d3=ab*bp; d4=ac*bp
    if d3>=0 and d4<=d3: return bp.length()
    vc=d1*d4-d3*d2
    if vc<=0 and d1>=0 and d3<=0:
        return (p-(a+ab*(d1/(d1-d3)))).length()
    cp=p-c; d5=ab*cp; d6=ac*cp
    if d6>=0 and d5<=d6: return cp.length()
    vb=d5*d2-d1*d6
    if vb<=0 and d2>=0 and d6<=0:
        return (p-(a+ac*(d2/(d2-d6)))).length()
    va=d3*d6-d5*d4
    if va<=0 and d4-d3>=0 and d5-d6>=0:
        return (p-(b+(c-b)*((d4-d3)/((d4-d3)+(d5-d6))))).length()
    denominator=va+vb+vc
    if abs(denominator)<1e-18:
        return min((p-a).length(),(p-b).length(),(p-c).length())
    return (p-(a+ab*(vb/denominator)+ac*(vc/denominator))).length()


def _segment_distance(p1,q1,p2,q2):
    d1=q1-p1; d2=q2-p2; r=p1-p2
    a=d1*d1; e=d2*d2; f=d2*r
    if a<=1e-18 and e<=1e-18: return r.length()
    if a<=1e-18:
        s=0; t=max(0,min(1,f/e))
    else:
        c=d1*r
        if e<=1e-18:
            t=0; s=max(0,min(1,-c/a))
        else:
            b=d1*d2; denominator=a*e-b*b
            s=max(0,min(1,(b*f-c*e)/denominator)) if abs(denominator)>1e-18 else 0
            t=(b*s+f)/e
            if t<0: t=0; s=max(0,min(1,-c/a))
            elif t>1: t=1; s=max(0,min(1,(b-c)/a))
    return ((p1+d1*s)-(p2+d2*t)).length()


def _segment_triangle_distance(p,q,a,b,c):
    direction=q-p; ab=b-a; ac=c-a
    h=direction^ac; determinant=ab*h
    if abs(determinant)>1e-14:
        s=p-a; u=(s*h)/determinant
        k=s^ab; v=(direction*k)/determinant
        t=(ac*k)/determinant
        if 0<=u<=1 and 0<=v and u+v<=1 and 0<=t<=1: return 0.0
    return min(_point_triangle_distance(p,a,b,c),_point_triangle_distance(q,a,b,c),
               _segment_distance(p,q,a,b),_segment_distance(p,q,b,c),
               _segment_distance(p,q,c,a))


def _triangle_body_clearances(data,points):
    """Exact segment-to-render-triangle test against the visible body capsules.

    A capsule is the Minkowski sum of its center segment and a radius. Thus
    segment-to-triangle distance minus radius checks entire triangle interiors,
    including narrow intersections missed by vertices/centroids/edge midpoints.
    """
    selection=om.MSelectionList(); selection.add(data['skirt'])
    path=selection.getDagPath(0); path.extendToShape()
    _,indices=om.MFnMesh(path).getTriangles()
    vectors=[om.MVector(*point) for point in points]
    triangles=[]
    for i in range(0,len(indices),3):
        tri=[vectors[indices[i+j]] for j in range(3)]
        bounds=[(min(v[ax] for v in tri),max(v[ax] for v in tri)) for ax in range(3)]
        triangles.append((tri,bounds))
    worst=float('inf'); count=0
    for cap in data['capsules']:
        wm=om.MMatrix(cmds.getAttr(cap['driver']+'.worldMatrix[0]'))
        a=om.MVector(om.MPoint(0,0,0)*wm)
        length=cmds.getAttr(cap['shape']+'.length')
        b=om.MVector(om.MPoint(0,-length,0)*wm)
        radius=cap['radius']*(om.MVector(1,0,0)*wm).length()
        axis_bounds=[(min(a[ax],b[ax]),max(a[ax],b[ax])) for ax in range(3)]
        for tri,bounds in triangles:
            lower_bound=math.sqrt(sum(max(0,bounds[ax][0]-axis_bounds[ax][1],
                                          axis_bounds[ax][0]-bounds[ax][1])**2
                                     for ax in range(3)))-radius
            if lower_bound>=0 and lower_bound>=worst: continue
            clearance=_segment_triangle_distance(a,b,*tri)-radius
            worst=min(worst,clearance)
            if clearance < -1e-4: count+=1
    return worst,count,len(triangles)


def validate_demo(data, frames=None, repeats=3):
    """Compare all vertices and joint matrix values, sequential and random access.

    This deliberately uses normal frame updates, not dgdirty or per-node
    getAttr pulls, so the Evaluation Manager must evaluate the animated graph.
    Scheduling is queried from the graph; no scheduling overrides are changed.
    """
    if frames is None: frames=list(range(1,146))
    frames=sorted(set(frames))
    old_mode=cmds.evaluationManager(query=True,mode=True)[0]
    old_frame=cmds.currentTime(query=True)
    report={'maya':cmds.about(version=True), 'api':cmds.about(apiVersion=True),
            'frame_count':len(frames), 'vertex_count':data['columns']*data['rows'],
            'keepout_count':len(data['keepouts']), 'modes':{},
            'skin_weight_profile':data.get('skin_weight_profile'),
            'sources':[
              'https://download.autodesk.com/us/maya/2011help/files/Muscle_Nodes_cMuscleKeepOut_node.htm',
              'https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/evaluationManager.html']}
    snapshots={}
    try:
        for mode in ('off','serial','parallel'):
            cmds.evaluationManager(mode=mode)
            cmds.currentTime(frames[-1]); cmds.currentTime(frames[0])
            snapshots[mode]={}
            clearances=[]; penetrations=0
            surface_clearances=[]; triangle_penetrations=0; worst_surface_frame=None
            for frame in frames:
                cmds.currentTime(frame, update=True)
                snap=_snapshot(data); snapshots[mode][frame]=snap
                distance,count=_capsule_clearances(data,snap['points'])
                clearances.append(distance); penetrations+=count
                if mode=='off':
                    distance,count,triangle_count=_triangle_body_clearances(data,snap['points'])
                    if not surface_clearances or distance<min(surface_clearances): worst_surface_frame=frame
                    surface_clearances.append(distance); triangle_penetrations+=count
            if mode=='off':
                report['surface_contact']={'triangle_count':triangle_count,
                       'frame_count':len(frames), 'minimum_body_clearance_cm':min(surface_clearances),
                       'worst_frame':worst_surface_frame,
                       'penetrating_triangle_capsule_pairs':triangle_penetrations,
                       'method':'exact segment-to-render-triangle distance against body capsules'}
            errors=[]
            # Jump backwards and forwards: detects stale results and time dependence.
            for frame in list(reversed(frames))[::3]+frames[1::3]:
                cmds.currentTime(frame,update=True)
                errors.append(_max_error(snapshots[mode][frame],_snapshot(data)))
            timings=[]
            for _ in range(repeats):
                cmds.currentTime(frames[0])
                start=time.perf_counter()
                for frame in frames:
                    cmds.currentTime(frame,update=True)
                    _snapshot(data)
                timings.append(1000*(time.perf_counter()-start)/len(frames))
            info={'requested':mode, 'actual':cmds.evaluationManager(query=True,mode=True),
                  'random_access_max_error':max(errors,default=0),
                  'minimum_vertex_clearance_cm':min(clearances),
                  'penetrating_vertex_capsule_pairs':penetrations,
                  'median_ms_per_sample_with_mesh_and_matrix_reads':statistics.median(timings)}
            if mode != 'off':
                info['fallback']=cmds.evaluationManager(query=True,fallbackTriggered=True)
                info['disable_info']=cmds.evaluationManager(query=True,disableInfo=True)
                info['dg_max_error']=max(_max_error(snapshots['off'][f],snapshots[mode][f]) for f in frames)
            report['modes'][mode]=info
            print('KeepOut evaluation checked: '+mode,flush=True)
        graph=cmds.dbpeek(op='graph', evaluationGraph=True, allObjects=True,
                         argument=['scheduling','verbose'])
        report['scheduling_graph']=graph
        scheduling=json.loads(graph)['scheduling']['scheduling']
        report['muscle_scheduling']={kind:[node for node in nodes
                                         if 'KeepOutShape' in node or 'ColliderShape' in node]
                                    for kind,nodes in scheduling.items()}
        report['scheduling_node_counts']={kind:len(nodes) for kind,nodes in scheduling.items()}
        report['scheduling_overrides']={flag:cmds.evaluationManager(query=True,**{flag:True})
                 for flag in ('nodeTypeParallel','nodeTypeSerialize','nodeTypeGloballySerialize','nodeTypeUntrusted')}
        report['cycle_clusters']={node:cluster for node in data['keepouts']+data['joints']
                                  if (cluster:=cmds.evaluationManager(cycleCluster=node))}
        report['dg_cycle_plugs']=cmds.cycleCheck(all=True,list=True) or []
        report['constraints']=cmds.ls(type='constraint') or []
        report['expressions']=cmds.ls(type='expression') or []
        report['driven_trs_connections']=[joint for joint in data['joints']
                if any(cmds.listConnections(joint+'.'+attr,source=True,destination=False)
                       for attr in ('translate','rotate','scale'))]
        # Contact must actually displace points, and disabled contact must recover rest.
        cmds.currentTime(25)
        on=_snapshot(data)
        cmds.setAttr(data['waist']+'.collisionEnable',False)
        cmds.currentTime(24); cmds.currentTime(25)
        disabled=_snapshot(data)
        off_clearance,off_count=_capsule_clearances(data,disabled['points'])
        report['collision_response_cm']=_max_error({'points':on['points'],'matrices':[]},
                                                  {'points':disabled['points'],'matrices':[]})
        report['disabled_contact']={'minimum_clearance_cm':off_clearance,'penetrating_pairs':off_count}
        expected=[tuple(cmds.getAttr(rest+'.worldMatrix[0]')[12:15]) for rest in data['rests']]
        report['disabled_rest_error_cm']=max(abs(a-b) for p,q in zip(expected,disabled['points']) for a,b in zip(p,q))
        cmds.setAttr(data['waist']+'.collisionEnable',True)
        report['passed']=(all(v.get('dg_max_error',0)<1e-5 and v['random_access_max_error']<1e-5
                             and (data.get('skin_weight_profile') or v['penetrating_vertex_capsule_pairs']==0)
                             and not v.get('fallback',False)
                             for v in report['modes'].values())
                          and report['collision_response_cm']>.1 and report['disabled_rest_error_cm']<1e-5
                          and report['surface_contact']['penetrating_triangle_capsule_pairs']==0
                          and not report['cycle_clusters'] and not report['dg_cycle_plugs']
                          and not report['constraints']
                          and not report['expressions'] and not report['driven_trs_connections'])
    finally:
        cmds.setAttr(data['waist']+'.collisionEnable',True)
        cmds.evaluationManager(mode=old_mode)
        cmds.currentTime(old_frame)
    return report
