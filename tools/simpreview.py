"""Simpreview sem mascara (G1, item 9d). Obrigatorio em todo entregavel.

O jogo NAO tem mascara: elipses pintam sobre a area "transparente" (que
in-game mostra a pintura do carro). Este preview aplica os shapes IGNORANDO
a mascara sobre um backdrop cinza — o spill (B1) aparece como tinta sobre
cinza. O cinza e SO backdrop, nunca entra no JSON (sem bloco cinza no carro).

Uso: python tools/simpreview.py <in.json> [--out <png>] [--bg R,G,B]
     python tools/simpreview.py <in.json> --image <png-fonte> (metricas spill)
"""
import os
import sys
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.post import render_all

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PNG = ("D:/users/thiag/downloads/forza/imagens_originais"
               "/efr_logo2_bg_off.png")


def load_all(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    shapes = d["shapes"]
    bg = shapes[0] if shapes and shapes[0].get("type") == 1 else None
    if bg is not None:
        W, H = int(bg["data"][2]), int(bg["data"][3])
    else:
        W = H = 0
        for s in shapes:
            if s.get("type") == 1 or s.get("hidden"):
                continue
            dd = s.get("data", [0, 0, 0, 0, 0])
            W = max(W, int(dd[0] + dd[2]))
            H = max(H, int(dd[1] + dd[3]))
    out = []
    for s in shapes:
        if s.get("type") != 16 or s.get("hidden"):
            continue  # type:1 e placeholder: nunca sao tinta
        cx, cy, rx, ry, ang = [float(v) for v in s["data"][:5]]
        c = [float(v) for v in s["color"][:4]]
        while len(c) < 4:
            c.append(255.0)
        out.append((cx, cy, rx, ry, ang, c[0], c[1], c[2], c[3]))
    return out, W, H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    ap.add_argument("--bg", default="160,160,160",
                    help="backdrop (pintura do carro), default cinza 160")
    ap.add_argument("--image", default=None,
                    help="PNG fonte p/ metrica de spill (opcional)")
    a = ap.parse_args()

    gray = tuple(int(x) for x in a.bg.split(","))
    shapes, W, H = load_all(a.input)
    print(f"[sim] {a.input}: {len(shapes)} desenhaveis canvas={W}x{H} "
          f"backdrop={gray} (backdrop nao e shape)")

    nomask = np.ones((H, W), dtype=np.bool_)
    bg_arr = np.array(gray, dtype=np.uint8)
    full = render_all(shapes, W, H, nomask, bg_arr)

    dst = a.out or os.path.join(
        BASE, "output", "simpreview",
        os.path.splitext(os.path.basename(a.input))[0] + ".nomask.png")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    from PIL import Image
    Image.fromarray(full).save(dst)
    print(f"[ok] preview sem mascara em {dst}")

    if a.image:
        from src.image import load_target
        target, _, mask, stats = load_target(
            a.image, max_resolution=max(W, H), alpha_threshold=10)
        x0, y0, x1, y1 = stats["crop"]
        if (x1 - x0, y1 - y0) == (W, H):
            diff = full.astype(np.int16) - np.asarray(gray, dtype=np.int16)
            painted = np.abs(diff).sum(axis=2) > 0
            spill = int((painted & ~mask).sum())
            n_transp = int((~mask).sum())
            print(f"[spill] pixels de tinta sobre transparente: {spill} "
                  f"({100.0 * spill / max(1, n_transp):.2f}% da area transparente)")
            if spill > 0:
                print("[spill] FALHA — voltar p/ melhorias.md#9, nao entregar.")
        else:
            print(f"[spill] canvas {W}x{H} != work {x1-x0}x{y1-y0}: "
                  f"metrica pulada (use JSON full-canvas ou work recortado)")


if __name__ == "__main__":
    main()
