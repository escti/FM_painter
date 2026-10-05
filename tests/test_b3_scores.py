"""Teste B3: checkpoints/final preservam o score por etapa (nao o erro final)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.gen import save_final


class TestB3Scores(unittest.TestCase):
    def test_checkpoint_keeps_stage_scores(self):
        shapes = [(10, 10, 5, 5, 0, 1, 2, 3, 255),
                  (20, 20, 4, 4, 0, 4, 5, 6, 255),
                  (30, 30, 3, 3, 0, 7, 8, 9, 255)]
        gen_scores = [0.9, 0.5, 0.2]
        out = tempfile.mkdtemp()
        save_final(out, "t", 64, 64, shapes, gen_scores, [2], (0, 0),
                   final_err=0.1)

        with open(os.path.join(out, "t.2.json")) as f:
            cp = json.load(f)
        cp_scores = [s["score"] for s in cp["shapes"][1:]]  # pula o bg type:1
        self.assertAlmostEqual(cp_scores[0], 0.9)
        self.assertAlmostEqual(cp_scores[1], 0.5)
        self.assertNotIn(0.1, cp_scores)  # era o erro final unico (bug B3)

        with open(os.path.join(out, "t.json")) as f:
            fin = json.load(f)
        fin_scores = [s["score"] for s in fin["shapes"][1:]]
        self.assertEqual(len(fin_scores), 3)
        self.assertAlmostEqual(fin_scores[2], 0.2)


if __name__ == "__main__":
    unittest.main()
