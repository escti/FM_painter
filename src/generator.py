"""Loop principal: batch paralelo (prange) -> hill-climb -> aplica vencedor.

Preview: SOMENTE checkpoints (saveAt) + final. Sem preview_every.
"""
import os
import time
import json
import numpy as np

from .cpu_backend import score_parallel, apply_ellipse_alpha_nb, full_error_nb
from .candidates import random_candidates, mutate_candidates
from .edgeweight import edge_weights


def resolve_workers(max_threads):
    import os as _os
    n = _os.cpu_count() or 4
    if max_threads and max_threads > 0:
        n = min(n, max_threads)
    try:
        import numba
        numba.set_num_threads(n)
    except Exception:
        pass
    return n


def generate(target, current, mask, profile, out_dir, base_name,
             log=print, save_preview_cb=None):
    os.makedirs(out_dir, exist_ok=True)
    H, W = mask.shape
    n_workers = resolve_workers(profile["maxThreads"])
    rng = np.random.default_rng(9001)

    shapes = []  # (cx,cy,rx,ry,ang,r,g,b,a)
    scores = []
    stop_at = profile["stopAt"]
    save_at = set(profile["saveAt"])
    opaque_only = bool(profile.get("opaqueOnly", 1))
    spill_w = float(profile.get("spillPenalty", 0.0))
    fit_inside = bool(profile.get("fitInsideBbox", 0))
    max_aspect = float(profile.get("maxAspect", 0.0))
    emap = edge_weights(target, float(profile.get("edgeBoost", 0.0)),
                         mask=mask)

    t0 = time.time()
    err = float(full_error_nb(target, current, mask, W, H))
    log(f"[gen] work={W}x{H} opaco={mask.mean()*100:.1f}% threads={n_workers} "
        f"rand={profile['randomSamples']} mut={profile['mutatedSamples']} "
        f"rounds={profile['mutationRounds']} opaco_only={int(opaque_only)} "
        f"err0={err:.5f}")

    for step in range(1, stop_at + 1):
        progress = step / max(1, stop_at)
        cands = random_candidates(
            profile["randomSamples"], W, H, mask,
            min_r=profile["minShapeRadius"],
            max_r_div=profile["maxShapeRadiusDiv"], rng=rng,
            target=target, current=current, progress=progress,
            opaque_only=opaque_only, fit_inside=fit_inside,
            max_aspect=max_aspect)
        res = score_parallel(target, current, mask, cands, spill_w=spill_w,
                             edge_map=emap)
        bi = int(np.argmin([r[0] for r in res]))
        best_d, br, bg, bb, ba, cnt = res[bi]
        best = cands[bi].copy()

        for _ in range(profile["mutationRounds"]):
            muts = mutate_candidates(best, profile["mutatedSamples"], W, H, mask, rng=rng,
                                     opaque_only=opaque_only, fit_inside=fit_inside,
                                     max_aspect=max_aspect)
            mres = score_parallel(target, current, mask, muts, spill_w=spill_w,
                                  edge_map=emap)
            mi = int(np.argmin([r[0] for r in mres]))
            if mres[mi][0] < best_d:
                best_d, br, bg, bb, ba, cnt = mres[mi]
                best = muts[mi].copy()

        if best_d < 0 and cnt > 0:
            cx, cy, rx, ry, ang, alp = [float(x) for x in best]
            apply_ellipse_alpha_nb(current, mask, W, H, cx, cy, rx, ry, ang,
                                   br, bg, bb, ba)
            shapes.append((cx, cy, rx, ry, ang, br, bg, bb, ba))
            err = float(full_error_nb(target, current, mask, W, H))
            scores.append(err)
        else:
            scores.append(err)

        if step % 50 == 0 or step == 1 or step == stop_at:
            log(f"[gen] {step}/{stop_at} err={scores[-1]:.5f} t={time.time()-t0:.0f}s")

        # preview + json SOMENTE em checkpoints e no final
        if step in save_at or step == stop_at:
            if save_preview_cb:
                try:
                    save_preview_cb(step if step != stop_at else "final", current)
                except Exception as e:
                    log(f"[gen] preview falhou: {e}")
            dump_json(out_dir, base_name, W, H, shapes, scores,
                      suffix=f".{step}" if step != stop_at else "")

    dump_json(out_dir, base_name, W, H, shapes, scores, suffix="")
    log(f"[gen] fim {len(shapes)} shapes err={scores[-1]:.5f} em {time.time()-t0:.0f}s")
    return shapes, scores


def dump_json(out_dir, base_name, W, H, shapes, scores, suffix="",
              offset=(0, 0)):
    """offset=(x0,y0): soma no cx,cy p/ export full-canvas (G1/9c, opt-in)."""
    ox, oy = offset
    data = {"shapes": [{"type": 1, "data": [0, 0, int(W), int(H)],
                        "color": [255, 0, 255, 0], "score": 0}]}
    for i, s in enumerate(shapes):
        if len(s) == 8:  # legado opaco
            cx, cy, rx, ry, ang, r, g, b = s
            a = 255
        else:
            cx, cy, rx, ry, ang, r, g, b, a = s
        data["shapes"].append({
            "type": 16,
            "data": [int(round(cx + ox)), int(round(cy + oy)),
                     int(round(rx)), int(round(ry)), int(round(ang) % 360)],
            "color": [int(r), int(g), int(b), int(a)],
            "score": float(scores[i]) if i < len(scores) else 0.0,
        })
    path = os.path.join(out_dir, base_name + suffix + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path
