"""Sparse matrix-driven joint chains for a real skinned dress.

KeepOut is evaluated only at chain stations. The original garment topology,
materials and upper-body skin remain intact. New weights use periodic quadratic
B-splines around the waist and along the chains. All driven joints use OPM;
world-space contact goals are independent of the deforming garment and joints.
Neutral contact is subtracted before filtering, and fitted rest orientations
follow the hip to preserve the silhouette and avoid inward transition twists.
"""
import json
import math
from collections import deque
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from maya_tools.scripts.tools import muscle_keepout_skirt as core


def mesh_path(mesh):
    selection=om.MSelectionList();selection.add(mesh)
    path=selection.getDagPath(0)
    if path.node().hasFn(om.MFn.kTransform):
        shapes=cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True,type='mesh') or []
        if len(shapes)!=1:
            raise ValueError('Expected one visible mesh shape on '+mesh)
        path=om.MSelectionList().add(shapes[0]).getDagPath(0)
    return path


def mesh_points(mesh):
    return [tuple(p)[:3] for p in om.MFnMesh(mesh_path(mesh)).getPoints(om.MSpace.kWorld)]


def lower_connected_region(mesh, top=83.0):
    """Flood from the hem, below the waist: disconnected sleeve tips stay out."""
    path=mesh_path(mesh);points=om.MFnMesh(path).getPoints(om.MSpace.kWorld)
    allowed={i for i,p in enumerate(points) if p.y<=top}
    minimum=min(p.y for p in points)
    seeds={i for i in allowed if points[i].y<=minimum+5}
    adjacency={}
    iterator=om.MItMeshVertex(path)
    while not iterator.isDone():
        if iterator.index() in allowed: adjacency[iterator.index()]=iterator.getConnectedVertices()
        iterator.next()
    region=set(seeds);queue=deque(seeds)
    while queue:
        vertex=queue.popleft()
        for neighbor in adjacency.get(vertex,[]):
            if neighbor in allowed and neighbor not in region: region.add(neighbor);queue.append(neighbor)
    return sorted(region)


def _periodic_delta(a,b): return (a-b+math.pi)%(2*math.pi)-math.pi


def _smoothstep(value):
    value=max(0,min(1,value))
    return value*value*(3-2*value)


def _quadratic_weights(value, count, periodic=False):
    nearest=int(math.floor(value+.5));fraction=value-nearest
    raw=[(nearest-1,.5*(.5-fraction)**2),(nearest,.75-fraction*fraction),
         (nearest+1,.5*(.5+fraction)**2)]
    result={}
    for index,weight in raw:
        index=index%count if periodic else max(0,min(count-1,index))
        result[index]=result.get(index,0)+weight
    return result


