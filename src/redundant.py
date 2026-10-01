"""Check de redundancia: remove shapes que quase nao mudam o erro."""
import numpy as np
from .cpu_backend import apply_ellipse_nb, full_error_nb


def render_all(shape_list, W, H, mask, bg):
    cur = np.zeros((H, W, 3), dtype=np.uint8)
    cur[:, :] = bg
    for s in shape_list:
        cx, cy, rx, ry, ang, r, g, b = s
        apply_ellipse_nb(cur, mask, W, H, float(cx), float(cy),
                         float(rx), float(ry), float(ang), int(r), int(g), int(b))
    return cur


def redundant_check(shapes, target, mask, bg, tol=0.0002, log=print):
    """Greedy reverso: tenta tirar do fim para o comeco."""
    if not shapes:
        return shapes, 0
    H, W = mask.shape
    cur = render_all(shapes, W, H, mask, bg)
    base = float(full_error_nb(target, cur, mask, W, H))
    kept = list(shapes)
    removed = 0
    # testa em blocos para nao ficar O(N^2) pesado em 1000 shapes:
    # comeca pelas ultimas (mais refinamento fino, mais redundantes)
    for idx in range(len(kept) - 1, -1, -1):
        trial = kept[:idx] + kept[idx + 1:]
        tcur = render_all(trial, W, H, mask, bg)
        e = float(full_error_nb(target, tcur, mask, W, H))
        if e - base <= tol:
            kept = trial
            base = e
            removed += 1
            if removed % 50 == 0:
                log(f"[redundant] removidos={removed} err={base:.5f}")
    log(f"[redundant] removidos={removed}/{len(shapes)} err_final={base:.5f}")
    return kept, removed
