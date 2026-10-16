"""Explicit CV identity, periodic aliases and B-spline surface sampling."""
import math

from maya.api import OpenMaya as om


def dag(name):
    return om.MSelectionList().add(name).getDagPath(0)


def surface_shape(node):
    from maya import cmds
    node = node.split('.')[0]
    if cmds.nodeType(node) == 'nurbsSurface':
        shapes = [node]
    else:
        shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True,
                                   type='nurbsSurface', fullPath=True) or []
    if len(shapes) != 1:
        raise ValueError('Select one NURBS surface or its CVs.')
    return cmds.ls(shapes[0], long=True)[0]


def signature(shape):
    return signature_fn(om.MFnNurbsSurface(dag(shape)))


def signature_fn(fn):
    return dict(nu=fn.numCVsInU, nv=fn.numCVsInV,
                du=fn.degreeInU, dv=fn.degreeInV,
                fu=fn.formInU, fv=fn.formInV,
                ku=list(fn.knotsInU()), kv=list(fn.knotsInV()),
                domain_u=list(fn.knotDomainInU), domain_v=list(fn.knotDomainInV))


def canonical(index, spec):
    u, v = divmod(index, spec['nv'])
    if spec['fu'] == om.MFnNurbsSurface.kPeriodic:
        u %= spec['nu'] - spec['du']
    if spec['fv'] == om.MFnNurbsSurface.kPeriodic:
        v %= spec['nv'] - spec['dv']
    return u * spec['nv'] + v


def neighbors(spec, active):
    """Four neighbors; closed endpoints stay distinct, periodic aliases do not."""
    active = set(active)
    nu = spec['nu'] - (spec['du'] if spec['fu'] == 3 else 0)
    nv = spec['nv'] - (spec['dv'] if spec['fv'] == 3 else 0)
    result = {}
    for index in active:
        u, v = divmod(index, spec['nv'])
        adjacent = set()
        for a, b in ((u-1, v), (u+1, v), (u, v-1), (u, v+1)):
            if spec['fu'] in (2, 3):
                a %= nu
            if spec['fv'] in (2, 3):
                b %= nv
            if 0 <= a < nu and 0 <= b < nv:
                other = a * spec['nv'] + b
                if other in active and other != index:
                    adjacent.add(other)
        result[index] = sorted(adjacent)
    return result


def full_knots(knots):
    # Maya omits the outer two knots. Extrapolation also handles repeated ends.
    return [2*knots[0]-knots[1]] + list(knots) + [2*knots[-1]-knots[-2]]


def basis(parameter, count, degree, knots):
    """Nonzero Cox-de Boor basis in the raw Maya CV indexing domain."""
    k = full_knots(knots)
    low, high = k[degree], k[count]
    t = max(low, min(float(parameter), high))
    if t == high:
        t = math.nextafter(high, low)
    work = [1.0 if k[i] <= t < k[i+1] else 0.0 for i in range(len(k)-1)]
    for d in range(1, degree+1):
        nxt = []
        for i in range(len(work)-1):
            a, b = k[i+d]-k[i], k[i+d+1]-k[i+1]
            nxt.append(((t-k[i])*work[i]/a if a else 0.0) +
                       ((k[i+d+1]-t)*work[i+1]/b if b else 0.0))
        work = nxt
    return work[:count]


def greville(count, degree, knots, domain, periodic=False):
    k = full_knots(knots)
    low, high = domain
    values = [sum(k[i+1:i+degree+1])/degree for i in range(count)]
    if periodic:
        return [low + (v-low) % (high-low) for v in values]
    return [max(low, min(v, high)) for v in values]


def anchors(spec):
    return (greville(spec['nu'], spec['du'], spec['ku'], spec['domain_u'], spec['fu'] == 3),
            greville(spec['nv'], spec['dv'], spec['kv'], spec['domain_v'], spec['fv'] == 3))


def footprint(shape, spec, active, uv, radius):
    """World-unit radius in the local surface tangent metric, no cage picking."""
    fn = om.MFnNurbsSurface(dag(shape))
    _, d_u, d_v = fn.getDerivativesAtParam(uv[0], uv[1], om.MSpace.kWorld)
    au, av = anchors(spec)
    result = {}
    for index in active:
        u, v = divmod(index, spec['nv'])
        a, b = au[u]-uv[0], av[v]-uv[1]
        if spec['fu'] in (2, 3):
            period = spec['domain_u'][1]-spec['domain_u'][0]
            a = (a+period/2) % period-period/2
        if spec['fv'] in (2, 3):
            period = spec['domain_v'][1]-spec['domain_v'][0]
            b = (b+period/2) % period-period/2
        distance = (d_u*a+d_v*b).length()
        if distance < radius:
            t = 1.0-distance/max(radius, 1e-12)
            result[index] = t*t*(3-2*t)
    return result


def ray_hit(shape, origin, direction):
    """Nearest forward exact surface hit, correctly transformed into object space."""
    path = dag(shape)
    inverse = path.inclusiveMatrixInverse()
    start = om.MPoint(origin)*inverse
    ray = om.MVector(direction)*inverse
    fn = om.MFnNurbsSurface(path)
    hits = fn.intersect(start, ray, tolerance=1e-6, space=om.MSpace.kObject,
                        distance=True, exactHit=True, all=True)
    if not hits:
        return None
    points, us, vs, distances, exact = hits
    if not exact:
        return None
    candidates = []
    for point, u, v in zip(points, us, vs):
        world = point*path.inclusiveMatrix()
        if (world-om.MPoint(origin))*om.MVector(direction) >= 0:
            if not fn.isPointInTrimmedRegion(u, v):
                candidates.append(((world-om.MPoint(origin)).length(), world, u, v))
    if not candidates:
        return None
    _, world, u, v = min(candidates, key=lambda item: item[0])
    return world, (u, v)


def surface_samples(shape, spec, values, divisions=24):
    """Display samples of rationally interpolated CV scalar values."""
    fn = om.MFnNurbsSurface(dag(shape))
    cvs = fn.cvPositions(om.MSpace.kObject)
    weights = [p.w for p in cvs]
    points, scalars, triangles = [], [], []
    for i in range(divisions+1):
        u = spec['domain_u'][0] + i/divisions*(spec['domain_u'][1]-spec['domain_u'][0])
        bu = basis(u, spec['nu'], spec['du'], spec['ku'])
        for j in range(divisions+1):
            v = spec['domain_v'][0] + j/divisions*(spec['domain_v'][1]-spec['domain_v'][0])
            bv = basis(v, spec['nv'], spec['dv'], spec['kv'])
            numerator = denominator = 0.0
            for a, wa in enumerate(bu):
                if not wa:
                    continue
                for b, wb in enumerate(bv):
                    index = a*spec['nv']+b
                    w = wa*wb*weights[index]
                    numerator += w*values[index]
                    denominator += w
            points.append(fn.getPointAtParam(u, v, om.MSpace.kWorld))
            scalars.append(numerator/denominator if denominator else 0.0)
            if i and j:
                k = i*(divisions+1)+j
                triangles.extend([k-divisions-2, k-1, k, k-divisions-2, k, k-divisions-1])
    return points, scalars, triangles
