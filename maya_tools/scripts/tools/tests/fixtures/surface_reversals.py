"""Compare emitted surface orientation without treating repaired folds as new ones."""
import numpy as np


def state(points, counts, indices, triangle_counts, triangles):
    points = np.asarray(points, dtype=float)
    counts = np.asarray(counts, dtype=int)
    indices = np.asarray(indices, dtype=int)
    triangles = np.asarray(triangles, dtype=int).reshape(-1, 3)
    faces = np.repeat(np.arange(len(counts)), triangle_counts)
    starts = np.r_[0, np.cumsum(counts)[:-1]]
    ends = np.cumsum(counts)
    following = np.arange(len(indices)) + 1
    following[ends - 1] = starts
    # Local origins avoid cancellation in large world-coordinate scenes.
    vertices = points[indices] - np.repeat(points[indices[starts]], counts, axis=0)
    area = np.add.reduceat(np.cross(vertices, vertices[following]), starts)
    normals = area / np.maximum(np.linalg.norm(area, axis=1)[:, None], 1e-30)
    cross = np.cross(points[triangles[:, 1]] - points[triangles[:, 0]],
                     points[triangles[:, 2]] - points[triangles[:, 0]])
    signed = np.sum(cross * normals[faces], axis=1)
    folds = np.bincount(faces[signed < -1e-8], minlength=len(counts))
    primitives = {(int(face), *sorted(triangle)): (normal, sign)
                  for face, triangle, normal, sign in zip(faces, triangles, cross, signed)}
    return dict(counts=counts, indices=indices, normals=normals, folds=folds, primitives=primitives)


def capture(mesh):
    from maya.api import OpenMaya as om
    points = [[p.x, p.y, p.z] for p in mesh.getPoints(om.MSpace.kWorld)]
    counts, indices = mesh.getVertices()
    triangle_counts, triangles = mesh.getTriangles()
    return state(points, counts, indices, triangle_counts, triangles)


def compare(before, after):
    assert np.array_equal(before['counts'], after['counts'])
    assert np.array_equal(before['indices'], after['indices'])
    # Retain the integration gate's original >90 degree normal-change test,
    # but compare an emitted primitive with itself and distinguish a new
    # front-to-back reversal from an already reversed triangle being repaired.
    old, new = before['primitives'], after['primitives']
    reversed_faces = []
    for key in old.keys() & new.keys():
        a, signed_before = old[key]
        b, signed_after = new[key]
        if (np.linalg.norm(a) > 1e-8 and np.dot(a, b) < 0
                and signed_before > 0 and signed_after < 0):
            reversed_faces.append(key[0])
    polygon_reversals = np.sum(before['normals'] * after['normals'], axis=1) < 0
    return dict(new_triangle_reversals=len(reversed_faces),
                new_polygon_reversals=int(polygon_reversals.sum()),
                new_folded_faces=sorted(set(reversed_faces)),
                resolved_folded_faces=np.flatnonzero(after['folds'] < before['folds']).tolist(),
                retessellated_triangles=len(old.keys() - new.keys()))
