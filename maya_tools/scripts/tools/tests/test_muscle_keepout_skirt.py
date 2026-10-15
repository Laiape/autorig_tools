"""Analytical geometry regression cases for the KeepOut demo's contact audit.

Run with mayapy. Full Maya integration is covered by build_keepout_skirt_test.py.
"""
import os
from pathlib import Path
import sys
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name='python')
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import muscle_keepout_skirt as tool


def vector(x,y,z): return om.MVector(x,y,z)


try:
    a,b,c=vector(0,0,0),vector(2,0,0),vector(0,2,0)
    cases=[
        # Axis pierces a triangle's interior; vertex tests alone miss this.
        (vector(.5,.5,-2),vector(.5,.5,2),0),
        # Parallel axis has its projection entirely inside the triangle.
        (vector(.25,.25,2),vector(.75,.25,2),2),
        # Closest feature is the long diagonal edge.
        (vector(2,2,-1),vector(2,2,1),2**.5),
        # Closest feature is a corner; segment never crosses the plane.
        (vector(-1,-1,0),vector(-1,-1,2),2**.5),
        # Degenerate center segment represents a sphere.
        (vector(.5,.5,3),vector(.5,.5,3),3),
        # Contact exactly on an edge.
        (vector(1,0,-1),vector(1,0,1),0),
    ]
    for p,q,expected in cases:
        measured=tool._segment_triangle_distance(p,q,a,b,c)
        assert abs(measured-expected)<1e-8,(measured,expected)
        # Translation/rotation/scale must preserve the classification.
        transform=om.MTransformationMatrix()
        transform.setTranslation(vector(23,-9,17),om.MSpace.kTransform)
        transform.setRotation(om.MEulerRotation(.31,-.47,.82))
        transform.setScale((1.4,1.4,1.4),om.MSpace.kTransform)
        matrix=transform.asMatrix()
        moved=[om.MVector(om.MPoint(v)*matrix) for v in (p,q,a,b,c)]
        assert abs(tool._segment_triangle_distance(*moved)-expected*1.4)<1e-8
    assert abs(tool._segment_distance(vector(0,0,0),vector(1,0,0),
                                      vector(.5,-1,1),vector(.5,1,1))-1)<1e-8
    assert abs(tool._segment_distance(vector(0,0,0),vector(1,0,0),
                                      vector(0,2,0),vector(1,2,0))-2)<1e-8
    print('PASS KeepOut audit: triangle interior, parallel projection, edge/corner, '
          'sphere, contact, segment distance, world transform invariance')
finally:
    maya.standalone.uninitialize()
