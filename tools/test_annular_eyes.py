import unittest
import numpy as np
from annular_eyes import membership, band_geometry, svg_sector


class SectorTests(unittest.TestCase):
    def test_offset_band_has_two_arcs_without_radial_mask(self):
        model = [50,50,20,30,.4,.35,-.35,.37,2.87,4.21]
        path,polygon = band_geometry(model)
        self.assertEqual(path.count(' A '),2)
        self.assertEqual(path.count(' L '),1)
        self.assertTrue(path.endswith(' Z'))
        self.assertTrue(np.isfinite(polygon).all())
        self.assertNotIn('<mask',svg_sector(model,1))

    def test_hole_exterior_and_angular_cut(self):
        model = [50,50,20,30,0,0,0,.5,0,np.pi]
        points = np.array([[65,50],[50,50],[35,50],[75,50]])
        self.assertEqual(membership(model,points,False).tolist(), [True,False,False,False])

    def test_rotation_and_translation(self):
        model = [0,0,20,30,0,0,0,.5,0,np.pi]
        points = np.array([[15.,0.],[0.,0.],[-15.,0.]])
        original = membership(model,points,False)
        model[:2] = [100,80]
        model[4] = np.pi/2
        transformed = np.column_stack((-points[:,1],points[:,0]))+[100,80]
        self.assertTrue(np.array_equal(original,membership(model,transformed,False)))


if __name__ == '__main__':unittest.main()
