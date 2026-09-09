import unittest
from unittest.mock import patch
import numpy as np
from eye_shapes import joint_ellipses, ellipse_level, boundary


class NestedEllipseTests(unittest.TestCase):
    def test_rejects_better_scoring_crossing_pair(self):
        small = ((0., 0.), (10., 10.), 0.)
        large = ((0., 0.), (20., 20.), 0.)
        iris = ((4., 0.), (8., 8.), 0.)
        with patch('eye_shapes.ellipse', side_effect=[[(0., small), (2., large)], [(0., iris)]]):
            outer, chosen, report = joint_ellipses(None, None, None)
        self.assertEqual(outer, large)
        self.assertEqual(chosen, iris)
        self.assertGreater(report['rejected_pairs'], 0)
        self.assertLessEqual(report['maximum_iris_level'], 1)

    def test_no_feasible_pair_is_rejected(self):
        outer = ((0., 0.), (10., 10.), 0.)
        iris = ((9., 0.), (8., 8.), 0.)
        with patch('eye_shapes.ellipse', side_effect=[[(0., outer)], [(0., iris)]]):
            with self.assertRaises(ValueError):
                joint_ellipses(None, None, None)

    def test_rotated_boundary_coordinate_transform(self):
        e = ((17., -3.), (10., 30.), 37.)
        self.assertTrue(np.allclose(ellipse_level(e, boundary(e)), 1))


if __name__ == '__main__':
    unittest.main()
