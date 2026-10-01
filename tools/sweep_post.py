"""Sweep de pos 0/1/2/3 sobre o 500 ja salvo (G4, item 6).

So pos, sem regenerar: carrega o .500, roda post_process(passes=P) a partir
da mesma base para cada P, mede RMSE mascarado com o mesmo rasterizador
(full_error_nb) e salva em output/sweep_post_500/ (nao toca nos checkpoints,
evita B3). N sempre preservado (contrato de template).
Uso: python tools/sweep_post.py [--passes 0,1,2,3]
"""
import os
import sys
import time
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.image import load_target
from src.post import post_process, render_all
from src.cpu_backend import full_error_nb
from src.generator import dump_json
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_JSON = os.path.join(
    BASE, "output", "efr_logo2_bg_off_v4_3000", "efr_logo2_bg_off.500.json")
DEFAULT_PNG = ("D:/users/thiag/downloads/forza/imagens_originais"
               "/efr_logo2_bg_off.png")
OUTDIR = os.path.join(BASE, "output", "sweep_post_500")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--image", default=DEFAULT_PNG)
    ap.add_argument("--passes", default="0,1,2,3")
    ap.add_argument("--post-mutations", type=int, default=100)
    ap.add_argument("--tol", type=float, default=0.0002)
    a = ap.parse_args()

    passes_list = [int(x) for x in a.passes.split(",") if x.strip().isdigit()]
    base_shapes = load_shapes(a.json)
    n0 = len(base_shapes)
    print(f"[sweep] base={a.json} shapes={n0}")
    assert n0 == 500, f"esperava 500 shapes, achei {n0}"

    target, _, mask, stats = load_target(
        a.image, max_resolution=1024, alpha_threshold=10)
    H, W = mask.shape
    bg = np.array(stats["avg_color"], dtype=np.uint8)
    print(f"[sweep] work={W}x{H} crop={stats['crop']} "
          f"transp={stats['pct_transparente']:.1f}%")

    # erro base (passes=0) sem pos
    os.makedirs(OUTDIR, exist_ok=True)
    results = []
    for p in passes_list:
        shapes = list(base_shapes)
        t0 = time.time()
        if p > 0:
            shapes = post_process(shapes, target, mask, bg, passes=p,
                                  post_mutations=a.post_mutations,
                                  tol=a.tol, opaque_only=True)
        assert len(shapes) == n0, "pos nunca pode mudar a contagem"
        cur = render_all(shapes, W, H, mask, bg)
        err = float(full_error_nb(target, cur, mask, W, H))
        dt = time.time() - t0
        results.append((p, err, dt))
        print(f"[sweep] passes={p} err={err:.5f} t={dt:.0f}s (N={len(shapes)})")
        # salva refinado em dir separada (nao sobrescreve checkpoints -> B3)
        scores = [err] * len(shapes)
        dump_json(OUTDIR, "efr_logo2_bg_off", W, H, shapes, scores,
                  suffix=f".sweep{p}")

    with open(os.path.join(OUTDIR, "metricas.txt"), "w", encoding="utf-8") as f:
        for p, err, dt in results:
            f.write(f"passes={p} RMSE={err:.5f} t={dt:.0f}s N={n0}\n")
    print(f"[ok] metricas em {OUTDIR}/metricas.txt")


if __name__ == "__main__":
    main()
