"""Teste H2.1b: bigFirstFrac forca raio grande na fase inicial (base washes)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.candidates import random_candidates


class TestBigFirst(unittest.TestCase):
    def test_floor_forced_early(self):
        H = W = 256
        mask = np.ones((H, W), dtype=np.bool_)
        rng = np.random.default_rng(13)
        c = random_candidates(300, W, H, mask, rng=rng, target=None,
                              current=None, progress=0.05, min_r=1,
                              max_r_div=2, big_first_frac=0.2)
        self.assertGreater(len(c), 0)
        floor = min(W, H) // 8
        for _, _, rx, ry, _, _ in c:
            self.assertGreaterEqual(min(rx, ry), floor - 1e-6)

    def test_off_by_default_and_late_phase_normal(self):
        from src import candidates
        import inspect
        self.assertEqual(
            inspect.signature(candidates.random_candidates)
            .parameters["big_first_frac"].default, 0.0)
        H = W = 256
        mask = np.ones((H, W), dtype=np.bool_)
        rng = np.random.default_rng(14)
        c = random_candidates(300, W, H, mask, rng=rng, target=None,
                              current=None, progress=0.9, min_r=1,
                              max_r_div=2, big_first_frac=0.2)
        self.assertTrue((np.minimum(c[:, 2], c[:, 3]) < 32).any())


if __name__ == "__main__":
    unittest.main()
