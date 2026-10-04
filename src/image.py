"""Carregamento com suporte a PNG sem fundo (alpha).

Economia: pixels 100% transparentes sao mascarados (peso 0 no score).
O gerador nao gasta shapes pintando fundo — vai direto para capacete,
chamas, asas e texto EFR.
"""
import numpy as np
from PIL import Image


def _quantize_masked(target, mask, K, seed=0, iters=15, cap=200000):
    """k-means (numpy) so nos pixels opacos; mapeia todos. Sem dithering."""
    px = target[mask].astype(np.float32)
    n = len(px)
    if n == 0:
        return target.copy()
    rng = np.random.default_rng(seed)
    sub = px if n <= cap else px[rng.choice(n, cap, replace=False)]
    K = int(max(1, min(K, len(np.unique(sub, axis=0)))))
    cent = sub[rng.choice(len(sub), K, replace=False)].copy()
    for _ in range(int(iters)):
        d = ((sub[:, None, :] - cent[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1)
        new = cent.copy()
        for k in range(K):
            m = lab == k
            if m.any():
                new[k] = sub[m].mean(0)
        if np.abs(new - cent).max() < 0.5:
            cent = new
            break
        cent = new
    out = target.copy()
    lab = np.empty(n, dtype=np.int64)
    step = 100000
    for i in range(0, n, step):
        chunk = px[i:i + step]
        dd = ((chunk[:, None, :] - cent[None, :, :]) ** 2).sum(2)
        lab[i:i + step] = dd.argmin(1)
    out[mask] = np.clip(cent[lab], 0, 255).astype(np.uint8)
    return out


def load_target(path, max_resolution=1024, alpha_threshold=10, luma_bands=0,
                palette_colors=0):
    im = Image.open(path).convert("RGBA")
    ow, oh = im.size

    # downscale proporcional se maior que maxResolution (lado maior)
    scale = 1.0
    m = max(ow, oh)
    if m > max_resolution:
        scale = max_resolution / m
        nw, nh = int(ow * scale), int(oh * scale)
        im = im.resize((nw, nh), Image.LANCZOS)
    else:
        nw, nh = ow, oh

    arr = np.array(im)  # H,W,4 uint8
    alpha = arr[:, :, 3]
    mask = alpha > alpha_threshold  # True = opaco / semi -> conta no score

    # autocrop na bbox opaca + 1px de borda (igual enforcement do antigo)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("imagem totalmente transparente")
    x0, x1 = max(0, xs.min() - 1), min(nw, xs.max() + 2)
    y0, y1 = max(0, ys.min() - 1), min(nh, ys.max() + 2)
    arr = arr[y0:y1, x0:x1]
    mask = mask[y0:y1, x0:x1]
    h, w = mask.shape

    target = arr[:, :, :3].copy()  # RGB
    # zera RGB onde transparente para nao contaminar medias
    target[~mask] = 0

    if luma_bands and luma_bands > 0:
        # G2/12 Luma Prep opt-in (docs KFPS): posteriza a luminancia em B
        # faixas preservando o matiz. Para regioes chapadas/stickers; o
        # proprio manual manda DESLIGAR p/ arte sombreada (ex. EFR).
        lum = (0.299 * target[:, :, 0].astype(np.float32)
               + 0.587 * target[:, :, 1].astype(np.float32)
               + 0.114 * target[:, :, 2].astype(np.float32))
        B = int(luma_bands)
        band = ((np.floor(lum * B / 256.0) + 0.5) * 255.0 / B)
        scale = np.ones_like(lum)
        nz = lum > 1e-6
        scale[nz] = band[nz] / lum[nz]
        target = np.clip(target.astype(np.float32) * scale[:, :, None],
                         0, 255).astype(np.uint8)
        target[~mask] = 0

    if palette_colors and palette_colors > 0:
        # G6c: quantiza a paleta (k-means SO nos pixels opacos) p/ reduzir o
        # "color mean error" (LIVE/CVPR22): regioes viram chapadas de cor real.
        target[~mask] = 0
        target = _quantize_masked(target, mask, int(palette_colors))
        target[~mask] = 0

    # cor inicial = media dos opacos (como geometrize faz com average)
    if mask.any():
        avg = target[mask].mean(axis=0).astype(np.uint8)
    else:
        avg = np.array([0, 0, 0], dtype=np.uint8)
    current = np.zeros_like(target)
    current[:, :] = avg

    stats = {
        "orig_size": (ow, oh),
        "work_size": (w, h),
        "crop": (x0, y0, x1, y1),
        "pct_transparente": float((~mask).mean() * 100),
        "pct_opaco": float(mask.mean() * 100),
        "avg_color": avg.tolist(),
    }
    return target, current, mask, stats
