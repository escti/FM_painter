"""Compara jpg com fundo vs png sem fundo: tempo, erro, shapes."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.profile import load_profile
from src.image import load_target
from src.generator import generate


def run_one(img, prof, outdir, stem):
    target, current, mask, stats = load_target(
        img, max_resolution=prof["maxResolution"],
        alpha_threshold=prof["alphaThreshold"])
    t0 = time.time()
    shapes, scores = generate(target, current, mask, dict(prof), outdir, stem,
                              log=lambda *a: None)
    dt = time.time() - t0
    return {"img": img, "shapes": len(shapes), "err": scores[-1],
            "time": dt, "transp": stats["pct_transparente"]}


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prof = load_profile(os.path.join(base, "profiles", "bg_off_balanced.ini"))
    prof["stopAt"] = 100
    prof["randomSamples"] = 300
    prof["mutatedSamples"] = 40
    prof["mutationRounds"] = 1
    old = "D:/users/thiag/downloads/forza/imagens_originais"
    for name in ["efr_logo2.jpg", "efr_logo2_bg_off.png"]:
        r = run_one(os.path.join(old, name), prof,
                    os.path.join(base, "output", "cmp"), name.split(".")[0] + "_t")
        print(r)
