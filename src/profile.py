"""Parser dos .ini do forza-painter (formato sem [section])."""
import configparser


DEFAULTS = {
    "description": "FM_Painter",
    "maxPreviewSize": 500,
    "maxResolution": 1024,
    "maxThreads": 0,
    "mutatedSamples": 200,
    "posterizeLevels": 256,
    "previewEvery": 10,
    "randomSamples": 2000,
    "saveAt": "500,1000",
    "saveEvery": 10,
    "stopAt": 1000,
    "redundantCheckEvery": 500,
    "opaqueOnly": 1,
    "alphaThreshold": 10,
    "maxShapeRadiusDiv": 4,
    "minShapeRadius": 2,
    "mutationRounds": 3,
    "postPasses": 1,
    "postMutations": 100,
    "redundantTol": 0.0002,
    "spillPenalty": 0.0,
    "fitInsideBbox": 0,
    "fullCanvas": 0,
    "maxAspect": 0.0,
    "edgeBoost": 0.0,
    "lateSmallShare": 0.0,
    "lateSmallStart": 0.5,
    "detailMaxR": 4,
    "adaptiveMut": 0,
    "refineTopK": 0,
    "lumaBands": 0,
    "paletteColors": 0,
    "backend": "cpu",
    "udfBoost": 0.0,
    "udfTau": 0.25,
    "areaNorm": 0.0,
}

INT_KEYS = {
    "maxPreviewSize", "maxResolution", "maxThreads", "mutatedSamples",
    "posterizeLevels", "previewEvery", "randomSamples", "saveEvery",
    "stopAt", "redundantCheckEvery", "opaqueOnly", "alphaThreshold",
    "maxShapeRadiusDiv", "minShapeRadius", "mutationRounds",
    "postPasses", "postMutations", "fitInsideBbox", "fullCanvas",
    "detailMaxR", "adaptiveMut", "refineTopK", "lumaBands", "paletteColors",
}

FLOAT_KEYS = {"redundantTol", "spillPenalty", "maxAspect", "edgeBoost",
              "lateSmallShare", "lateSmallStart", "udfBoost", "udfTau",
              "areaNorm"}


def load_profile(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    # arquivos originais nao tem [section]; injeta uma
    if "[DEFAULT]" not in text and "[profile]" not in text.lower():
        text = "[profile]\n" + text
    cp = configparser.ConfigParser()
    cp.read_string(text)
    sec = cp["profile"] if "profile" in cp else cp["DEFAULT"]
    out = dict(DEFAULTS)
    for k in out:
        if k in sec:
            out[k] = sec[k]
    for k in INT_KEYS:
        out[k] = int(out[k])
    for k in FLOAT_KEYS:
        out[k] = float(out[k])
    # saveAt -> lista de ints
    raw = out["saveAt"]
    if isinstance(raw, str):
        out["saveAt"] = [int(x) for x in raw.replace(";", ",").split(",") if x.strip().isdigit()]
    return out
