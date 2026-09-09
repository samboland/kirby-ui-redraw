import unittest
from pathlib import Path
import numpy as np

scope = {}
exec(Path('integrations/chainner/restore_grain.py').read_text().split('# Imports are kept below')[0], scope)
restore = scope['restore_grain']


class GrainTests(unittest.TestCase):
    def test_flat_reference_stays_flat(self):
        ref = np.full((32, 32, 3), 0.5, np.float32)
        target = np.full((128, 128, 3), 0.5, np.float32)
        result, mask = restore(target, ref)
        np.testing.assert_array_equal(result, target)
        self.assertLess(mask.max(), 1e-5)

    def test_seed_and_alpha(self):
        rng = np.random.default_rng(3)
        ref = np.clip(rng.normal(.5, .08, (32, 32, 3)), 0, 1).astype(np.float32)
        target = np.full((128, 128, 4), .5, np.float32)
        target[:, :, 3] = rng.random((128, 128))
        a, _ = restore(target, ref)
        b, _ = restore(target, ref)
        c, _ = restore(target, ref, seed=1)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(a[:, :, 3], target[:, :, 3])
        self.assertGreater(float(np.abs(a-c).max()), .001)
        zero, _ = restore(target, ref, strength=0)
        np.testing.assert_array_equal(zero, target)

    def test_hidden_noise_is_ignored(self):
        ref = np.random.default_rng(0).random((32, 32, 4), dtype=np.float32)
        ref[:, :, 3] = 0
        target = np.zeros((128, 128, 4), np.float32)
        result, mask = restore(target, ref)
        np.testing.assert_array_equal(result, target)
        self.assertEqual(float(mask.max()), 0)


if __name__ == '__main__':
    unittest.main()
