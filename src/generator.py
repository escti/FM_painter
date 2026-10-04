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


class CpuScorer:
    """Adapter CPU (mesma interface do GpuScorer) sobre o backend numba."""

    def __init__(self, target, current, mask, emap, spill_w, udf_boost=0.0,
                 udf_tau=0.25, area_norm=0.0):
        self.target = target
        self.current = current
        self.mask = mask
        self.emap = emap
        self.spill_w = spill_w
        self.udf_boost = udf_boost
        self.udf_tau = udf_tau
        self.area_norm = area_norm
        self.H, self.W = mask.shape

    def score(self, cands):
        res = score_parallel(self.target, self.current, self.mask, cands,
                             spill_w=self.spill_w, edge_map=self.emap,
                             udf_boost=self.udf_boost,
                             udf_tau=self.udf_tau,
                             area_norm=self.area_norm)
        from .scoring import BatchScores
        if not len(res):
            e = np.empty(0)
            return BatchScores(e, e, e, e, e, e.astype(np.int64))
        a = np.asarray(res, dtype=np.float64)
        return BatchScores(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4],
                           a[:, 5].astype(np.int64))

    def apply(self, cx, cy, rx, ry, ang, r, g, b, a):
        apply_ellipse_alpha_nb(self.current, self.mask, self.W, self.H,
                               cx, cy, rx, ry, ang, r, g, b, a)

    def error(self):
        return float(full_error_nb(self.target, self.current, self.mask,
                                   self.W, self.H))

    def read_current(self):
        return self.current


def make_scorer(profile, target, current, mask, emap, spill_w, log=print):
    """Escolhe backend (G5): opencl/gpu/auto com fallback CPU."""
    backend = str(profile.get("backend", "cpu")).lower()
    udf_boost = float(profile.get("udfBoost", 0.0))
    udf_tau = float(profile.get("udfTau", 0.25))
    area_norm = float(profile.get("areaNorm", 0.0))
    if backend in ("opencl", "gpu", "auto"):
        try:
            from .opencl_backend import GpuScorer, available, _get_context
            if available():
                g = GpuScorer(target, current, mask, emap, spill_w,
                              udf_boost=udf_boost, udf_tau=udf_tau,
                              area_norm=area_norm)
                _, _, _, devname = _get_context()
                log(f"[gen] backend=opencl device={devname}")
                return g, True
            if backend in ("opencl", "gpu"):
                log("[gen] aviso: OpenCL indisponivel; usando CPU")
        except Exception as e:
            log(f"[gen] aviso: OpenCL falhou ({e}); usando CPU")
    return CpuScorer(target, current, mask, emap, spill_w, udf_boost=udf_boost,
                     udf_tau=udf_tau, area_norm=area_norm), False


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
    adaptive_mut = bool(profile.get("adaptiveMut", 0))
    refine_top_k = int(profile.get("refineTopK", 0))
    late_share = float(profile.get("lateSmallShare", 0.0))
    late_start = float(profile.get("lateSmallStart", 0.5))
    detail_max_r = int(profile.get("detailMaxR", 4))
    emap = edge_weights(target, float(profile.get("edgeBoost", 0.0)),
                         mask=mask)
    scorer, gpu = make_scorer(profile, target, current, mask, emap, spill_w,
                              log=log)

    def do_apply(cx, cy, rx, ry, ang, r, g, b, a):
        scorer.apply(cx, cy, rx, ry, ang, r, g, b, a)
        if gpu and current is not None:
            # espelho CPU p/ a amostragem guiada (error_tiles) continuar fresca
            apply_ellipse_alpha_nb(current, mask, W, H, cx, cy, rx, ry, ang,
                                   r, g, b, a)

    t0 = time.time()
    err = scorer.error()
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
            max_aspect=max_aspect, late_share=late_share,
            late_start=late_start, detail_max_r=detail_max_r)
        res = scorer.score(cands)
        bi = res.argmin()
        best_d, br, bg, bb, ba, cnt = res.get(bi)
        best = cands[bi].copy()

        scale, base_scale = 0.15, 0.15
        first_rounds = 1 if refine_top_k > 1 else 0
        if refine_top_k > 1:
            # G2/2 two-stage (CPU): 1a rodada distribuida no top-K em vez de
            # só no melhor; restante dos rounds no vencedor global. Orçamento:
            # random + K*mut_each + (R-1)*mut ≈ caminho original.
            order = res.argsort(refine_top_k)
            mut_each = max(50, profile["mutatedSamples"] // refine_top_k)
            for bi_k in order:
                bk = cands[int(bi_k)].copy()
                muk = mutate_candidates(
                    bk, mut_each, W, H, mask, rng=rng,
                    opaque_only=opaque_only, fit_inside=fit_inside,
                    max_aspect=max_aspect, scale=scale)
                mrk = scorer.score(muk)
                mik = mrk.argmin()
                if mrk.delta[mik] < best_d:
                    best_d, br, bg, bb, ba, cnt = mrk.get(mik)
                    best = muk[mik].copy()
        for _ in range(profile["mutationRounds"] - first_rounds):
            if adaptive_mut and rng.random() < 0.5:
                scale = float(rng.uniform(0.05, 0.30))  # Exp D: passo aleatorio
            muts = mutate_candidates(best, profile["mutatedSamples"], W, H, mask, rng=rng,
                                     opaque_only=opaque_only, fit_inside=fit_inside,
                                     max_aspect=max_aspect, scale=scale)
            mres = scorer.score(muts)
            mi = mres.argmin()
            if mres.delta[mi] < best_d:
                best_d, br, bg, bb, ba, cnt = mres.get(mi)
                best = muts[mi].copy()
                if adaptive_mut:
                    scale = base_scale  # acerto: reseta o passo
            elif adaptive_mut:
                scale = max(0.02, scale * 0.7)  # falha: encolhe (anti-minimo-local)

        if best_d < 0 and cnt > 0:
            cx, cy, rx, ry, ang, alp = [float(x) for x in best]
            do_apply(cx, cy, rx, ry, ang, br, bg, bb, ba)
            shapes.append((cx, cy, rx, ry, ang, br, bg, bb, ba))
            err = scorer.error()
            scores.append(err)
        else:
            scores.append(err)

        if step % 50 == 0 or step == 1 or step == stop_at:
            log(f"[gen] {step}/{stop_at} err={scores[-1]:.5f} t={time.time()-t0:.0f}s")

        # preview + json SOMENTE em checkpoints e no final
        if step in save_at or step == stop_at:
            if save_preview_cb:
                try:
                    save_preview_cb(step if step != stop_at else "final",
                                    scorer.read_current())
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
