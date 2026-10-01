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
    ap = argparse.ArgumentParser(description="ForzaPainter2 - rapido e bonito (bg_off)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("image")
    ap.add_argument("--profile", default="profiles/bg_off_fast_beautiful.ini")
    ap.add_argument("--stop-at", type=int, default=None)
    ap.add_argument("--random-samples", type=int, default=None)
    ap.add_argument("--mutated-samples", type=int, default=None)
    ap.add_argument("--post-passes", type=int, default=None,
                    help="0=sem pos, >=1 diagnostico + refines (default do perfil), N preservado")
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
                              opaque_only=opaque_only)
        assert len(shapes) == n0, "pos nao pode mudar a contagem"
        # re-render final + re-score + re-salva checkpoints como prefixos
        from src.post import render_all
        cur = render_all(shapes, W, H, mask, bg)
        current[:, :] = cur
        err = float(full_error_nb(target, current, mask, W, H))
        scores = [err] * len(shapes)
        for cp in sorted(set(prof["saveAt"])):
            if cp <= len(shapes):
                dump_json(outdir, stem, W, H, shapes[:cp], scores[:cp], suffix=f".{cp}")
        dump_json(outdir, stem, W, H, shapes, scores, suffix="")
        preview_cb("final", current)
        print(f"[post] {n0} -> {len(shapes)} shapes err={err:.5f} "
              f"passes={prof['postPasses']} (contagem preservada)")

    print(f"[ok] json em {outdir}/{stem}.json com {len(shapes)} shapes")
    print(f"[ok] importe no FH5 arrastando o .json no forza-painter.exe antigo "
          f"com template de {len(shapes)} esferas desagrupado")


if __name__ == "__main__":
    main()
