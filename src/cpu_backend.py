"""Backend CPU: scoring com alpha + paralelismo real (nogil + prange).

Formato candidato: [cx, cy, rx, ry, angle_deg, alpha_0_255].
Cor RGB otima e calculada em forma fechada para o alpha dado:
  optimal = mean((target - (1-a)*current) / a), clip 0..255.
Para a=255 cai no caso opaco (media do target).
"""
import math
import numpy as np
import numba


@numba.njit(nogil=True, fastmath=True)
def _score_one(target, current, mask, W, H, cx, cy, rx, ry, angle_deg, alpha):
    if rx < 1.0:
        rx = 1.0
    if ry < 1.0:
        ry = 1.0
    if alpha < 8.0:
        alpha = 8.0
    if alpha > 255.0:
        alpha = 255.0
    a = alpha / 255.0
    inv_a = 1.0 / a
    ang = angle_deg * 0.017453292519943295
    ca = math.cos(ang)
    sa = math.sin(ang)
    ex = abs(rx * ca) + abs(ry * sa)
    ey = abs(rx * sa) + abs(ry * ca)
    x0 = int(cx - ex)
    x1 = int(cx + ex)
    y0 = int(cy - ey)
    y1 = int(cy + ey)
    if x0 < 0:
        x0 = 0
    if y0 < 0:
        y0 = 0
    if x1 >= W:
        x1 = W - 1
    if y1 >= H:
        y1 = H - 1
    if x1 < x0 or y1 < y0:
        return 0.0, 0.0, 0.0, 0.0, 0

    inv_rx2 = 1.0 / (rx * rx)
    inv_ry2 = 1.0 / (ry * ry)
    om_a = 1.0 - a

    # passada 1: acumula cor otima + erro antes
    sum_r = 0.0
    sum_g = 0.0
    sum_b = 0.0
    cnt = 0
    err_before = 0.0
    for y in range(y0, y1 + 1):
        dy = float(y) - cy
        for x in range(x0, x1 + 1):
            if not mask[y, x]:
                continue
            dx = float(x) - cx
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            if lx * lx * inv_rx2 + ly * ly * inv_ry2 > 1.0:
                continue
            cnt += 1
            tr = float(target[y, x, 0])
            tg = float(target[y, x, 1])
            tb = float(target[y, x, 2])
            cr = float(current[y, x, 0])
            cg = float(current[y, x, 1])
            cb = float(current[y, x, 2])
            # alvo desagregado do blend atual
            sum_r += (tr - om_a * cr) * inv_a
            sum_g += (tg - om_a * cg) * inv_a
            sum_b += (tb - om_a * cb) * inv_a
            dr = tr - cr
            dg = tg - cg
            db = tb - cb
            err_before += dr * dr + dg * dg + db * db

    if cnt == 0:
        return 0.0, 0.0, 0.0, 0.0, 0

    br = sum_r / cnt
    if br < 0.0:
        br = 0.0
    elif br > 255.0:
        br = 255.0
    bg = sum_g / cnt
    if bg < 0.0:
        bg = 0.0
    elif bg > 255.0:
        bg = 255.0
    bb = sum_b / cnt
    if bb < 0.0:
        bb = 0.0
    elif bb > 255.0:
        bb = 255.0

    # passada 2: erro depois com blend
    err_after = 0.0
    for y in range(y0, y1 + 1):
        dy = float(y) - cy
        for x in range(x0, x1 + 1):
            if not mask[y, x]:
                continue
            dx = float(x) - cx
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            if lx * lx * inv_rx2 + ly * ly * inv_ry2 > 1.0:
                continue
            tr = float(target[y, x, 0])
            tg = float(target[y, x, 1])
            tb = float(target[y, x, 2])
            cr = float(current[y, x, 0])
            cg = float(current[y, x, 1])
            cb = float(current[y, x, 2])
            nar = a * br + om_a * cr
            nag = a * bg + om_a * cg
            nab = a * bb + om_a * cb
            dr = tr - nar
            dg = tg - nag
            db = tb - nab
            err_after += dr * dr + dg * dg + db * db

    return err_after - err_before, br, bg, bb, cnt


# Compat: versao opaca antiga (alpha=255) para testes
@numba.njit(nogil=True, fastmath=True)
def score_candidate_nb(target, current, mask, W, H, cx, cy, rx, ry, angle_deg):
    d, r, g, b, c = _score_one(target, current, mask, W, H,
                               cx, cy, rx, ry, angle_deg, 255.0)
    return d, int(r), int(g), int(b), c


@numba.njit(nogil=True, fastmath=True)
def apply_ellipse_nb(current, mask, W, H, cx, cy, rx, ry, angle_deg, r, g, b):
    apply_ellipse_alpha_nb(current, mask, W, H, cx, cy, rx, ry, angle_deg,
                           float(r), float(g), float(b), 255.0)


