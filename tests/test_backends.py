import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.cpu_backend import score_candidate_nb, score_parallel, full_error_nb


class TestBackend(unittest.TestCase):
    def test_score_improves(self):
        H, W = 32, 32
        target = np.zeros((H, W, 3), dtype=np.uint8) + 200
        current = np.zeros((H, W, 3), dtype=np.uint8)
        mask = np.ones((H, W), dtype=np.bool_)
        d, r, g, b, cnt = score_candidate_nb(target, current, mask, W, H, 16, 16, 10, 10, 0)
        self.assertLess(d, 0)
        self.assertGreater(cnt, 0)
        self.assertGreater(r, 150)

    def test_transparent_ignored(self):
        H, W = 16, 16
        target = np.zeros((H, W, 3), dtype=np.uint8) + 100
        current = np.zeros((H, W, 3), dtype=np.uint8)
        mask = np.zeros((H, W), dtype=np.bool_)
        d, r, g, b, cnt = score_candidate_nb(target, current, mask, W, H, 8, 8, 6, 6, 0)
        self.assertEqual(cnt, 0)
        self.assertEqual(d, 0.0)

    def test_parallel_alpha(self):
        H, W = 32, 32
        target = np.zeros((H, W, 3), dtype=np.uint8) + 200
        current = np.zeros((H, W, 3), dtype=np.uint8)
        mask = np.ones((H, W), dtype=np.bool_)
        cands = np.array([[16, 16, 10, 10, 0, 255],
                          [16, 16, 10, 10, 0, 128]], dtype=np.float32)
        res = score_parallel(target, current, mask, cands)
        self.assertEqual(len(res), 2)
        # opaco deve melhorar mais que semi neste caso simples
        self.assertLess(res[0][0], 0)
        self.assertLess(res[1][0], 0)

    def test_json_format_alpha(self):
        from src.generator import dump_json
        import json, tempfile
        with tempfile.TemporaryDirectory() as td:
            p = dump_json(td, "x", 64, 64,
                          [(10, 10, 5, 5, 0, 255, 0, 0, 128)], [0.1])
            with open(p) as f:
                d = json.load(f)
            self.assertEqual(d["shapes"][0]["type"], 1)
            self.assertEqual(d["shapes"][1]["type"], 16)
            self.assertEqual(d["shapes"][1]["color"][3], 128)

    def test_post_prune(self):
        from src.post import prune_diagnostic
        H, W = 32, 32
        target = np.zeros((H, W, 3), dtype=np.uint8) + 50
        mask = np.ones((H, W), dtype=np.bool_)
        bg = np.array([50, 50, 50], dtype=np.uint8)
        shapes = [(16, 16, 5, 5, 0, 50, 50, 50, 255),
                  (16, 16, 5, 5, 0, 50, 50, 50, 255)]  # duplicada redundante
        kept, removable = prune_diagnostic(shapes, target, mask, bg, tol=0.001)
        self.assertEqual(len(kept), 2)  # diagnostico nao remove
        self.assertGreaterEqual(len(removable), 1)

    def test_post_preserves_count(self):
        from src.post import post_process
        H, W = 32, 32
        target = np.zeros((H, W, 3), dtype=np.uint8) + 50
        mask = np.ones((H, W), dtype=np.bool_)
        bg = np.array([50, 50, 50], dtype=np.uint8)
        shapes = [(8 + i, 8 + i, 4, 4, 0, 60, 60, 60, 255) for i in range(5)]
        out = post_process(shapes, target, mask, bg, passes=1,
                           post_mutations=10)
        self.assertEqual(len(out), 5)


if __name__ == "__main__":
    unittest.main()
