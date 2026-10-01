"""Candidatos [cx,cy,rx,ry,angle,alpha] com amostragem guiada por erro."""
import numpy as np

ALPHA_CHOICES = np.array([32, 64, 96, 128, 192, 255], dtype=np.float32)
ALPHA_PROBS = np.array([0.05, 0.10, 0.15, 0.20, 0.20, 0.30])


def opaque_bbox(mask):
    ys, xs = np.where(mask)
    return xs.min(), ys.min(), xs.max(), ys.max()


def error_tiles(target, current, mask, tile=64):
    """Mapa de erro medio por tile para guiar amostragem (foco em texto/borda)."""
    H, W = mask.shape
    d = target.astype(np.float32) - current.astype(np.float32)
    diff = np.zeros((H, W), dtype=np.float32)
    diff[mask] = (d[mask] ** 2).mean(axis=1)
    ty, tx = (H + tile - 1) // tile, (W + tile - 1) // tile
    w = np.zeros((ty, tx), dtype=np.float64)
    for i in range(ty):
        for j in range(tx):
            m = mask[i * tile:(i + 1) * tile, j * tile:(j + 1) * tile]
            if m.any():
                v = diff[i * tile:(i + 1) * tile, j * tile:(j + 1) * tile][m].mean() + 1.0
                w[i, j] = float(v) if np.isfinite(v) else 1.0
    s = w.sum()
    if not np.isfinite(s) or s <= 0:
        w[:] = 1.0 / w.size
    else:
        w /= s
    return w


def _sample_alpha(rng, n, opaque_only=False):
    if opaque_only:
        return np.full(n, 255.0, dtype=np.float32)
    return rng.choice(ALPHA_CHOICES, size=n, p=ALPHA_PROBS).astype(np.float32)


def radius_for_progress(progress, W, H, min_r=2):
    """Grosso->fino: comeco grande, fim pequeno (letra fina EFR)."""
    m = min(W, H)
    if progress < 0.3:
        return min_r, max(8, m // 2)
    if progress < 0.7:
        return min_r, max(8, m // 4)
    return 1, max(4, m // 8)


def random_candidates(n, W, H, mask, min_r=2, max_r_div=4, rng=None,
                      target=None, current=None, progress=0.5, guided=0.7,
                      opaque_only=True):
    rng = rng or np.random.default_rng()
    x0, y0, x1, y1 = opaque_bbox(mask)
    lo, hi = radius_for_progress(progress, W, H, min_r)
    # respeita max_r_div do profile como teto adicional
    hi = min(hi, max(4, min(W, H) // max_r_div)) if max_r_div else hi
    hi = max(hi, lo + 1)
    log_min, log_max = np.log(lo), np.log(hi)

    # tiles ponderados pelo erro (se disponivel)
    tiles = None
    if target is not None and current is not None and rng.random() < 0.95:
        try:
            tiles = error_tiles(target, current, mask)
        except Exception:
            tiles = None

    out = np.zeros((n, 6), dtype=np.float32)
    alphas = _sample_alpha(rng, n, opaque_only=opaque_only)
    made = 0
    guard = 0
    ty, tx = tiles.shape if tiles is not None else (0, 0)
    while made < n and guard < n * 30:
        guard += 1
        if tiles is not None and rng.random() < guided:
            ti = rng.choice(ty * tx, p=tiles.ravel())
            i, j = divmod(int(ti), tx)
            cx = rng.uniform(max(x0, j * 64), min(x1, (j + 1) * 64 - 1))
            cy = rng.uniform(max(y0, i * 64), min(y1, (i + 1) * 64 - 1))
        else:
            cx = rng.uniform(x0, x1)
            cy = rng.uniform(y0, y1)
        ix, iy = int(round(cx)), int(round(cy))
        if ix < 0 or iy < 0 or ix >= W or iy >= H or not mask[iy, ix]:
            continue
        rx = float(np.exp(rng.uniform(log_min, log_max)))
        ry = float(np.exp(rng.uniform(log_min, log_max)))
        ang = float(rng.uniform(0, 360))
        out[made] = (cx, cy, rx, ry, ang, float(alphas[made]))
        made += 1
    return out[:made]


def mutate_candidates(base, n, W, H, mask, rng=None, scale=0.15,
                      opaque_only=True):
    """Muta 1 dos 6 params (alpha fixo em 255 se opaque_only)."""
    rng = rng or np.random.default_rng()
    cx, cy, rx, ry, ang, alp = [float(x) for x in base]
    if opaque_only:
        alp = 255.0
    span = max(rx, ry, 8.0)
    out = np.zeros((n, 6), dtype=np.float32)
    for i in range(n):
        j = rng.integers(0, 6 if not opaque_only else 5)
        ncx, ncy, nrx, nry, nang, nalp = cx, cy, rx, ry, ang, alp
        if j == 0:
            ncx = cx + rng.normal(0, span * scale)
        elif j == 1:
            ncy = cy + rng.normal(0, span * scale)
        elif j == 2:
            nrx = max(1.0, rx * (1 + rng.normal(0, scale)))
        elif j == 3:
            nry = max(1.0, ry * (1 + rng.normal(0, scale)))
        elif j == 4:
            nang = (ang + rng.normal(0, 25)) % 360
        else:
            nalp = float(np.clip(alp + rng.normal(0, 40), 16, 255))
        ncx = min(max(ncx, 0), W - 1)
        ncy = min(max(ncy, 0), H - 1)
        out[i] = (ncx, ncy, nrx, nry, nang, nalp)
    return out
