"""Autopsia do nosso 500 (G4, item 7, escopo: so o nosso JSON).

So leitura + renders diagnosticos, nunca altera JSON:
- distribuicao area/aspecto/angulo
- ganho marginal por bloco (curva erro x indice, passo 25)
- densidade espacial centros-vs-erro residual (tiles 128)
- paleta usada (cores exatas mais frequentes)
- top-10 gigantes (pista do B1 spill)
Uso: python tools/autopsy.py [--step 25]
Saida: output/autopsy_500/resumo.txt + curva.csv (console espelha o resumo)
"""
import os
import sys
import json
import argparse
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.image import load_target
from src.post import render_all
from src.cpu_backend import full_error_nb

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_JSON = os.path.join(
    BASE, "output", "efr_logo2_bg_off_v4_3000", "efr_logo2_bg_off.500.json")
DEFAULT_PNG = ("D:/users/thiag/downloads/forza/imagens_originais"
               "/efr_logo2_bg_off.png")
OUTDIR = os.path.join(BASE, "output", "autopsy_500")


def load_shapes(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    out = []
    for s in d["shapes"]:
        if s.get("type") != 16 or s.get("hidden"):
            continue
        cx, cy, rx, ry, ang = [float(v) for v in s["data"][:5]]
        c = [float(v) for v in s["color"][:4]]
        while len(c) < 4:
            c.append(255.0)
        out.append((cx, cy, rx, ry, ang, c[0], c[1], c[2], c[3]))
    return out


def pct(a, q):
    return float(np.percentile(np.asarray(a, dtype=np.float64), q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--image", default=DEFAULT_PNG)
    ap.add_argument("--step", type=int, default=25)
    ap.add_argument("--tile", type=int, default=128)
    a = ap.parse_args()

    shapes = load_shapes(a.json)
    n = len(shapes)
    print(f"[autopsy] {a.json} shapes={n}")
    assert n == 500, f"esperava 500, achei {n}"

    target, _, mask, stats = load_target(
        a.image, max_resolution=1024, alpha_threshold=10)
    H, W = mask.shape
    bg = np.array(stats["avg_color"], dtype=np.uint8)

    arr = np.asarray(shapes, dtype=np.float64)
    cx, cy, rx, ry, ang = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
    area = np.pi * np.maximum(rx, 1.0) * np.maximum(ry, 1.0)
    asp = np.maximum(rx, ry) / np.maximum(1.0, np.minimum(rx, ry))

    # curva erro x indice (render incremental)
    steps = list(range(0, n + 1, a.step))
    if steps[-1] != n:
        steps.append(n)
    curve = []
    for k in steps:
        cur = render_all(shapes[:k], W, H, mask, bg)
        e = float(full_error_nb(target, cur, mask, W, H))
        curve.append((k, e))

    # residual final por tile vs densidade de centros
    final = render_all(shapes, W, H, mask, bg)
    d = (target.astype(np.float32) - final.astype(np.float32)) ** 2
    t = a.tile
    ty, tx = (H + t - 1) // t, (W + t - 1) // t
    rows = []
    for i in range(ty):
        for j in range(tx):
            m = mask[i * t:(i + 1) * t, j * t:(j + 1) * t]
            if not m.any():
                continue
            resid = float(d[i * t:(i + 1) * t, j * t:(j + 1) * t][m].mean()
                          / (255.0 ** 2))
            cnt = int(((cx >= j * t) & (cx < (j + 1) * t) &
                       (cy >= i * t) & (cy < (i + 1) * t)).sum())
            rows.append((i, j, cnt, resid))
    rows.sort(key=lambda r: -r[3])

    pal = Counter((int(r), int(g), int(b))
                  for _, _, _, _, _, r, g, b, _ in shapes)
    top_colors = pal.most_common(15)

    order_area = np.argsort(-area)[:10]
    giants = [(int(i), float(cx[i]), float(cy[i]), float(rx[i]), float(ry[i]),
               float(area[i])) for i in order_area]

    # correlacao simples densidade x residual
    cc = np.corrcoef([r[2] for r in rows], [r[3] for r in rows])[0, 1] \
        if len(rows) > 2 else float("nan")

    L = []
    L.append(f"shapes={n} work={W}x{H} crop={stats['crop']}")
    L.append(f"area px: p50={pct(area,50):.0f} p90={pct(area,90):.0f} "
             f"p99={pct(area,99):.0f} max={area.max():.0f}")
    L.append(f"aspecto max/min: p50={pct(asp,50):.2f} p90={pct(asp,90):.2f} "
             f"max={asp.max():.2f}")
    L.append(f"angulo: media={ang.mean():.1f} (uniforme esperado ~180)")
    L.append("curva erro x indice (bloco de %d):" % a.step)
    for (k0, e0), (k1, e1) in zip(curve[:-1], curve[1:]):
        L.append(f"  {k0:4d}->{k1:4d}: {e0:.5f}->{e1:.5f} "
                 f"ganho={e0-e1:+.5f}")
    L.append(f"tiles {t}px: correlacao(densidade, residual)={cc:.3f}")
    L.append("top-5 tiles por residual (ti,tj,n_shapes,resid):")
    for i, j, c, r in rows[:5]:
        L.append(f"  ({i},{j}) n={c} resid={r:.5f}")
    L.append("paleta top-15 (rgb:qtd):")
    for (r, g, b), q in top_colors:
        L.append(f"  ({r},{g},{b}):{q}")
    L.append("top-10 gigantes idx,cx,cy,rx,ry,area (pista B1):")
    for i, x, y, rxa, rya, ar in giants:
        L.append(f"  {i}: ({x:.0f},{y:.0f}) {rxa:.0f}x{rya:.0f} area={ar:.0f}")

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "resumo.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(OUTDIR, "curva.csv"), "w", encoding="utf-8") as f:
        f.write("k,rmse\n")
        for k, e in curve:
            f.write(f"{k},{e:.6f}\n")
    print("\n".join(L))
    print(f"[ok] {OUTDIR}/resumo.txt + curva.csv")


if __name__ == "__main__":
    main()
