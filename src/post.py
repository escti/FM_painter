"""Pos-processamento com contagem preservada (500/1000 exatos p/ template).

passes=0: nada.
passes=1: 1 refine in-place (mantem N) + prune DIAGNOSTICO (so relata).
passes>=2: prune-diagnostico + (passes-1) refines + diagnostico final.

Prune nunca remove do entregue por default (preserve_counts=True): evita o
bug anterior (1000->209, erro 0.108->0.179 por deriva cumulativa do `base=e`).
Se um dia quiser remover, use preserve_counts=False com maxDrift absoluto.
"""
import numpy as np
from .cpu_backend import (apply_ellipse_alpha_nb, full_error_nb,
                          score_parallel)
from .candidates import mutate_candidates


def _get(shape):
    if len(shape) == 8:
        cx, cy, rx, ry, ang, r, g, b = shape
        return cx, cy, rx, ry, ang, r, g, b, 255.0
    return tuple(float(x) for x in shape)


def render_all(shapes, W, H, mask, bg):
    cur = np.zeros((H, W, 3), dtype=np.uint8)
    cur[:, :] = bg
    for s in shapes:
        cx, cy, rx, ry, ang, r, g, b, a = _get(s)
        apply_ellipse_alpha_nb(cur, mask, W, H, cx, cy, rx, ry, ang, r, g, b, a)
    return cur


def prune_diagnostic(shapes, target, mask, bg, tol=0.0002, max_drift=0.005,
                     log=print):
    """Nao remove nada: estima quantos seriam redundantes com drift limitado.

    Retorna (kept_unchanged, removable_idx). Drift medido contra o erro
    ORIGINAL (nao cumulativo) — fix do bug 1000->209.
    """
    if not shapes:
        return shapes, []
    H, W = mask.shape
    cur = render_all(shapes, W, H, mask, bg)
    err0 = float(full_error_nb(target, cur, mask, W, H))
    removable = []
    for idx in range(len(shapes) - 1, -1, -1):
        trial = [s for j, s in enumerate(shapes) if j != idx
                 and j not in removable]
        tcur = render_all(trial, W, H, mask, bg)
        e = float(full_error_nb(target, tcur, mask, W, H))
        if e - err0 <= tol and (e - err0) <= max_drift:
            removable.append(idx)
    log(f"[post-prune-diag] redundantes={len(removable)}/{len(shapes)} "
        f"err0={err0:.5f} (contagem preservada)")
    return shapes, removable


def refine_pass(shapes, target, mask, bg, post_mutations=100, log=print, tag="",
                opaque_only=True, top_k=3):
    """Coordinate-descent in-place com aceite GLOBAL (N preservado).

    Fix: a versao anterior aceitava pelo delta local (canvas sem o shape),
    ignorando as camadas acima — 924 aceites degradaram 0.108->0.111.
    Agora os top_k candidatos locais sao reavaliados com render global e
    aceitos so se o erro global cair. Mais caro (1 render full por idx),
    mas nunca piora.
    """
    H, W = mask.shape
    rng = np.random.default_rng(1234)
    cur = render_all(shapes, W, H, mask, bg)
    base = float(full_error_nb(target, cur, mask, W, H))
    improved = 0
    out = list(shapes)
    for idx in range(len(out) - 1, -1, -1):
        cx, cy, rx, ry, ang, r, g, b, a = _get(out[idx])
        if opaque_only:
            a = 255.0
        base_cand = np.array([[cx, cy, rx, ry, ang, a]], dtype=np.float32)
        trial_shapes = out[:idx] + out[idx + 1:]
        without = render_all(trial_shapes, W, H, mask, bg)
        muts = mutate_candidates(base_cand[0], post_mutations, W, H, mask,
                                 rng=rng, opaque_only=opaque_only)
        res = score_parallel(target, without, mask, muts)
        order = np.argsort([x[0] for x in res])[:top_k]
        for mi in order:
            mi = int(mi)
            d, br, bgc, bb, ba, cnt = res[mi]
            if d >= 0 or cnt == 0:
                break
            m = muts[mi]
            if opaque_only:
                ba = 255.0
            cand = (float(m[0]), float(m[1]), float(m[2]), float(m[3]),
                    float(m[4]), float(br), float(bgc), float(bb), float(ba))
            trial2 = trial_shapes[:idx] + [cand] + trial_shapes[idx:]
            tcur = render_all(trial2, W, H, mask, bg)
            e = float(full_error_nb(target, tcur, mask, W, H))
            if e < base:
                out[idx] = cand
                base = e
                improved += 1
                break
    cur = render_all(out, W, H, mask, bg)
    base = float(full_error_nb(target, cur, mask, W, H))
    log(f"[post-refine{tag}] melhorados={improved}/{len(out)} err={base:.5f} "
        f"(N preservado, aceite global)")
    return out, base


def post_process(shapes, target, mask, bg, passes=1, post_mutations=100,
                 tol=0.0002, max_drift=0.005, opaque_only=True, log=print):
    """passes=0 nada; >=1 diagnostico + (passes) refines. Nunca muda N."""
    if passes <= 0 or not shapes:
        return shapes
    n0 = len(shapes)
    _, _ = prune_diagnostic(shapes, target, mask, bg, tol=tol,
                            max_drift=max_drift, log=log)
    for p in range(passes):
        shapes, _ = refine_pass(shapes, target, mask, bg,
                                post_mutations=post_mutations, log=log,
                                tag=f" p{p + 1}/{passes}",
                                opaque_only=opaque_only)
    _, _ = prune_diagnostic(shapes, target, mask, bg, tol=tol,
                            max_drift=max_drift, log=log)
    assert len(shapes) == n0, "pos nunca pode mudar a contagem"
    return shapes
