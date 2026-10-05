"""Testes G7d: serializador exato do app antigo (round-trip byte a byte)."""
import os
import sys
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.oldexe import serialize_entries, shapes_to_entries, BG_COLOR

REF = ("D:/users/thiag/downloads/forza/imagens_originais/efr_logo2_bg_off"
       "/efr_logo2_bg_off.500.json")


class TestOldExeSerializer(unittest.TestCase):
    def test_exact_synthetic(self):
        entries = [
            (1, [0, 0, 1023, 1023], [255, 0, 255, 0], 0),
            (16, [546, 603, 423, 332, 281], [73, 56, 60, 255], 0.556274),
        ]
        text = serialize_entries(entries)
        self.assertEqual(
            text,
            '{"shapes":\r\n['
            '{"type":1, "data":[0,0,1023,1023],"color":[255,0,255,0],'
            '"score":0},\r\n'
            '{"type":16, "data":[546,603,423,332,281],'
            '"color":[73,56,60,255],"score":0.556274}\r\n]}')

    def test_bg_is_w_minus_1(self):
        ent = shapes_to_entries([(10, 10, 3, 3, 0, 1, 2, 3, 255)], 1024, 1024)
        self.assertEqual(ent[0][1], [0, 0, 1023, 1023])
        self.assertEqual(ent[0][2], list(BG_COLOR))

    def test_total_counts_bg(self):
        shapes = [(i, i, 2, 2, 0, 1, 2, 3, 255) for i in range(10)]
        ent = shapes_to_entries(shapes, 1024, 1024, total=5)
        self.assertEqual(len(ent), 5)  # 1 bg + 4 shapes

    @unittest.skipUnless(os.path.exists(REF), "referencia ausente")
    def test_roundtrip_reference_bytes(self):
        raw = open(REF, "rb").read().decode("utf-8")
        d = json.loads(raw)
        entries = [(s["type"], s["data"], s["color"], s.get("score", 0))
                   for s in d["shapes"]]
        self.assertEqual(serialize_entries(entries), raw)


if __name__ == "__main__":
    unittest.main()
