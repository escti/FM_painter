"""Testes G1 (itens 8+9): normalizador, penalidade spill, fit-inside, full-canvas."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cpu_backend import score_parallel
from src.candidates import random_candidates
from src.generator import dump_json


def kfps_like():
    return {"shapes": [
        {"type": 16, "data": [10.4, 20.6, 5.2, 6.8, 30.1],
         "color": [200.2, 100.7, 50.3, 255.0], "score": 0.5},
        {"type": 16, "data": [40.0, 40.0, 8.0, 8.0, 0.0],
         "color": [10, 20, 30, 255], "score": 0.4},
    ]}


class TestNormalize(unittest.TestCase):
    def test_kfps_to_exe(self):
        from tools.normalize_for_old_exe import normalize_to_exe, validate
        out, _ = normalize_to_exe(kfps_like())
        self.assertEqual(out["shapes"][0]["type"], 1)
        self.assertEqual(validate(out, "exe"), [])

    def test_check_catches_floats_and_missing_bg(self):
        from tools.normalize_for_old_exe import validate
        errs = validate(kfps_like(), "exe")
        self.assertTrue(any("fundo" in e for e in errs))

    def test_check_kfps_counts_bg(self):
        from tools.normalize_for_old_exe import validate
        d = {"shapes": [{"type": 1, "data": [0, 0, 10, 10],
                         "color": [255, 0, 255, 0], "score": 0},
                        {"type": 16, "data": [1, 1, 2, 2, 0],
                         "color": [1, 2, 3, 255], "score": 0}]}
        self.assertTrue(validate(d, "kfps"))  # type:1 contamina a contagem
        stripped = {"shapes": d["shapes"][1:]}
        self.assertEqual(validate(stripped, "kfps", expect=1), [])
        self.assertTrue(validate(stripped, "kfps", expect=2))


class TestSpillPenalty(unittest.TestCase):
    def test_penalty_punishes_transparent_coverage(self):
        H, W = 32, 32
        target = np.zeros((H, W, 3), dtype=np.uint8) + 100
        current = np.zeros((H, W, 3), dtype=np.uint8) + 100
        mask = np.zeros((H, W), dtype=np.bool_)
        mask[:, :16] = True  # metade opaca, metade transparente
        cands = np.array([[16, 16, 14, 14, 0, 255]], dtype=np.float32)
        d0 = score_parallel(target, current, mask, cands, spill_w=0.0)[0][0]
        d1 = score_parallel(target, current, mask, cands,
                            spill_w=1000.0)[0][0]
        self.assertGreater(d1, d0)

    def test_zero_penalty_preserves_old_scores(self):
        H, W = 32, 32
        target = np.zeros((H, W, 3), dtype=np.uint8) + 200
        current = np.zeros((H, W, 3), dtype=np.uint8)
        mask = np.ones((H, W), dtype=np.bool_)
        cands = np.array([[16, 16, 10, 10, 0, 255]], dtype=np.float32)
        d = score_parallel(target, current, mask, cands, spill_w=0.0)[0][0]
        self.assertLess(d, 0)


class TestFitInside(unittest.TestCase):
    def test_stays_within_opaque_bbox(self):
        H, W = 64, 64
        mask = np.zeros((H, W), dtype=np.bool_)
        mask[16:48, 16:48] = True
        rng = np.random.default_rng(7)
        c = random_candidates(200, W, H, mask, rng=rng, target=None,
                              current=None, fit_inside=True)
        self.assertGreater(len(c), 0)
        import math
        for cx, cy, rx, ry, ang, _ in c:
            ca, sa = abs(math.cos(math.radians(ang))), abs(
                math.sin(math.radians(ang)))
            ex, ey = rx * ca + ry * sa, rx * sa + ry * ca
            self.assertGreaterEqual(cx - ex, 16 - 1e-6)
            self.assertLessEqual(cx + ex, 47 + 1e-6)
            self.assertGreaterEqual(cy - ey, 16 - 1e-6)
            self.assertLessEqual(cy + ey, 47 + 1e-6)


class TestFullCanvas(unittest.TestCase):
    def test_offset_shifts_centers_and_bg(self):
        import json
        import tempfile
        p = dump_json(tempfile.mkdtemp(), "x", 1024, 1024,
                      [(10, 10, 5, 5, 0, 1, 2, 3, 255)], [0.1],
                      offset=(0, 4))
        with open(p) as f:
            d = json.load(f)
        self.assertEqual(d["shapes"][0]["data"], [0, 0, 1024, 1024])
        self.assertEqual(d["shapes"][1]["data"][:2], [10, 14])


class TestSimpreview(unittest.TestCase):
    def test_bg_never_a_shape(self):
        from tools.simpreview import load_all
        import json
        import tempfile
        dd = {"shapes": [{"type": 1, "data": [0, 0, 64, 64],
                          "color": [255, 0, 255, 0], "score": 0},
                         {"type": 16, "data": [10, 10, 5, 5, 0],
                          "color": [9, 9, 9, 255], "score": 0}]}
        td = tempfile.mkdtemp()
        pj = os.path.join(td, "s.json")
        with open(pj, "w") as f:
            json.dump(dd, f)
        shapes, W, H = load_all(pj)
        self.assertEqual(len(shapes), 1)  # type:1 nunca e tinta
        self.assertEqual((W, H), (64, 64))


class TestAspectCap(unittest.TestCase):
    def test_random_respects_cap(self):
        H, W = 64, 64
        mask = np.zeros((H, W), dtype=np.bool_)
        mask[8:56, 8:56] = True
        rng = np.random.default_rng(3)
        c = random_candidates(300, W, H, mask, rng=rng, target=None,
                              current=None, max_aspect=8.0)
        self.assertGreater(len(c), 0)
        for _, _, rx, ry, _, _ in c:
            self.assertLessEqual(max(rx, ry) / max(1.0, min(rx, ry)), 8.0)

    def test_off_by_default(self):
        from src import candidates
        import inspect
        self.assertEqual(
            inspect.signature(candidates.random_candidates)
            .parameters["max_aspect"].default, 0.0)


class TestLateSmall(unittest.TestCase):
    def test_share_forces_small(self):
        H, W = 64, 64
        mask = np.zeros((H, W), dtype=np.bool_)
        mask[8:56, 8:56] = True
        rng = np.random.default_rng(11)
        c = random_candidates(200, W, H, mask, rng=rng, target=None,
                              current=None, progress=0.9, late_share=1.0,
                              late_start=0.5, detail_max_r=4)
        self.assertGreater(len(c), 0)
        for _, _, rx, ry, _, _ in c:
            self.assertLessEqual(max(rx, ry), 4.0 + 1e-6)

    def test_off_by_default(self):
        from src import candidates
        import inspect
        self.assertEqual(
            inspect.signature(candidates.random_candidates)
            .parameters["late_share"].default, 0.0)


class TestAdaptiveMut(unittest.TestCase):
    def test_scale_flows_to_mutants(self):
        from src.candidates import mutate_candidates
        H, W = 64, 64
        mask = np.zeros((H, W), dtype=np.bool_)
        mask[8:56, 8:56] = True
        rng = np.random.default_rng(5)
        base = np.array([32, 32, 10, 10, 0, 255], dtype=np.float32)
        muts = mutate_candidates(base, 50, W, H, mask, rng=rng, scale=0.01)
        self.assertTrue((np.abs(muts[:, 0] - 32) < 3.0).all())

    def test_off_by_default(self):
        from src.profile import load_profile
        import tempfile, os
        fd, pp = tempfile.mkstemp(suffix=".ini")
        os.write(fd, b"stopAt = 10\n")
        os.close(fd)
        self.assertEqual(load_profile(pp)["adaptiveMut"], 0)
        os.remove(pp)


class TestTwoStage(unittest.TestCase):
    def test_topk_path_preserves_count(self):
        from src.generator import generate
        H, W = 32, 32
        target = (np.random.default_rng(2)
                  .integers(0, 255, (H, W, 3)).astype(np.uint8))
        current = np.zeros((H, W, 3), dtype=np.uint8) + 50
        mask = np.ones((H, W), dtype=np.bool_)
        prof = {"stopAt": 3, "saveAt": [], "maxThreads": 1,
                "randomSamples": 20, "mutatedSamples": 10,
                "mutationRounds": 2, "minShapeRadius": 2,
                "maxShapeRadiusDiv": 4, "refineTopK": 4}
        import tempfile
        shapes, _ = generate(target, current, mask, prof,
                             tempfile.mkdtemp(), "t", log=lambda *a: None)
        self.assertEqual(len(shapes), 3)


class TestLumaBands(unittest.TestCase):
    def test_off_is_identity(self):
        from src.image import load_target
        t0, _, m0, _ = load_target(
            "D:/users/thiag/downloads/forza/imagens_originais"
            "/efr_logo2_bg_off.png", luma_bands=0)
        t1, _, m1, _ = load_target(
            "D:/users/thiag/downloads/forza/imagens_originais"
            "/efr_logo2_bg_off.png")
        self.assertTrue((t0 == t1).all())
        self.assertTrue((m0 == m1).all())

    def test_bands_reduce_luminance_levels(self):
        from src.image import load_target
        t0, _, m, _ = load_target(
            "D:/users/thiag/downloads/forza/imagens_originais"
            "/efr_logo2_bg_off.png", luma_bands=0)
        t, _, _, _ = load_target(
            "D:/users/thiag/downloads/forza/imagens_originais"
            "/efr_logo2_bg_off.png", luma_bands=4)
        self.assertFalse((t == t0).all())  # posteriza de verdade
        lum = (0.299 * t[:, :, 0].astype(float)
               + 0.587 * t[:, :, 1].astype(float)
               + 0.114 * t[:, :, 2].astype(float))
        coarse = set(np.unique((lum[m] // 32).astype(int)).tolist())
        self.assertLessEqual(len(coarse), 6)  # 4 faixas (+arredondamento)


if __name__ == "__main__":
    unittest.main()