@numba.njit(nogil=True, fastmath=True)
def apply_ellipse_alpha_nb(current, mask, W, H, cx, cy, rx, ry, angle_deg,
                           r, g, b, alpha):
    if rx < 1.0:
        rx = 1.0
    if ry < 1.0:
        ry = 1.0
    if alpha < 0.0:
        alpha = 0.0
    if alpha > 255.0:
        alpha = 255.0
    a = alpha / 255.0
    om_a = 1.0 - a
    ang = angle_deg * 0.017453292519943295
    ca = math.cos(ang)
    sa = math.sin(ang)
    ex = abs(rx * ca) + abs(ry * sa)
    ey = abs(rx * sa) + abs(ry * ca)
    x0 = int(cx - ex)
    x1 = int(cx + ex)
    y0 = int(cy - ey)
    y1 = int(cy + ey)
    if x0 < 0:
        x0 = 0
    if y0 < 0:
        y0 = 0
    if x1 >= W:
        x1 = W - 1
    if y1 >= H:
        y1 = H - 1
    inv_rx2 = 1.0 / (rx * rx)
    inv_ry2 = 1.0 / (ry * ry)
    for y in range(y0, y1 + 1):
        dy = float(y) - cy
        for x in range(x0, x1 + 1):
            if not mask[y, x]:
                continue
            dx = float(x) - cx
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            if lx * lx * inv_rx2 + ly * ly * inv_ry2 <= 1.0:
                cr = float(current[y, x, 0])
                cg = float(current[y, x, 1])
                cb = float(current[y, x, 2])
                current[y, x, 0] = np.uint8(a * r + om_a * cr)
                current[y, x, 1] = np.uint8(a * g + om_a * cg)
                current[y, x, 2] = np.uint8(a * b + om_a * cb)


@numba.njit(nogil=True, fastmath=True)
def full_error_nb(target, current, mask, W, H):
    tot = 0.0
    n = 0
    for y in range(H):
        for x in range(W):
            if not mask[y, x]:
                continue
            dr = float(target[y, x, 0]) - float(current[y, x, 0])
            dg = float(target[y, x, 1]) - float(current[y, x, 1])
            db = float(target[y, x, 2]) - float(current[y, x, 2])
            tot += dr * dr + dg * dg + db * db
            n += 1
    if n == 0:
        return 0.0
    return (tot / (n * 3 * 255.0 * 255.0)) ** 0.5


@numba.njit(parallel=True, nogil=True, fastmath=True)
def score_batch_parallel_nb(target, current, mask, cands,
                            out_delta, out_r, out_g, out_b, out_cnt, W, H):
    """Um dispatch paralelo: 1 iteracao por candidato (prange libera todos os cores)."""
    n = cands.shape[0]
    for i in numba.prange(n):
        d, r, g, b, c = _score_one(
            target, current, mask, W, H,
            float(cands[i, 0]), float(cands[i, 1]), float(cands[i, 2]),
            float(cands[i, 3]), float(cands[i, 4]), float(cands[i, 5]))
        out_delta[i] = d
        out_r[i] = r
        out_g[i] = g
        out_b[i] = b
        out_cnt[i] = c


def score_batch(target, current, mask, candidates):
    """Fallback serial (candidatos 5-col opacos ou 6-col com alpha)."""
    H, W = mask.shape
    out = []
    for c in candidates:
        if len(c) >= 6:
            d, r, g, b, cnt = _score_one(
                target, current, mask, W, H,
                float(c[0]), float(c[1]), float(c[2]),
                float(c[3]), float(c[4]), float(c[5]))
        else:
            d, r, g, b, cnt = _score_one(
                target, current, mask, W, H,
                float(c[0]), float(c[1]), float(c[2]),
                float(c[3]), float(c[4]), 255.0)
        out.append((d, float(r), float(g), float(b),
                    float(c[5]) if len(c) >= 6 else 255.0, cnt))
    return out


def score_parallel(target, current, mask, cands):
    """Sempre via prange (sem ThreadPool/GIL). Retorna lista de tuplas."""
    import numpy as np
    n = len(cands)
    if n == 0:
        return []
    c = np.ascontiguousarray(cands, dtype=np.float64)
    if c.shape[1] == 5:
        a = np.full((n, 1), 255.0)
        c = np.hstack([c, a])
    out_d = np.empty(n, dtype=np.float64)
    out_r = np.empty(n, dtype=np.float64)
    out_g = np.empty(n, dtype=np.float64)
    out_b = np.empty(n, dtype=np.float64)
    out_c = np.empty(n, dtype=np.int64)
    H, W = mask.shape
    score_batch_parallel_nb(target, current, mask, c, out_d, out_r, out_g,
                            out_b, out_c, W, H)
    return [(float(out_d[i]), float(out_r[i]), float(out_g[i]),
             float(out_b[i]), float(c[i, 5]), int(out_c[i])) for i in range(n)]
