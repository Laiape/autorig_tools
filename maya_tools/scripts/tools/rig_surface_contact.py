"""Sampled world-space surface gaps and closed-mesh point containment.

This is an authoring/QA diagnostic, not a collision solver. Vertex sampling
cannot prove absence of edge/triangle intersections between samples.
"""
import math
from collections import Counter
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_roles as roles, pose_blendshapes as poses


def reference(root, definition):
    return roles.resolve(root, definition.get('role'), definition.get('side','C'), definition.get('module'),
                         definition.get('index',0), 'mesh', definition.get('binding'))


def mesh_fn(mesh):
    path=om.MSelectionList().add(poses.mesh_transform(mesh)).getDagPath(0);path.extendToShape()
    return om.MFnMesh(path)


def _target_data(fn, faces=None):
    """World-space copy gives identical coordinates for rays and closest points."""
    points=fn.getPoints(om.MSpace.kWorld)
    if faces is None:
        counts,indices=fn.getVertices()
    else:
        if not faces or any(type(i) is not int or i<0 or i>=fn.numPolygons for i in faces):
            raise ValueError('Choose valid target face indices.')
        polygons=[list(fn.getPolygonVertices(i)) for i in sorted(set(faces))]
        counts=[len(p) for p in polygons];indices=[v for p in polygons for v in p]
    owner=om.MFnMeshData().create();copy_fn=om.MFnMesh()
    mesh=copy_fn.create(points,counts,indices,parent=owner)
    return owner,mesh,copy_fn


def _closed(fn):
    counts,indices=fn.getVertices();edges=Counter();offset=0
    for count in counts:
        polygon=list(indices[offset:offset+count]);offset+=count
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):edges[tuple(sorted((a,b)))]+=1
    if not edges or any(v!=2 for v in edges.values()):
        raise ValueError('Containment needs a closed manifold target; use proximity for open regions.')


def _inside(fn, point, extent, tolerance):
    classifications=[]
    for direction in ((1,.371,.137),(.193,1,.419),(.271,.157,1)):
        vector=om.MVector(*direction).normal()
        hits=fn.allIntersections(om.MFloatPoint(point.x,point.y,point.z),om.MFloatVector(vector.x,vector.y,vector.z),
            om.MSpace.kObject,extent,False,sortHits=True,tolerance=1e-6)
        params=list(hits[1]) if hits else []
        unique=[]
        for value in params:
            if value>tolerance and (not unique or abs(value-unique[-1])>tolerance):unique.append(value)
        classifications.append(bool(len(unique)%2))
    return classifications[0] if len(set(classifications))==1 else None


def measure(root, spec):
    source,target=reference(root,spec['source']),reference(root,spec['target'])
    mode=spec.get('mode','proximity')
    if mode not in ('proximity','closed'):raise ValueError('Contact mode must be proximity or closed.')
    tolerance=spec.get('tolerance',1e-5)
    limits={name:spec.get(name) for name in ('max_gap','max_penetration')}
    if not math.isfinite(tolerance) or tolerance<=0 or any(v is not None and (not math.isfinite(v) or v<0) for v in limits.values()):
        raise ValueError('Use positive finite tolerance and nonnegative contact limits.')
    if mode=='proximity' and limits['max_penetration'] is not None:
        raise ValueError('Open-surface proximity does not classify penetration.')
    source_fn,target_fn=mesh_fn(source),mesh_fn(target)
    vertices=spec.get('source_vertices',list(range(source_fn.numVertices)))
    if not vertices or any(type(i) is not int or i<0 or i>=source_fn.numVertices for i in vertices):
        raise ValueError('Choose valid source vertex indices.')
    if source==target and not spec.get('target_faces'):
        raise ValueError('Contact on one mesh needs a disjoint target face region.')
    if source==target:
        target_vertices={v for f in spec['target_faces'] for v in target_fn.getPolygonVertices(f)}
        if target_vertices.intersection(vertices):raise ValueError('Source vertices and target faces must be disjoint.')
    if mode=='closed' and spec.get('target_faces') is not None:
        raise ValueError('Containment requires the complete closed target mesh.')
    owner,target_object,fn=_target_data(target_fn,spec.get('target_faces'))
    if mode=='closed':_closed(fn)
    intersector=om.MMeshIntersector();intersector.create(target_object,om.MMatrix())
    points=source_fn.getPoints(om.MSpace.kWorld)
    target_points=fn.getPoints()
    extent=max(((p-om.MPoint()).length() for p in list(points)+list(target_points)),default=1)*4+1
    rows=[]
    for vertex in sorted(set(vertices)):
        point=points[vertex];hit=intersector.getClosestPoint(point)
        distance=(point-om.MPoint(hit.point)).length()
        inside=False if distance<=tolerance or mode=='proximity' else _inside(fn,point,extent,tolerance)
        row={'vertex':vertex,'gap':distance,'classification':'uncertain' if inside is None else ('inside' if inside else 'outside_or_contact')}
        if mode=='closed':row['signed_distance']=None if inside is None else (-distance if inside else distance)
        rows.append(row)
    penetration=max((r['gap'] for r in rows if r['classification']=='inside'),default=0)
    gap=max((r['gap'] for r in rows),default=0)
    uncertain=[r['vertex'] for r in rows if r['classification']=='uncertain']
    offenders=[r['vertex'] for r in rows if (limits['max_gap'] is not None and r['gap']>limits['max_gap']+tolerance) or
        (limits['max_penetration'] is not None and r['classification']=='inside' and r['gap']>limits['max_penetration']+tolerance)]
    return {'name':spec.get('name','surface_contact'),'source':source,'target':target,'mode':mode,
            'measurement':'Sampled vertex-to-surface distance in world space; closed mode uses three agreeing ray parities. Unsampled edge/face intersections are not certified.',
            'max_gap':gap,'max_penetration':penetration,'uncertain_vertices':uncertain,'offending_vertices':offenders,
            'samples':rows,'pass':not offenders and not uncertain}


def profile_contacts(root, profile):
    result=[]
    for spec in profile.get('contacts',[]):
        try:result.append(measure(root,spec))
        except ValueError as exc:result.append({'name':spec.get('name','surface_contact'),'pass':False,'error':str(exc)})
    return result