def _fit_stations(mesh, region, waist, chains, levels, top_world):
    points=om.MFnMesh(mesh_path(mesh)).getPoints(om.MSpace.kWorld)
    inverse=om.MMatrix(cmds.getAttr(waist+'.worldInverseMatrix[0]'))
    local=[points[i]*inverse for i in region]
    top=(om.MPoint(0,top_world,0)*inverse).y
    step=2*math.pi/chains
    station_points=[];hems=[]
    for chain in range(chains):
        angle=chain*step
        sector=[p for p in local if abs(_periodic_delta(math.atan2(p.z,p.x),angle))<=step*.65]
        if not sector: raise ValueError('Empty garment angular sector: '+str(chain))
        hem=min(p.y for p in sector);hems.append(hem)
        station=[]
        for level in range(levels):
            y=top+(hem-top)*level/(levels-1)
            # Fit the actual cloth silhouette, including the asymmetric hem.
            candidates=sorted(sector,key=lambda p:abs(p.y-y))[:max(4,len(sector)//5)]
            radii=sorted(math.hypot(p.x,p.z) for p in candidates)
            radius=radii[len(radii)//2]
            station.append((radius*math.cos(angle),y,radius*math.sin(angle)))
        station_points.append(station)
    return station_points,top,hems


def _capsule(prefix,label,start,end,radius,waist,group,settings):
    aim=core._node('aimMatrix',prefix+label+'Aim_AMX')
    cmds.connectAttr(start+'.worldMatrix[0]',aim+'.inputMatrix')
    cmds.connectAttr(end+'.worldMatrix[0]',aim+'.primaryTargetMatrix')
    cmds.setAttr(aim+'.primaryInputAxis',0,-1,0,type='double3')
    cmds.setAttr(aim+'.secondaryInputAxis',1,0,0,type='double3')
    cmds.setAttr(aim+'.secondaryTargetVector',1,0,0,type='double3')
    cmds.setAttr(aim+'.secondaryMode',2)
    cmds.connectAttr(waist+'.worldMatrix[0]',aim+'.secondaryTargetMatrix')
    holder=core._node('transform',prefix+label+'_GRP',group)
    cmds.setAttr(holder+'.inheritsTransform',False)
    cmds.connectAttr(aim+'.outputMatrix',holder+'.offsetParentMatrix')
    shape=core._node('cMuscleObject',prefix+label+'Shape',holder)
    cmds.setAttr(shape+'.type',2);cmds.setAttr(shape+'.capsuleAxis',4)
    cmds.setAttr(shape+'.relative',False);cmds.setAttr(shape+'.fat',0)
    cmds.connectAttr(holder+'.worldMatrix[0]',shape+'.worldMatrixStart')
    radius_plug=core._attribute(settings,label+'Radius',radius,.1,20)
    padded=core._node('plusMinusAverage',prefix+label+'Radius_PMA')
    cmds.connectAttr(radius_plug,padded+'.input1D[0]')
    cmds.connectAttr(settings+'.collisionMargin',padded+'.input1D[1]')
    cmds.connectAttr(padded+'.output1D',shape+'.radius')
    distance=core._node('distanceBetween',prefix+label+'Length_DST')
    cmds.connectAttr(start+'.worldMatrix[0]',distance+'.inMatrix1')
    cmds.connectAttr(end+'.worldMatrix[0]',distance+'.inMatrix2')
    row=core._node('decomposeMatrix',prefix+label+'Scale_DCM')
    cmds.connectAttr(holder+'.worldMatrix[0]',row+'.inputMatrix')
    normalize=core._node('multiplyDivide',prefix+label+'Length_MDV')
    cmds.setAttr(normalize+'.operation',2)
    cmds.connectAttr(distance+'.distance',normalize+'.input1X')
    cmds.connectAttr(row+'.outputScaleX',normalize+'.input2X')
    cmds.connectAttr(normalize+'.outputX',shape+'.length')
    cmds.setAttr(shape+'.shaded',False)
    return {'shape':shape,'driver':holder,'radius_attribute':radius_plug,'start':start,'end':end}


def _coherence(contacts,chains,levels):
    radial={};angular={}
    for (chain,level),item in contacts.items():
        dot=core._node('vectorProduct',item['name']+'Radial_VPR')
        cmds.setAttr(dot+'.operation',1)
        cmds.connectAttr(item['shape']+'.outTranslateLocal',dot+'.input1')
        cmds.setAttr(dot+'.input2',*item['direction'],type='double3')
        radial[chain,level]=dot+'.outputX'
    for (chain,level),item in contacts.items():
        angular[chain,level]=core._maximum(item['name']+'AcrossChains',
                                         [radial[(chain+d)%chains,level] for d in (-1,0,1)])
    for (chain,level),item in contacts.items():
        push=core._maximum(item['name']+'AlongChain',
                           [angular[chain,r] for r in (level-1,level,level+1) if (chain,r) in angular])
        vector=core._node('multiplyDivide',item['name']+'Push_MDV')
        cmds.setAttr(vector+'.input1',*item['direction'],type='double3')
        for axis in 'XYZ': cmds.connectAttr(push,vector+'.input2'+axis)
        cmds.connectAttr(vector+'.output',item['compose']+'.inputTranslate')


def compensate_rest_contacts(data=None):
    """Calibrate at neutral: only additional capsule contact bends the dress.

    Subtract each station's static KeepOut response before neighborhood maxima.
    Clamping the difference prevents inward pull when a leg moves away. The
    saved graph uses native nodes and does not require this module at playback.
    Joint orientations follow the hip while translations follow contact goals.
    Call once, with the character in its intended rest pose and collisions on.
    """
    if data is None:
        data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
    if data.get('rest_contacts'):
        raise ValueError('Rest contacts have already been calibrated.')
    if not cmds.getAttr(data['settings']+'.collisionEnable'):
        raise ValueError('Enable collisions before calibrating the rest pose.')
    stations=[]
    # Sample all stations before editing any connection.
    for shape in data['keepouts']:
        name=shape.removesuffix('KeepOutShape')
        source=name+'Radial_VPR.outputX'
        destinations=cmds.listConnections(source,source=False,destination=True,plugs=True) or []
        stations.append((name,source,destinations,cmds.getAttr(source)))
    records=[]
    for name,source,destinations,baseline in stations:
        delta=core._node('plusMinusAverage',name+'RestDelta_PMA')
        cmds.setAttr(delta+'.operation',2)
        cmds.connectAttr(source,delta+'.input1D[0]')
        cmds.setAttr(delta+'.input1D[1]',baseline)
        positive=core._node('clamp',name+'RestContact_CLP')
        cmds.setAttr(positive+'.minR',0)
        cmds.setAttr(positive+'.maxR',1e10)
        cmds.connectAttr(delta+'.output1D',positive+'.inputR')
        for destination in destinations:
            cmds.disconnectAttr(source,destination)
            cmds.connectAttr(positive+'.outputR',destination)
        records.append({'station':name,'baseline':baseline,'subtract':delta,'clamp':positive})
    data['rest_contacts']=records
    # Follow contact positions without rotating the upper transition into the
    # body. Joint orientations retain the fitted rest shape and follow the hip;
    # child local matrices still resolve explicitly against their real parent.
    waist_inverse=om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
    orientations=[(joint,om.MMatrix(cmds.getAttr(joint+'.worldMatrix[0]'))*waist_inverse)
                  for joint in data['joints']]
    data['rest_orientations']=[]
    for joint,local in orientations:
        name=joint.removesuffix('_JNT')
        reference=core._node('multMatrix',name+'RestOrientation_MMT')
        core._set_matrix(reference+'.matrixIn[0]',list(local))
        cmds.connectAttr(data['waist']+'.worldMatrix[0]',reference+'.matrixIn[1]')
        destination=name+'ParentSpace_MMT.matrixIn[0]'
        source=cmds.connectionInfo(destination,sourceFromDestination=True)
        blend=core._node('blendMatrix',name+'RestOrientation_BMT')
        cmds.connectAttr(reference+'.matrixSum',blend+'.inputMatrix')
        cmds.connectAttr(source,blend+'.target[0].targetMatrix')
        for component in ('rotate','scale','shear'):
            cmds.setAttr(blend+'.target[0].'+component+'Weight',0)
        cmds.disconnectAttr(source,destination)
        cmds.connectAttr(blend+'.outputMatrix',destination)
        data['rest_orientations'].append({'joint':joint,'reference':reference,'blend':blend})
    data['rest_collision_settings']={attribute:cmds.getAttr(data['settings']+'.'+attribute)
                                    for attribute in ('collisionMargin','L_thighRadius','L_calfRadius',
                                                      'R_thighRadius','R_calfRadius')}
    cmds.setAttr(data['module']+'.dressRigData',json.dumps(data),type='string')
    return records


def _skin_garment(mesh,skin,data,region,transition=9.0):
    selection=om.MSelectionList();selection.add(skin)
    old_fn=oma.MFnSkinCluster(selection.getDependNode(0))
    path=mesh_path(mesh);mesh_fn=om.MFnMesh(path);points=mesh_fn.getPoints(om.MSpace.kWorld)
    component=om.MFnSingleIndexedComponent()
    obj=component.create(om.MFn.kMeshVertComponent);component.addElements(range(mesh_fn.numVertices))
    old_weights,old_count=old_fn.getWeights(path,obj)
    old_names=[p.fullPathName() for p in old_fn.influenceObjects()]
    old_max=cmds.getAttr(skin+'.maxInfluences')
    old_normalization=cmds.getAttr(skin+'.normalizeWeights')
    old_maintain=cmds.getAttr(skin+'.maintainMaxInfluences')
    cmds.setAttr(skin+'.normalizeWeights',0)
    cmds.setAttr(skin+'.maintainMaxInfluences',False)
    cmds.skinCluster(skin,edit=True,addInfluence=data['joints'],weight=0.0,lockWeights=False)
    selection=om.MSelectionList();selection.add(skin)
    fn=oma.MFnSkinCluster(selection.getDependNode(0))
    paths=fn.influenceObjects();lookup={p.fullPathName():i for i,p in enumerate(paths)}
    old_indices=[lookup[name] for name in old_names]
    chain_indices={}
    for chain,names in enumerate(data['chains']):
        for level,name in enumerate(names): chain_indices[chain,level]=lookup[cmds.ls(name,long=True)[0]]
    inverse=om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
    allowed=set(region);weights=[];counts=[];alphas=[];affected=[]
    for vertex,p in enumerate(points):
        local=p*inverse
        alpha=_smoothstep((data['top_local']-local.y)/transition) if vertex in allowed else 0.0
        alphas.append(alpha)
        row=[0.0]*len(paths)
        for old_index,new_index in enumerate(old_indices):
            row[new_index]=old_weights[vertex*old_count+old_index]*(1-alpha)
        if alpha:
            parameter=(math.atan2(local.z,local.x)%(2*math.pi))*data['chain_count']/(2*math.pi)
            angular=_quadratic_weights(parameter,data['chain_count'],periodic=True)
            for chain,angular_weight in angular.items():
                height=data['top_local']-data['hems_local'][chain]
                vertical=(data['top_local']-local.y)/height*(data['levels']-1)
                for level,vertical_weight in _quadratic_weights(vertical,data['levels']).items():
                    row[chain_indices[chain,level]]+=alpha*angular_weight*vertical_weight
        if alpha:
            total=sum(row)
            row=[value/total for value in row]
            affected.append(vertex);weights.extend(row)
        counts.append(sum(value>1e-8 for value in row))
    cmds.setAttr(skin+'.maxInfluences',max(old_max,max(counts)))
    changed_component=om.MFnSingleIndexedComponent()
    changed=changed_component.create(om.MFn.kMeshVertComponent);changed_component.addElements(affected)
    fn.setWeights(path,changed,om.MIntArray(range(len(paths))),om.MDoubleArray(weights),False)
    cmds.setAttr(skin+'.normalizeWeights',old_normalization)
    cmds.setAttr(skin+'.maintainMaxInfluences',old_maintain)
    stored,_=fn.getWeights(path,obj)
    unchanged_error=max((abs(stored[v*len(paths)+new]-old_weights[v*old_count+old])
                         for v,a in enumerate(alphas) if a==0 for old,new in enumerate(old_indices)),default=0)
    normalization=max(abs(sum(stored[v*len(paths):(v+1)*len(paths)])-1) for v in affected)
    return {'mesh':mesh,'skin':skin,'vertex_count':len(points),'region':region,
            'affected_vertices':sum(alpha>0 for alpha in alphas),'max_influences':max(counts),
            'upper_weight_error':unchanged_error,'normalization_error':normalization,
            'alpha':alphas}


def build(mesh='c_tunic_GEO',skin='skinCluster__c_tunic_GEO',waist='C_localHip_ENV',
          chain_count=12,levels=6,top_world=83.0,prefix='NiniDress_',margin=3.0):
    """Attach sparse contact/bend chains to Nini's existing leg/hip rig."""
    if cmds.objExists(prefix+'Module_GRP'): raise ValueError('Dress module already exists.')
    if chain_count<6 or levels<3: raise ValueError('At least 6 chains and 3 joints per chain.')
    if not cmds.pluginInfo('MayaMuscle',q=True,loaded=True): cmds.loadPlugin('MayaMuscle')
    region=lower_connected_region(mesh,top_world)
    stations,top,hems=_fit_stations(mesh,region,waist,chain_count,levels,top_world)
    module=core._node('transform',prefix+'Module_GRP','modules_GRP')
    cmds.setAttr(module+'.inheritsTransform',False)
    technical=core._node('transform',prefix+'Calculations_GRP',module)
    chains_group=core._node('transform',prefix+'Chains_GRP','skel_GRP')
    cmds.setAttr(chains_group+'.inheritsTransform',False)
    control_group=core._follow(prefix+'Settings_GRP',(23,9,0),waist+'.worldMatrix[0]','controls_GRP')
    settings=core._control('C_dressSettings_CTL',control_group,2.5,(1,.65,.1),normal=(0,0,1))
    for channel in ('translate','rotate','scale'):
        for axis in 'XYZ':
            cmds.setAttr(settings+'.'+channel+axis,lock=True,keyable=False,channelBox=False)
        cmds.setAttr(settings+'.'+channel,lock=True,keyable=False,channelBox=False)
    cmds.setAttr(settings+'.visibility',lock=True,keyable=False,channelBox=False)
    core._attribute(settings,'collisionEnable',False,kind='bool')
    core._attribute(settings,'collisionBlend',1,0,1)
    core._attribute(settings,'collisionMargin',margin,0,6)
    capsules=[]
    for side in ('L','R'):
        for label,start,end,radius in ((side+'_thigh',side+'_legUpper00_ENV',side+'_legLower00_ENV',6.8),
                                       (side+'_calf',side+'_legLower00_ENV',side+'_legAnkle_ENV',4.9)):
            capsules.append(_capsule(prefix,label,start,end,radius,waist,technical,settings))
    for attribute in ('showChains','showColliders'):
        plug=core._attribute(settings,attribute,False,kind='bool')
        cmds.setAttr(plug,keyable=False,channelBox=True)
    cmds.connectAttr(settings+'.showChains',chains_group+'.visibility')
    for capsule in capsules:
        cmds.connectAttr(settings+'.showColliders',capsule['shape']+'.draw')
    goals={};contacts={};rest_nodes={}
    for chain in range(chain_count):
        angle=2*math.pi*chain/chain_count
        for level in range(levels):
            name=prefix+'c{:02d}_j{:02d}'.format(chain,level)
            rest=core._follow(name+'Rest_GRP',stations[chain][level],waist+'.worldMatrix[0]',technical)
            rest_nodes[chain,level]=rest
            goal=rest+'.worldMatrix[0]'
            if level:
                shape=core._node('cMuscleKeepOut',name+'KeepOutShape',rest)
                cmds.setAttr(shape+'.draw',0)
                cmds.connectAttr(goal,shape+'.worldMatrixAim')
                for axis,value in zip('XYZ',(math.cos(angle),0,math.sin(angle))): cmds.setAttr(shape+'.inDirection'+axis,value)
                cmds.connectAttr(settings+'.collisionEnable',shape+'.enable')
                for index,cap in enumerate(capsules): cmds.connectAttr(cap['shape']+'.muscleData',shape+'.muscleData[{}]'.format(index))
                compose=core._node('composeMatrix',name+'Push_CMT')
                corrected=core._node('multMatrix',name+'Contact_MMT')
                cmds.connectAttr(compose+'.outputMatrix',corrected+'.matrixIn[0]')
                cmds.connectAttr(goal,corrected+'.matrixIn[1]')
                blend=core._node('blendMatrix',name+'Contact_BMT')
                cmds.connectAttr(goal,blend+'.inputMatrix')
                cmds.connectAttr(corrected+'.matrixSum',blend+'.target[0].targetMatrix')
                cmds.connectAttr(settings+'.collisionBlend',blend+'.target[0].weight')
                for component in ('rotate','scale','shear'): cmds.setAttr(blend+'.target[0].'+component+'Weight',0)
                goals[chain,level]=blend+'.outputMatrix'
                contacts[chain,level]={'name':name,'shape':shape,'compose':compose,
                                       'direction':(math.cos(angle),0,math.sin(angle))}
            else: goals[chain,level]=goal
    _coherence(contacts,chain_count,levels)
    chains=[];joints=[]
    for chain in range(chain_count):
        angle=2*math.pi*chain/chain_count;names=[];matrices=[]
        for level in range(levels):
            name=prefix+'c{:02d}_j{:02d}'.format(chain,level)
            if level<levels-1:
                aim=core._node('aimMatrix',name+'Bend_AMX')
                cmds.connectAttr(goals[chain,level],aim+'.inputMatrix')
                cmds.connectAttr(goals[chain,level+1],aim+'.primaryTargetMatrix')
                cmds.setAttr(aim+'.primaryInputAxis',0,-1,0,type='double3')
                cmds.setAttr(aim+'.secondaryInputAxis',math.cos(angle),0,math.sin(angle),type='double3')
                cmds.setAttr(aim+'.secondaryTargetVector',math.cos(angle),0,math.sin(angle),type='double3')
                cmds.setAttr(aim+'.secondaryMode',2)
                cmds.connectAttr(waist+'.worldMatrix[0]',aim+'.secondaryTargetMatrix')
                world=aim+'.outputMatrix'
            else:
                tip=core._node('blendMatrix',name+'Tip_BMT')
                cmds.connectAttr(goals[chain,level],tip+'.inputMatrix')
                cmds.connectAttr(matrices[-1],tip+'.target[0].targetMatrix')
                for component in ('translate','scale','shear'): cmds.setAttr(tip+'.target[0].'+component+'Weight',0)
                world=tip+'.outputMatrix'
            parent=names[-1] if names else chains_group
            joint=core._node('joint',name+'_JNT',parent)
            cmds.setAttr(joint+'.segmentScaleCompensate',False);cmds.setAttr(joint+'.radius',.5)
            local=core._node('multMatrix',name+'ParentSpace_MMT')
            cmds.connectAttr(world,local+'.matrixIn[0]')
            # Read the explicit parent, never the driven joint's parentInverseMatrix.
            cmds.connectAttr(parent+'.worldInverseMatrix[0]',local+'.matrixIn[1]')
            cmds.connectAttr(local+'.matrixSum',joint+'.offsetParentMatrix')
            names.append(joint);joints.append(joint);matrices.append(world)
        chains.append(names)
    data={'module':module,'waist':waist,'settings':settings,'chains_group':chains_group,
          'chain_count':chain_count,'levels':levels,'chains':chains,'joints':joints,
          'capsules':capsules,'top_world':top_world,'top_local':top,'hems_local':hems,
          'stations_local':stations,'goals':{str(k):v for k,v in goals.items()},'mesh':mesh,'skin':skin,
          'keepouts':[item['shape'] for item in contacts.values()], 'garments':[]}
    data['garments'].append(_skin_garment(mesh,skin,data,region))
    if cmds.objExists('c_embroider_GEO'):
        embroidered=mesh_points('c_embroider_GEO')
        trim_region=[i for i,p in enumerate(embroidered) if p[1]<=top_world]
        if trim_region: data['garments'].append(_skin_garment('c_embroider_GEO','skinCluster__c_embroider_GEO',data,trim_region))
    cmds.setAttr(settings+'.collisionEnable',True)
    cmds.addAttr(module,longName='dressRigData',dataType='string')
    cmds.setAttr(module+'.dressRigData',json.dumps(data),type='string')
    compensate_rest_contacts(data)
    return data


def _inside_point(fn,point,acceleration):
    """Require three agreeing rays that do not graze triangle boundaries."""
    votes=[]
    for direction in ((1,.371,.137),(.193,1,.419),(.271,.157,1),
                      (-.813,.291,.571),(.317,-.913,.227),(.439,.637,-.717),
                      (-.593,-.217,.773),(.733,-.439,-.521),(-.317,.839,-.467)):
        vector=om.MVector(*direction).normal()
        hits=fn.allIntersections(om.MFloatPoint(point.x,point.y,point.z),
            om.MFloatVector(vector.x,vector.y,vector.z),om.MSpace.kObject,600,False,
            accelParams=acceleration,sortHits=True,tolerance=1e-7)
        params=list(hits[1]) if hits else []
        # A ray close to an edge can double-count a shared triangle boundary.
        # Discard that direction and use another, rather than taking a majority.
        if hits and any(min(a,b,1-a-b)<1e-4 for a,b in zip(hits[4],hits[5])): continue
        unique=[]
        for value in params:
            if value>1e-4 and (not unique or abs(value-unique[-1])>1e-4): unique.append(value)
        votes.append(bool(len(unique)%2))
        if len(votes)>=3 and len(set(votes))==1: return votes[0]
    return None


def signed_mesh_clearance(source,vertices,target,closed=True,surface_samples=False,
                          penetration_tolerance=.05):
    """Vertex sampling; three agreeing ray parities for a closed body mesh.

    An open garment such as the pants only supports unsigned proximity.
    """
    if not math.isfinite(penetration_tolerance) or penetration_tolerance < 0:
        raise ValueError('A finite nonnegative penetration tolerance is required.')
    from maya_tools.scripts.tools import rig_surface_contact as audit
    source_points=mesh_points(source)
    owner,target_object,target_fn=audit._target_data(om.MFnMesh(mesh_path(target)))
    if closed: audit._closed(target_fn)
    acceleration=target_fn.autoUniformGridParams()
    intersector=om.MMeshIntersector();intersector.create(target_object,om.MMatrix())
    samples=[(vertex,om.MPoint(*source_points[vertex])) for vertex in vertices]
    if surface_samples:
        source_fn=om.MFnMesh(mesh_path(source));allowed=set(vertices)
        counts,indices=source_fn.getTriangles();edges=set();offset=0
        for triangle in range(len(indices)//3):
            ids=list(indices[triangle*3:triangle*3+3])
            if not allowed.intersection(ids): continue
            pts=[om.MPoint(*source_points[i]) for i in ids]
            samples.append(('triangle_'+str(triangle),om.MPoint(*[sum(p[axis] for p in pts)/3 for axis in range(3)])))
            for a,b in ((ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0])):
                edge=tuple(sorted((a,b)))
                if edge in edges: continue
                edges.add(edge)
                samples.append(('edge_{}_{}'.format(*edge),om.MPoint(*[(source_points[a][axis]+source_points[b][axis])/2 for axis in range(3)])))
    minimum=float('inf');surface_minimum=float('inf');inside=[];uncertain=[]
    for sample,point in samples:
        hit=intersector.getClosestPoint(point)
        distance=(point-om.MPoint(hit.point)).length()
        containment=_inside_point(target_fn,point,acceleration) if closed and distance>penetration_tolerance else False
        if containment is None: uncertain.append(sample)
        signed=distance*(-1 if containment else 1)
        minimum=min(minimum,signed)
        surface_minimum=min(surface_minimum,distance)
        if signed < -penetration_tolerance: inside.append(sample)
    return {'minimum_signed_clearance_cm':minimum if closed else None,
            'minimum_surface_distance_cm':surface_minimum,
            'penetration_tolerance_cm':penetration_tolerance,
            'penetrating_vertices':inside,'uncertain_vertices':uncertain,
            'closed_target':closed,'checked_vertices':len(vertices),'checked_samples':len(samples),
            'measurement':'Vertices, triangle centers and edge midpoints' if surface_samples else 'Vertices'}
