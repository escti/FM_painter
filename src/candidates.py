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


def _clamp_aspect(rx, ry, max_aspect):
    """G2: teto de aspecto (0=off). Encolhe o maior eixo p/ menor*A."""
    if max_aspect and max_aspect > 0:
        major, minor = (rx, ry) if rx >= ry else (ry, rx)
        if minor >= 1.0 and major / minor > max_aspect:
            major = minor * max_aspect
            rx, ry = (major, minor) if rx >= ry else (minor, major)
    return rx, ry


def _sample_centers(n, rng, x0, y0, x1, y1, W, H, mask, tiles, guided):
    """Centros validos (dentro da mascara), vetorizado, com redesenho."""
    cx = rng.uniform(x0, x1, n).astype(np.float64)
    cy = rng.uniform(y0, y1, n).astype(np.float64)
    if tiles is not None and guided > 0:
        gsel = rng.random(n) < guided
        ng = int(gsel.sum())
        if ng:
            ty, tx = tiles.shape
            ti = rng.choice(ty * tx, size=ng, p=tiles.ravel())
            i, j = np.divmod(ti, tx)
            lox = np.maximum(x0, j * 64).astype(np.float64)
            hix = np.minimum(x1, (j + 1) * 64 - 1).astype(np.float64)
            loy = np.maximum(y0, i * 64).astype(np.float64)
            hiy = np.minimum(y1, (i + 1) * 64 - 1).astype(np.float64)
            cx[gsel] = lox + rng.random(ng) * (hix - lox)
            cy[gsel] = loy + rng.random(ng) * (hiy - loy)
    for _ in range(12):
        ix = np.rint(cx).astype(np.int64)
        iy = np.rint(cy).astype(np.int64)
        inside = (ix >= 0) & (iy >= 0) & (ix < W) & (iy < H)
        bad = ~inside
        if inside.any():
            bad[inside] = ~mask[iy[inside], ix[inside]]
        if not bad.any():
            break
        nb = int(bad.sum())
        cx[bad] = rng.uniform(x0, x1, nb)
        cy[bad] = rng.uniform(y0, y1, nb)
    ix = np.rint(cx).astype(np.int64)
    iy = np.rint(cy).astype(np.int64)
    ok = (ix >= 0) & (iy >= 0) & (ix < W) & (iy < H)
    if ok.any():
        ok[ok] = mask[iy[ok], ix[ok]]
    return cx[ok], cy[ok]


def random_candidates(n, W, H, mask, min_r=2, max_r_div=4, rng=None,
                      target=None, current=None, progress=0.5, guided=0.7,
                      opaque_only=True, fit_inside=False, max_aspect=0.0,
                      late_share=0.0, late_start=0.5, detail_max_r=4,
                      big_first_frac=0.0):
    rng = rng or np.random.default_rng()
    x0, y0, x1, y1 = opaque_bbox(mask)
    lo, hi = radius_for_progress(progress, W, H, min_r)
    # H2.1b: fase base (big-first) — piso de raio alto p/ criar washes grandes
    # (espelha o app antigo: %area 1os5 ~33%); so nos primeiros big_first_frac.
    if big_first_frac > 0.0 and progress < big_first_frac:
        lo = max(lo, min(W, H) // 8)
    # respeita max_r_div do profile como teto adicional
    hi = min(hi, max(4, min(W, H) // max_r_div)) if max_r_div else hi
    hi = max(hi, lo + 1)
    log_min, log_max = np.log(lo), np.log(hi)
    # G2/3+11: faixa pequena p/ a 2a metade (texto fino); sorteio por candidato
    late_on = (late_share > 0 and progress >= late_start)
    dlo, dhi = min(lo, 1), max(2, detail_max_r)
    dlog_min, dlog_max = np.log(dlo), np.log(dhi)

    # tiles ponderados pelo erro (se disponivel)
    tiles = None
    if target is not None and current is not None and rng.random() < 0.95:
        try:
            tiles = error_tiles(target, current, mask)
        except Exception:
            tiles = None

    cx, cy = _sample_centers(n, rng, x0, y0, x1, y1, W, H, mask, tiles,
                             guided)
    m = len(cx)
    if m == 0:
        return np.zeros((0, 6), dtype=np.float32)

    lmn = np.full(m, log_min, dtype=np.float64)
    lmx = np.full(m, log_max, dtype=np.float64)
    if late_on:
        late_sel = rng.random(m) < late_share
        lmn[late_sel] = dlog_min
        lmx[late_sel] = dlog_max
    rx = np.exp(rng.uniform(lmn, lmx))
    ry = np.exp(rng.uniform(lmn, lmx))
    ang = rng.uniform(0, 360, m)

    if max_aspect and max_aspect > 0:
        rx_major = rx >= ry
        major = np.where(rx_major, rx, ry)
        minor = np.where(rx_major, ry, rx)
        s = np.ones(m)
        over = (minor >= 1.0) & (major / minor > max_aspect)
        s[over] = (minor[over] * max_aspect) / major[over]
        rx = np.where(rx_major, rx * s, rx)
        ry = np.where(rx_major, ry, ry * s)

    keep = np.ones(m, dtype=bool)
    if fit_inside:
        ca = np.abs(np.cos(np.radians(ang)))
        sa = np.abs(np.sin(np.radians(ang)))
        ex = rx * ca + ry * sa
        ey = rx * sa + ry * ca
        lim = np.minimum(np.minimum(cx - x0, x1 - cx),
                         np.minimum(cy - y0, y1 - cy))
        keep = lim >= 1.0
        ratio = np.where(keep, np.maximum(ex, ey) / np.maximum(lim, 1.0), 0.0)
        f = np.where(ratio > 1.0, ratio, 1.0)
        rx = rx / f
        ry = ry / f

    cx, cy, rx, ry, ang = (cx[keep], cy[keep], rx[keep], ry[keep], ang[keep])
    m = len(cx)
    if m == 0:
        return np.zeros((0, 6), dtype=np.float32)
    alphas = _sample_alpha(rng, m, opaque_only=opaque_only)
    out = np.empty((m, 6), dtype=np.float32)
    out[:, 0] = cx
    out[:, 1] = cy
    out[:, 2] = rx
    out[:, 3] = ry
    out[:, 4] = ang
    out[:, 5] = alphas
    return out


def mutate_candidates(base, n, W, H, mask, rng=None, scale=0.15,
                      opaque_only=True, fit_inside=False, max_aspect=0.0):
    """Muta 1 dos 6 params (alpha fixo em 255 se opaque_only)."""
    rng = rng or np.random.default_rng()
    cx, cy, rx, ry, ang, alp = [float(x) for x in base]
    if opaque_only:
        alp = 255.0
    ys, xs = np.where(mask)
    bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
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
        nrx, nry = _clamp_aspect(nrx, nry, max_aspect)
        if fit_inside:
            import math as _m
            ca, sa = abs(_m.cos(_m.radians(nang))), abs(_m.sin(_m.radians(nang)))
            lim = min(ncx - bx0, bx1 - ncx, ncy - by0, by1 - ncy)
            if lim >= 1.0:
                over = max(nrx * ca + nry * sa, nrx * sa + nry * ca) / lim
                if over > 1.0:
                    nrx, nry = nrx / over, nry / over
        out[i] = (ncx, ncy, nrx, nry, nang, nalp)
    return out
