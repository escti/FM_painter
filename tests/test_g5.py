"""Testes G5: paridade GPU x CPU (score, apply, erro global)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from src.opencl_backend import available as _ocl_available
    _GPU = _ocl_available()
except Exception:
    _GPU = False


def _fixtures(H=64, W=64):
    rng = np.random.default_rng(0)
    target = rng.integers(0, 255, (H, W, 3)).astype(np.uint8)
    mask = np.ones((H, W), dtype=np.bool_)
    mask[:4, :] = False
    mask[:, :4] = False
    emap = np.ones((H, W), dtype=np.float32)
    emap[10:20, 10:20] = 2.0
    current = np.zeros_like(target)
    current[:, :] = 100
    return target, current, mask, emap


def _cands(W=64, H=64, n=300):
    rng = np.random.default_rng(1)
    c = np.zeros((n, 6), dtype=np.float32)
    c[:, 0] = rng.uniform(0, W, n)
    c[:, 1] = rng.uniform(0, H, n)
    c[:, 2] = rng.uniform(1, 12, n)
    c[:, 3] = rng.uniform(1, 12, n)
    c[:, 4] = rng.uniform(0, 360, n)
    c[:, 5] = 255
    return c


@unittest.skipUnless(_GPU, "sem device OpenCL")
class TestGpuParity(unittest.TestCase):
    def test_score_parity_and_argmin(self):
        from src.opencl_backend import GpuScorer
        from src.cpu_backend import score_parallel
        target, current, mask, emap = _fixtures()
        spill_w = 3.0
        c = np.ascontiguousarray(current)
        g = GpuScorer(target, c, mask, emap, spill_w)
        cands = _cands()
        rg = g.score(cands)
        rc = score_parallel(target, current, mask, cands,
                            spill_w=spill_w, edge_map=emap)
        dg = np.array([r[0] for r in rg])
        dc = np.array([r[0] for r in rc])
        self.assertEqual(int(np.argmin(dg)), int(np.argmin(dc)))
        self.assertTrue(np.allclose(dg, dc, rtol=2e-3, atol=5e-1),
                        f"max dif {np.abs(dg - dc).max()}")
        rg_ = np.array([r[1:4] for r in rg])
        rc_ = np.array([r[1:4] for r in rc])
        self.assertTrue(np.allclose(rg_, rc_, atol=1.5))
        self.assertTrue((np.array([r[5] for r in rg]) ==
                         np.array([r[5] for r in rc])).all())

    def test_error_parity(self):
        from src.opencl_backend import GpuScorer
        from src.cpu_backend import full_error_nb
        target, current, mask, emap = _fixtures()
        c = np.ascontiguousarray(current)
        g = GpuScorer(target, c, mask, emap, 0.0)
        e_gpu = g.error()
        e_cpu = float(full_error_nb(target, current, mask, 64, 64))
        self.assertAlmostEqual(e_gpu, e_cpu, places=4)

    def test_apply_parity(self):
        from src.opencl_backend import GpuScorer
        from src.cpu_backend import apply_ellipse_alpha_nb
        target, current, mask, emap = _fixtures()
        c = np.ascontiguousarray(current)
        g = GpuScorer(target, c, mask, emap, 0.0)
        args = (32, 32, 12, 6, 25.0, 200, 50, 10, 255)
        cpu = np.ascontiguousarray(current)
        apply_ellipse_alpha_nb(cpu, mask, 64, 64, *args)
        g.apply(*args)
        got = g.read_current()
        self.assertTrue(np.abs(got.astype(int) - cpu.astype(int)).max() <= 2)

    def test_error_after_apply(self):
        from src.opencl_backend import GpuScorer
        from src.cpu_backend import apply_ellipse_alpha_nb, full_error_nb
        target, current, mask, emap = _fixtures()
        c = np.ascontiguousarray(current)
        g = GpuScorer(target, c, mask, emap, 0.0)
        args = (32, 32, 12, 6, 25.0, 200, 50, 10, 255)
        cpu = np.ascontiguousarray(current)
        apply_ellipse_alpha_nb(cpu, mask, 64, 64, *args)
        g.apply(*args)
        e_cpu = float(full_error_nb(target, cpu, mask, 64, 64))
        self.assertAlmostEqual(g.error(), e_cpu, places=4)


if __name__ == "__main__":
    unittest.main()
