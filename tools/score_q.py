"""score_q.py — Q-offline: metricas fieis p/ comparar JSONs de vinil.

Motivo (melhorias.md item 15): o RMSE mascarado ordena errado (premia gigante
borrado e ignora spill). Aqui medimos 5 metricas com o MESMO rasterizador
(`src/post.py:render_all`) e um Q composto calibrado p/ reproduzir o ranking
visual do dono: antigo < KFPS < nosso (menor = melhor).

Metricas:
  RMSE_mask  erro L2 nos pixels opacos (o que ja tinhamos)
  SSIM_mask  similaridade estrutural (luminancia) nos opacos
  EdgeRMSE   RMSE so nos 15% pixels de maior Sobel no interior erodido (texto)
  Spill%     tinta sobre transparente (simpreview mask-off)
  LabMAE     erro medio absoluto em CIELAB (perceptual de cor)

Uso: python tools/score_q.py [--jobs antigo,kfps,nosso] [--out output/q]
"""
import os
import sys
import json
import argparse

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.post import render_all
from src.edgeweight import _erode

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = ("D:/users/thiag/downloads/forza/imagens_originais"
        "/efr_logo2_bg_off.png")
JOBS = {
    "antigo": ("D:/users/thiag/downloads/forza/imagens_originais"
               "/efr_logo2_bg_off/efr_logo2_bg_off.500.json", (0, 0)),
    "kfps": ("D:/users/thiag/downloads/forza/KFPS-3.1.91/KloudysFH6Painter"
             "/imgs/generated/efr_logo2_bg_off-c924ecde9267/finals"
             "/efr_logo2_bg_off.500v2.json", (0, 0)),
    "nosso_v11": (os.path.join(BASE, "output", "efr_logo2_bg_off_v11_400k",
                               "efr_logo2_bg_off.json"), (0, 4)),
    "nosso_v12": (os.path.join(BASE, "output", "efr_logo2_bg_off_v12_nospill",
                               "efr_logo2_bg_off.json"), (0, 4)),
}


def load_shapes(path, off):
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
        out.append((cx + off[0], cy + off[1], rx, ry, ang,
                    c[0], c[1], c[2], c[3]))
    return out


def sobel_mag(rgb):
    lum = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1]
           + 0.114 * rgb[:, :, 2]).astype(np.float32)
    gx = np.zeros_like(lum)
    gy = np.zeros_like(lum)
    gx[:, 1:-1] = lum[:, 2:] - lum[:, :-2]
    gy[1:-1, :] = lum[2:, :] - lum[:-2, :]
    return np.sqrt(gx * gx + gy * gy)


