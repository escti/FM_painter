"""Testes G3 (item 4): peso de borda no scoring (UDF estatico)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cpu_backend import score_parallel
from src.edgeweight import edge_weights


class TestEdgeMap(unittest.TestCase):
    def test_uniform_is_ones(self):
        t = np.zeros((16, 16, 3), dtype=np.uint8) + 100
        w = edge_weights(t, 5.0)
        self.assertTrue((w == 1.0).all())

    def test_edge_weighs_boundary(self):
        t = np.zeros((16, 16, 3), dtype=np.uint8)
        t[:, 8:] = 200
        w = edge_weights(t, 4.0)
        self.assertGreater(float(w[:, 7:10].max()), 1.0)
        self.assertEqual(float(w[8, 0]), 1.0)

    def test_off_returns_ones(self):
        t = np.zeros((8, 8, 3), dtype=np.uint8)
        t[:, 4:] = 200
        self.assertTrue((edge_weights(t, 0.0) == 1.0).all())

    def test_border_not_boosted_with_mask(self):
        t = np.zeros((16, 16, 3), dtype=np.uint8)
        t[:, 8:] = 200
        m = np.zeros((16, 16), dtype=np.bool_)
        m[:, 8:] = True  # borda da mascara colada na borda da imagem
        w = edge_weights(t, 4.0, mask=m, erode_px=4)
        self.assertEqual(float(w[8, 8]), 1.0)  # silhueta: neutro
        self.assertEqual(float(w[:, :4].max()), 1.0)  # fora: neutro


class TestWeightedScoring(unittest.TestCase):
    def test_parity_with_ones(self):
        H, W = 32, 32
        rng = np.random.default_rng(1)
        target = rng.integers(0, 255, (H, W, 3)).astype(np.uint8)
        current = rng.integers(0, 255, (H, W, 3)).astype(np.uint8)
        mask = np.ones((H, W), dtype=np.bool_)
        cands = np.array([[16, 16, 10, 10, 0, 255]], dtype=np.float32)
        a = score_parallel(target, current, mask, cands)[0][0]
        ones = np.ones((H, W), dtype=np.float32)
        b = score_parallel(target, current, mask, cands,
                           edge_map=ones)[0][0]
        self.assertEqual(a, b)

    def test_edge_candidate_wins(self):
        H, W = 16, 16
        target = np.zeros((H, W, 3), dtype=np.uint8) + 100
        target[:, 8] = 200  # coluna de borda
        current = np.zeros((H, W, 3), dtype=np.uint8) + 100
        mask = np.ones((H, W), dtype=np.bool_)
        em = edge_weights(target, 4.0)
        cands = np.array([[2, 4, 2, 2, 0, 255],    # longe da borda
                          [8, 8, 2, 2, 0, 255]],   # sobre a borda
                         dtype=np.float32)
        res = score_parallel(target, current, mask, cands, edge_map=em)
        self.assertLess(res[1][0], res[0][0])

    def test_weighted_mean_color(self):
        H, W = 8, 8
        target = np.zeros((H, W, 3), dtype=np.uint8) + 100
        target[2, 2] = 200
        current = np.zeros((H, W, 3), dtype=np.uint8) + 100
        mask = np.zeros((H, W), dtype=np.bool_)
        mask[2, 2] = True
        mask[2, 3] = True
        em = np.ones((H, W), dtype=np.float32)
        em[2, 2] = 7.0  # peso 7:1 -> cor ~ (7*200+100)/8 = 187.5
        cands = np.array([[2.5, 2, 2, 1, 0, 255]], dtype=np.float32)
        _, r, _, _, _, cnt = score_parallel(
            target, current, mask, cands, edge_map=em)[0]
        self.assertEqual(cnt, 2)
        self.assertGreater(r, 160)


if __name__ == "__main__":
    unittest.main()
