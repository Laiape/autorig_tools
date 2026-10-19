"""Surface gates distinguish a new fold, a repaired fold and native retessellation."""
import unittest
import numpy as np
from fixtures import surface_reversals as surface


class SurfaceTests(unittest.TestCase):
    def quad(self, points, triangles=(0, 1, 2, 0, 2, 3)):
        return surface.state(points, [4], [0, 1, 2, 3], [2], triangles)

    def test_repaired_fold_is_not_reported_as_a_new_reversal(self):
        # A compressed nonplanar lip quad whose second triangle initially
        # opposes its own polygon, then returns to the polygon's front side.
        folded = self.quad([[1.77454388, 189.00189209, 11.33932304],
                            [1.65087104, 189.09649658, 11.44828415],
                            [1.64552581, 189.08827209, 11.33686638],
                            [1.59145427, 189.13978577, 11.37550831]])
        repaired = self.quad([[1.77454233, 189.00189209, 11.39076805],
                              [1.65086877, 189.09649658, 11.53008080],
                              [1.64552343, 189.08827209, 11.42291164],
                              [1.59145284, 189.13978577, 11.42991352]])
        result = surface.compare(folded, repaired)
        self.assertEqual(result['new_triangle_reversals'], 0)
        self.assertEqual(result['new_polygon_reversals'], 0)
        self.assertEqual(result['resolved_folded_faces'], [0])
        self.assertEqual(surface.compare(repaired, folded)['new_triangle_reversals'], 1)

    def test_retriangulated_planar_quad_keeps_its_orientation(self):
        points = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
        result = surface.compare(self.quad(points), self.quad(points, (0, 1, 3, 1, 2, 3)))
        self.assertEqual(result['new_triangle_reversals'], 0)
        self.assertEqual(result['new_polygon_reversals'], 0)
        self.assertEqual(result['retessellated_triangles'], 2)

    def test_whole_face_reversal_is_still_rejected(self):
        points = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
        mirrored = points.copy()
        mirrored[:, 0] *= -1
        result = surface.compare(self.quad(points), self.quad(mirrored))
        self.assertEqual(result['new_polygon_reversals'], 1)


if __name__ == '__main__':
    unittest.main()
