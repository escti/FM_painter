"""CLI: python tools/gen.py <imagem> --profile profiles/bg_off_fast_beautiful.ini ..."""
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.profile import load_profile
from src.image import load_target
from src.generator import generate, dump_json
from src.render import save_preview
from src.post import post_process
from src.cpu_backend import full_error_nb
from src.version import __version__


def main():
    ap = argparse.ArgumentParser(description="FM_Painter - rapido e bonito (bg_off)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("image")
    ap.add_argument("--profile", default="profiles/bg_off_fast_beautiful.ini")
    ap.add_argument("--stop-at", type=int, default=None)
    ap.add_argument("--random-samples", type=int, default=None)
    ap.add_argument("--mutated-samples", type=int, default=None)
    ap.add_argument("--post-passes", type=int, default=None,
                    help="0=sem pos, >=1 diagnostico + refines (default do perfil), N preservado")
    ap.add_argument("--spill-penalty", type=float, default=None,
                    help="w_spill G1/9a (default do perfil, 0=off)")
    ap.add_argument("--fit-inside", action="store_true",
                    help="trava fit-inside-bbox G1/9b (default off)")
    ap.add_argument("--full-canvas", action="store_true",
                    help="export full-canvas G1/9c opt-in (fix B2)")
    ap.add_argument("--preview", default="checkpoints", choices=["none", "checkpoints"],
                    help="none: sem PNG; checkpoints: so saveAt + final")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prof_path = args.profile if os.path.isabs(args.profile) else os.path.join(base_dir, args.profile)
    prof = load_profile(prof_path)
    if args.stop_at:
        prof["stopAt"] = args.stop_at
    if args.random_samples:
        prof["randomSamples"] = args.random_samples
    if args.mutated_samples:
        prof["mutatedSamples"] = args.mutated_samples
    if args.post_passes is not None:
        prof["postPasses"] = args.post_passes
    if args.spill_penalty is not None:
        prof["spillPenalty"] = args.spill_penalty
    if args.fit_inside:
        prof["fitInsideBbox"] = 1
    if args.full_canvas:
        prof["fullCanvas"] = 1

    img_path = args.image if os.path.isabs(args.image) else os.path.join(base_dir, args.image)
    if not os.path.exists(img_path) and os.path.exists(args.image):
        img_path = args.image

    target, current, mask, stats = load_target(
        img_path, max_resolution=prof["maxResolution"],
        alpha_threshold=prof["alphaThreshold"])
    print(f"[info] {img_path} -> work={stats['work_size']} "
          f"transparente={stats['pct_transparente']:.1f}% avg={stats['avg_color']}")

    stem = os.path.splitext(os.path.basename(img_path))[0]
    outdir = args.outdir or os.path.join(base_dir, "output", stem + "_v2")
    os.makedirs(outdir, exist_ok=True)

    def preview_cb(step, cur):
        if args.preview == "none":
            return
        save_preview(cur, mask, os.path.join(outdir, f"preview_{step}.png"))

    shapes, scores = generate(target, current, mask, prof, outdir, stem,
                              save_preview_cb=preview_cb)

    # export full-canvas opt-in (G1/9c, fix B2): so muda a SAIDA —
    # scoring/render seguem no espaco recortado; checkpoints do generate()
    # acima ficam recortados, os re-salvos abaixo sao os autoritativos.
    full_canvas = bool(prof.get("fullCanvas", 0))
    x0, y0, x1, y1 = stats["crop"]
    ow, oh = stats["orig_size"]
    expW, expH, expo = (ow, oh, (x0, y0)) if full_canvas else (
        x1 - x0, y1 - y0, (0, 0))
    if full_canvas:
        print(f"[export] full-canvas {ow}x{oh} offset={x0},{y0} (opt-in B2)")

    # pos-processamento configuravel (N sempre preservado p/ template)
    if prof["postPasses"] > 0:
        import numpy as np
        bg = np.array(stats["avg_color"], dtype=np.uint8)
        H, W = mask.shape
        n0 = len(shapes)
        opaque_only = bool(prof.get("opaqueOnly", 1))
        shapes = post_process(shapes, target, mask, bg,
                              passes=prof["postPasses"],
                              post_mutations=prof["postMutations"],
                              tol=float(prof["redundantTol"]),
                              opaque_only=opaque_only,
                              spill_w=float(prof.get("spillPenalty", 0.0)))
        assert len(shapes) == n0, "pos nao pode mudar a contagem"
        # re-render final + re-score + re-salva checkpoints como prefixos
        from src.post import render_all
        cur = render_all(shapes, W, H, mask, bg)
        current[:, :] = cur
        err = float(full_error_nb(target, current, mask, W, H))
        scores = [err] * len(shapes)
        for cp in sorted(set(prof["saveAt"])):
            if cp <= len(shapes):
                dump_json(outdir, stem, expW, expH, shapes[:cp], scores[:cp],
                          suffix=f".{cp}", offset=expo)
        dump_json(outdir, stem, expW, expH, shapes, scores, suffix="",
                  offset=expo)
        preview_cb("final", current)
        print(f"[post] {n0} -> {len(shapes)} shapes err={err:.5f} "
              f"passes={prof['postPasses']} (contagem preservada)")
    elif full_canvas:
        # sem pos mas com full-canvas: re-salva deslocado (N preservado)
        for cp in sorted(set(prof["saveAt"])):
            if cp <= len(shapes):
                dump_json(outdir, stem, expW, expH, shapes[:cp], scores[:cp],
                          suffix=f".{cp}", offset=expo)
        dump_json(outdir, stem, expW, expH, shapes, scores, suffix="",
                  offset=expo)

    print(f"[ok] json em {outdir}/{stem}.json com {len(shapes)} shapes")
    print(f"[ok] importe no FH5 arrastando o .json no forza-painter.exe antigo "
          f"com template de {len(shapes)} esferas desagrupado")


if __name__ == "__main__":
    main()