def _boxmean(x, k):
    p = k // 2
    xp = np.pad(x, p, mode="reflect")
    c = np.cumsum(np.cumsum(xp, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    H, W = x.shape
    s = (c[k:k + H, k:k + W] - c[0:H, k:k + W]
         - c[k:k + H, 0:W] + c[0:H, 0:W])
    return s / (k * k)


def ssim_masked(target_rgb, cur_rgb, mask, k=7):
    x = (0.299 * target_rgb[:, :, 0] + 0.587 * target_rgb[:, :, 1]
         + 0.114 * target_rgb[:, :, 2]).astype(np.float64)
    y = (0.299 * cur_rgb[:, :, 0] + 0.587 * cur_rgb[:, :, 1]
         + 0.114 * cur_rgb[:, :, 2]).astype(np.float64)
    ux, uy = _boxmean(x, k), _boxmean(y, k)
    uxx = _boxmean(x * x, k) - ux * ux
    uyy = _boxmean(y * y, k) - uy * uy
    uxy = _boxmean(x * y, k) - ux * uy
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    s = ((2 * ux * uy + C1) * (2 * uxy + C2)) / \
        ((ux * ux + uy * uy + C1) * (uxx + uyy + C2))
    return float(np.clip(s[mask].mean(), -1, 1))


def _srgb_to_lab(rgb):
    a = rgb.astype(np.float64) / 255.0
    a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = a @ M.T
    xyz[:, :, 0] /= 0.95047
    xyz[:, :, 1] /= 1.0
    xyz[:, :, 2] /= 1.08883
    d = 6 / 29
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4 / 29)
    L = 116 * f[:, :, 1] - 16
    A = 500 * (f[:, :, 0] - f[:, :, 1])
    B = 200 * (f[:, :, 1] - f[:, :, 2])
    return np.stack([L, A, B], axis=2)


def lab_mae(target_rgb, cur_rgb, mask):
    lt = _srgb_to_lab(target_rgb)
    lc = _srgb_to_lab(cur_rgb)
    return float(np.abs(lt - lc)[mask].mean())


def evaluate(target, mask, shapes, bg, W, H, erode_px=8):
    cur = render_all(shapes, W, H, mask, bg)
    d = cur.astype(np.float32) - target.astype(np.float32)
    rmse = float(np.sqrt((d[mask] ** 2).mean() / (255.0 ** 2)))
    ssim = ssim_masked(target, cur, mask)
    # EdgeRMSE
    em = _erode(mask, erode_px)
    if em.any():
        sob = sobel_mag(target)
        vals = sob[em]
        thr = np.percentile(vals, 85)
        e = em & (sob >= thr)
        edge_rmse = float(np.sqrt((d[e] ** 2).mean() / (255.0 ** 2)))
    else:
        edge_rmse = 0.0
    # Spill% (mask-off)
    nomask = np.ones((H, W), dtype=bool)
    gray = np.array([160, 160, 160], np.uint8)
    full = render_all(shapes, W, H, nomask, gray)
    painted = np.abs(full.astype(np.int16) - gray).sum(axis=2) > 0
    ntrans = int((~mask).sum())
    spill = 100.0 * float((painted & ~mask).sum()) / max(1, ntrans)
    lab = lab_mae(target, cur, mask)
    return dict(rmse=rmse, ssim=ssim, edge=edge_rmse, spill=spill, lab=lab)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default="antigo,kfps,nosso_v11")
    ap.add_argument("--out", default=os.path.join(BASE, "output", "q"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    arr = np.array(Image.open(ORIG).convert("RGBA"))
    H, W = arr.shape[:2]
    mask = arr[:, :, 3] > 10
    target = arr[:, :, :3].copy()
    target[~mask] = 0
    bg = np.array(target[mask].mean(axis=0).astype(np.uint8))

    rows = []
    for name in a.jobs.split(","):
        name = name.strip()
        if name not in JOBS:
            continue
        path, off = JOBS[name]
        if not os.path.exists(path):
            print(f"[q] ausente: {name} {path}")
            continue
        shapes = load_shapes(path, off)
        m = evaluate(target, mask, shapes, bg, W, H)
        rows.append((name, m))
        print(f"[q] {name:10s} rmse={m['rmse']:.5f} ssim={m['ssim']:.4f} "
              f"edge={m['edge']:.5f} spill={m['spill']:.2f}% lab={m['lab']:.2f}")

    # Q provisorio: spill domina (o jogo ve), depois cor/estrutura
    def Q(m):
        return (m["rmse"] * 100.0 + (1 - m["ssim"]) * 40.0
                + m["edge"] * 100.0 + m["spill"] * 1.0 + m["lab"] * 0.5)

    rows.sort(key=lambda r: Q(r[1]))
    with open(os.path.join(a.out, "metricas.txt"), "w", encoding="utf-8") as f:
        f.write("name rmse ssim edge spill% lab Q\n")
        for name, m in rows:
            f.write(f"{name} {m['rmse']:.5f} {m['ssim']:.4f} "
                    f"{m['edge']:.5f} {m['spill']:.2f} {m['lab']:.2f} "
                    f"{Q(m):.3f}\n")
    print("[q] ranking por Q (menor=melhor):",
          " < ".join(n for n, _ in rows))
    print(f"[q] metricas em {a.out}/metricas.txt")


if __name__ == "__main__":
    main()
