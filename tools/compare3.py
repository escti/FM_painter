"""Comparativo a 3: app original vs FM_Painter vs KFPS. Mesma metrica p/ todos.

Uso: python tools/compare3.py --n 500|1000|3000
Saida: output/comparacao3_<n>/{antigo,v2,kfps}_<n>.png, lado_a_lado.png, metricas.txt
"""
import os
import sys
import json
import argparse

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.image import load_target
from src.post import render_all
from src.render import save_preview

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_DIR = ("D:/users/thiag/downloads/forza/imagens_originais"
           "/efr_logo2_bg_off")
ORIG_PNG = ("D:/users/thiag/downloads/forza/imagens_originais"
            "/efr_logo2_bg_off.png")
V4_3000 = os.path.join(BASE, "output", "efr_logo2_bg_off_v4_3000")
KFPS = ("D:/users/thiag/downloads/forza/KFPS-3.1.91/KloudysFH6Painter"
        "/imgs/generated/efr_logo2_bg_off-c924ecde9267/finals")


def load_any(path):
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


def rmse(a, b, m):
    d = a.astype(np.float32) - b.astype(np.float32)
    return float(np.sqrt((d[m] ** 2).mean() / (255.0 ** 2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", required=True, choices=["500", "1000", "3000"])
    a = ap.parse_args()
    n = a.n
    OUT = os.path.join(BASE, "output", f"comparacao3_{n}")
    os.makedirs(OUT, exist_ok=True)

    from PIL import Image as _I
    _arr = np.array(_I.open(ORIG_PNG).convert("RGBA"))
    Hf, Wf = _arr.shape[:2]
    mask = _arr[:, :, 3] > 10
    target = _arr[:, :, :3].copy()
    target[~mask] = 0
    bg = np.array(target[mask].mean(axis=0).astype(np.uint8))

    jobs = {
        "antigo": os.path.join(OLD_DIR, f"efr_logo2_bg_off.{n}.json"),
        "v2": os.path.join(V4_3000, f"efr_logo2_bg_off.{n}.json")
        if n in ("500", "1000") else os.path.join(V4_3000, "efr_logo2_bg_off.json"),
        "kfps": os.path.join(KFPS, f"efr_logo2_bg_off.{n}v2.json"),
    }
    results = {}
    for name, path in jobs.items():
        shapes = load_any(path)
        # nosso v2 usa espaco com crop: reconstroi canvas cheio
        if name == "v2":
            _, _, m2, s2 = load_target(ORIG_PNG, max_resolution=1024,
                                       alpha_threshold=10)
            x0, y0, x1, y1 = s2["crop"]
            part = render_all(shapes, x1 - x0, y1 - y0, m2, bg)
            full = np.zeros((Hf, Wf, 3), dtype=np.uint8) + 32
            full[y0:y1, x0:x1] = part
        else:
            full = render_all(shapes, Wf, Hf, mask, bg)
        e = rmse(target, full, mask)
        results[name] = (len(shapes), e)
        save_preview(full, mask, os.path.join(OUT, f"{name}_{n}.png"))
        print(f"[{name}] shapes={len(shapes)} RMSE={e:.5f}")

    with open(os.path.join(OUT, "metricas.txt"), "w", encoding="utf-8") as f:
        for name in ("antigo", "v2", "kfps"):
            c, e = results[name]
            f.write(f"{name}: shapes={c} RMSE={e:.5f}\n")

    orig = _I.open(ORIG_PNG).convert("RGB").resize((Wf, Hf))
    imgs = [orig] + [_I.open(os.path.join(OUT, f"{k}_{n}.png")).convert("RGB")
                     for k in ("antigo", "v2", "kfps")]
    combo = Image.new("RGB", (Wf * 4, Hf + 40), (20, 20, 20))
    labels = ["ORIGINAL"] + [
        f"{k.upper()} {results[k][0]} (RMSE {results[k][1]:.4f})"
        for k in ("antigo", "v2", "kfps")]
    for i, im in enumerate(imgs):
        combo.paste(im, (Wf * i, 40))
    dr = ImageDraw.Draw(combo)
    for i, lb in enumerate(labels):
        dr.text((Wf * i + 10, 10), lb, fill=(255, 255, 255))
    combo.save(os.path.join(OUT, "lado_a_lado.png"))
    print("[ok] lado_a_lado.png salvo")


if __name__ == "__main__":
    main()
