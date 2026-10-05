"""Converte um JSON nosso (coords recortadas, ints) -> formato EXATO do app
antigo (FH5), pronto para importar. Ver `src/oldexe.py`.

Uso:
  python tools/to_old_exe.py <nosso.json> --out <out.json> \
      --orig-w 1024 --orig-h 1024 --off 0,4 --total 500
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.oldexe import write_old_exe

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    shapes, scores = [], []
    for s in d["shapes"]:
        if s.get("type") != 16 or s.get("hidden"):
            continue
        cx, cy, rx, ry, ang = [float(v) for v in s["data"][:5]]
        c = [float(v) for v in s["color"][:4]]
        while len(c) < 4:
            c.append(255.0)
        shapes.append((cx, cy, rx, ry, ang, c[0], c[1], c[2], c[3]))
        scores.append(s.get("score", 0))
    return shapes, scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    ap.add_argument("--orig-w", type=int, default=1024)
    ap.add_argument("--orig-h", type=int, default=1024)
    ap.add_argument("--off", default="0,0", help="offset do crop x,y")
    ap.add_argument("--total", type=int, default=None,
                    help="camadas do template (entries totais; fundo conta)")
    ap.add_argument("--bg", default="first", choices=["first", "last", "none"],
                    help="posicao do fundo type:1 (testes de import)")
    a = ap.parse_args()

    ox, oy = (int(v) for v in a.off.split(","))
    shapes, scores = load(a.input)
    out = a.out or os.path.join(
        BASE, "output", "for_old_exe",
        os.path.splitext(os.path.basename(a.input))[0] + ".exact.json")
    write_old_exe(out, shapes, a.orig_w, a.orig_h, off=(ox, oy),
                  total=a.total, scores=scores, bg=a.bg)
    if a.bg == "none":
        n = len(shapes) if a.total is None else min(len(shapes), a.total)
        extra = "sem fundo"
    else:
        n = len(shapes) if a.total is None else min(len(shapes), a.total - 1)
        extra = f"1 bg ({a.bg})"
    print(f"[ok] {a.input} -> {out}")
    print(f"[ok] entries={n + (0 if a.bg == 'none' else 1)} "
          f"({extra} + {n} shapes) orig={a.orig_w}x{a.orig_h} off=({ox},{oy})")


if __name__ == "__main__":
    main()
