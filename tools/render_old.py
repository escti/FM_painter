"""Renderiza o JSON 1000 do app original + metricas justas vs FM_Painter.

So LE o JSON antigo (nunca escreve la). Tudo novo vai para output/comparacao/.
Mesmo rasterizador numba pros dois lados (apples-to-apples).
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
from src.cpu_backend import full_error_nb
from src.render import save_preview

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_DIR = ("D:/users/thiag/downloads/forza/imagens_originais"
           "/efr_logo2_bg_off")
ORIG_PNG = ("D:/users/thiag/downloads/forza/imagens_originais"
            "/efr_logo2_bg_off.png")
V4_DIR = os.path.join(BASE, "output", "efr_logo2_bg_off_v4")


def load_shapes(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    shapes = d["shapes"]
    bg = shapes[0]
    # type:1 data [0,0,x1,y1] inclusivo -> tamanho x1+1
    W = int(bg["data"][2]) + 1
    H = int(bg["data"][3]) + 1
    out = []
    for s in shapes[1:]:
        if s["type"] != 16:
            continue
        cx, cy, rx, ry, ang = s["data"]
        r, g, b, a = s["color"]
        out.append((float(cx), float(cy), float(rx), float(ry), float(ang),
                    float(r), float(g), float(b), float(a)))
    return out, W, H, shapes[-1].get("score")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", default="1000",
                    help="sufixo do checkpoint (ex: 500, 1000, 3000). "
                         "'' = json final sem sufixo")
    ap.add_argument("--old", default=None)
    ap.add_argument("--v4", default=None)
    ap.add_argument("--v4dir", default=V4_DIR)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    n = a.n
    OLD_JSON = a.old or os.path.join(OLD_DIR, f"efr_logo2_bg_off.{n}.json")
    if n in ("", "final"):
        V4_JSON = a.v4 or os.path.join(a.v4dir, "efr_logo2_bg_off.json")
        tag = "final"
    else:
        V4_JSON = a.v4 or os.path.join(a.v4dir, f"efr_logo2_bg_off.{n}.json")
        tag = n
    OUT = a.out or os.path.join(BASE, "output", f"comparacao_{tag}")
    os.makedirs(OUT, exist_ok=True)
    # target NATIVO 1024 sem crop (metricas no canvas cheio)
    from PIL import Image as _I
    _im = _I.open(ORIG_PNG).convert("RGBA")
    _arr = np.array(_im)
    Hf, Wf = _arr.shape[:2]
    mask_f = _arr[:, :, 3] > 10
    target_f = _arr[:, :, :3].copy()
    target_f[~mask_f] = 0
    bg = np.array(target_f[mask_f].mean(axis=0).astype(np.uint8))
    print(f"[info] target nativo={Wf}x{Hf} opaco={mask_f.mean()*100:.1f}%")

    # --- lado antigo ---
    old_shapes, Wo, Ho, old_last_score = load_shapes(OLD_JSON)
    print(f"[info] antigo: {len(old_shapes)} shapes canvas={Wo}x{Ho} "
          f"last_score={old_last_score}")
    old_render = render_all(old_shapes, Wf, Hf, mask_f, bg)
    save_preview(old_render, mask_f, os.path.join(OUT, f"original_{tag}.png"))

    # --- lado v4 (reconstroi canvas cheio via crop offset) ---
    v4_shapes, Wv, Hv, v4_last = load_shapes(V4_JSON)
    # v4 foi gerado com crop; recupera o offset com a mesma resolucao
    t2, _, m2, s2 = load_target(ORIG_PNG, max_resolution=1024,
                                alpha_threshold=10)
    cx0, cy0, cx1, cy1 = s2["crop"]
    v4_full_c = render_all(v4_shapes, cx1 - cx0, cy1 - cy0, m2, bg)
    v4_full = np.zeros((Hf, Wf, 3), dtype=np.uint8) + 32
    v4_full[cy0:cy1, cx0:cx1] = v4_full_c
    save_preview(v4_full, mask_f, os.path.join(OUT, f"v4_{tag}.png"))

    # --- metricas (RMSE mascarado justo + cru) ---
    def rmse(a, b, m):
        d = a.astype(np.float32) - b.astype(np.float32)
        return float(np.sqrt((d[m] ** 2).mean() / (255.0 ** 2)))

    m_old = rmse(target_f, old_render, mask_f)
    m_v4 = rmse(target_f, v4_full, mask_f)
    ones = np.ones_like(mask_f, dtype=bool)
    m_old_raw = rmse(np.where(mask_f[:, :, None], target_f, 0),
                     np.where(mask_f[:, :, None], old_render, 0), ones)
    m_v4_raw = rmse(np.where(mask_f[:, :, None], target_f, 0),
                    np.where(mask_f[:, :, None], v4_full, 0), ones)

    from collections import Counter
    old_alphas = Counter(int(s[8]) for s in old_shapes)
    v4_alphas = Counter(int(s[8]) for s in v4_shapes)

    with open(os.path.join(OUT, "metricas.txt"), "w", encoding="utf-8") as f:
        f.write(f"shapes antigo: {len(old_shapes)} | v4: {len(v4_shapes)}\n")
        f.write(f"canvas antigo: {Wo}x{Ho} | v4 crop: {cx1-cx0}x{cy1-cy0} "
                f"offset=({cx0},{cy0})\n")
        f.write(f"score gravado antigo (ultimo shape): {old_last_score}\n")
        f.write(f"score gravado v4 (ultimo shape): {v4_last}\n")
        f.write(f"RMSE mascarado (transparente ignorado) antigo: {m_old:.5f}\n")
        f.write(f"RMSE mascarado (transparente ignorado) v4:     {m_v4:.5f}\n")
        f.write(f"RMSE cru (fundo=preto) antigo: {m_old_raw:.5f} | "
                f"v4: {m_v4_raw:.5f}\n")
        f.write(f"alphas antigo: {dict(sorted(old_alphas.items()))}\n")
        f.write(f"alphas v4: {dict(sorted(v4_alphas.items()))}\n")
    print(open(os.path.join(OUT, "metricas.txt"), encoding="utf-8").read())

    # --- lado a lado: original | antigo | v4 ---
    orig = Image.open(ORIG_PNG).convert("RGB").resize((Wf, Hf))
    a = Image.open(os.path.join(OUT, f"original_{tag}.png")).convert("RGB")
    b = Image.open(os.path.join(OUT, f"v4_{tag}.png")).convert("RGB")
    W3 = Wf * 3
    combo = Image.new("RGB", (W3, Hf + 40), (20, 20, 20))
    combo.paste(orig, (0, 40))
    combo.paste(a, (Wf, 40))
    combo.paste(b, (Wf * 2, 40))
    dr = ImageDraw.Draw(combo)
    no = len(old_shapes)
    nv = len(v4_shapes)
    dr.text((10, 10), "ORIGINAL", fill=(255, 255, 255))
    dr.text((Wf + 10, 10), f"APP ORIGINAL {no} (RMSE {m_old:.4f})",
            fill=(255, 255, 255))
    dr.text((Wf * 2 + 10, 10), f"FORZAPAINTER2 {nv} (RMSE {m_v4:.4f})",
            fill=(255, 255, 255))
    combo.save(os.path.join(OUT, "lado_a_lado.png"))
    print("[ok] lado_a_lado.png salvo")


if __name__ == "__main__":
    main()
