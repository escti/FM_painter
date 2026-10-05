"""Normalizador KFPS->`.exe` antigo + validador --check (G1, item 8, fix B4).

Direcao KFPS->exe (finals deles vem sem `type:1` e com floats; o `.exe`
antigo exige fundo + ints, senao "Malformed or invalid geometry file").
Direcao exe->KFPS continua em `tools/strip_bg.py`.

Contratos (ver skill `forza-json-contracts`):
- exe (FH5): shapes[0] `type:1` [0,0,W,H] + `data`/`color` inteiros + alpha 255.
- kfps (FM8): sem `type:1`, contagem de desenhaveis == template (--expect N).

Nunca edita o original: normalizar grava copia nova em output/.
Uso:
  python tools/normalize_for_old_exe.py <in.json> --out <out.json> [--canvas W,H]
  python tools/normalize_for_old_exe.py <in.json> --check --dest exe|kfps [--expect N]
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_int_list(v):
    return isinstance(v, list) and all(isinstance(x, int) for x in v)


def validate(data, dest, expect=None):
    """Retorna lista de erros (vazia = ok)."""
    errs = []
    shapes = data.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        return ["shapes vazio ou ausente"]
    if dest == "exe":
        bg = shapes[0]
        if bg.get("type") != 1:
            errs.append("exe: shapes[0] deve ser type:1 de fundo")
        elif not _is_int_list(bg.get("data", [])):
            errs.append("exe: data do fundo deve ser ints")
        for i, s in enumerate(shapes[1:], 1):
            if s.get("type") != 16:
                errs.append(f"exe: shapes[{i}] type != 16")
                break
            if not _is_int_list(s.get("data", [])):
                errs.append(f"exe: shapes[{i}] data com floats")
                break
            if not _is_int_list(s.get("color", [])):
                errs.append(f"exe: shapes[{i}] color com floats")
                break
            if len(s.get("color", [])) == 4 and s["color"][3] != 255:
                errs.append(f"exe: shapes[{i}] alpha != 255")
                break
    elif dest == "kfps":
        if any(s.get("type") == 1 and not s.get("hidden") for s in shapes):
            errs.append("kfps: type:1 conta como shape visivel (usar strip_bg)")
        vis = [s for s in shapes if s.get("type") != 1 and not s.get("hidden")]
        if expect is not None and len(vis) != expect:
            errs.append(f"kfps: desenhaveis={len(vis)} != template {expect}")
    elif dest in ("exe-nobg", "exe_nobg"):
        # B7: trilha primaria entrega SEM fundo (o app antigo desenha type:1)
        for i, s in enumerate(shapes):
            if s.get("type") != 16:
                errs.append(f"exe-nobg: shapes[{i}] type != 16")
                break
            if not _is_int_list(s.get("data", [])):
                errs.append(f"exe-nobg: shapes[{i}] data com floats")
                break
            if not _is_int_list(s.get("color", [])):
                errs.append(f"exe-nobg: shapes[{i}] color com floats")
                break
            if len(s.get("color", [])) == 4 and s["color"][3] != 255:
                errs.append(f"exe-nobg: shapes[{i}] alpha != 255")
                break
        if expect is not None and len(shapes) != expect:
            errs.append(f"exe-nobg: desenhaveis={len(shapes)} != template {expect}")
    else:
        errs.append(f"destino desconhecido: {dest}")
    if expect is not None and dest == "exe":
        # B7: o .exe antigo conta o fundo (type:1) como UMA das camadas do
        # template -> total de entries deve ser == camadas (bg + shapes).
        if len(shapes) != expect:
            errs.append(f"exe: entries={len(shapes)} != template {expect} "
                        f"(fundo conta como camada)")
    return errs


def normalize_to_exe(data, canvas=None, total=None):
    """Injeta type:1 se ausente + arredonda p/ int. `total` = camadas do
    template (entries totais, fundo incluido) -> corta desenhaveis p/ total-1."""
    notes = []
    shapes = [dict(s) for s in data["shapes"]]
    vis = [s for s in shapes if s.get("type") != 1 and not s.get("hidden")]
    if total is not None and len(vis) > int(total) - 1:
        notes.append(f"desenhaveis {len(vis)} -> {int(total) - 1} "
                     f"(exe conta o fundo como camada; B7)")
        vis = vis[:int(total) - 1]
    for s in vis:
        if "data" in s:
            s["data"] = [int(round(v)) for v in s["data"]]
        if "color" in s:
            s["color"] = [int(round(v)) for v in s["color"]]
        if len(s.get("color", [])) == 4 and s["color"][3] != 255:
            notes.append("alpha != 255 coercido p/ 255 (jogo e opaco-only)")
            s["color"][3] = 255
    if canvas:
        W, H = canvas
    else:
        W = H = 0
        for s in vis:
            d = s.get("data", [0, 0, 0, 0, 0])
            W = max(W, int(d[0] + d[2]))
            H = max(H, int(d[1] + d[3]))
        notes.append(f"canvas derivado dos shapes: {W}x{H} (confira --canvas)")
    bg = {"type": 1, "data": [0, 0, int(W), int(H)],
          "color": [255, 0, 255, 0], "score": 0}
    if not shapes or shapes[0].get("type") != 1:
        notes.append("type:1 injetado")
    return {"shapes": [bg] + vis}, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dest", default="exe",
                    choices=["exe", "exe-nobg", "kfps"])
    ap.add_argument("--expect", type=int, default=None,
                    help="N do template p/ validar contagem")
    ap.add_argument("--canvas", default=None, help="W,H (ex: 1024,1024)")
    ap.add_argument("--exe-total", type=int, default=None,
                    help="camadas do template p/ o .exe antigo (fundo conta); "
                         "corta desenhaveis p/ total-1 (B7)")
    a = ap.parse_args()

    with open(a.input, encoding="utf-8") as f:
        data = json.load(f)

    if a.check:
        errs = validate(data, a.dest, a.expect)
        if errs:
            print("[check-FAIL]")
            for e in errs:
                print(f"  - {e}")
            sys.exit(1)
        print(f"[check-OK] {a.input} dest={a.dest}")
        return

    # default: normalizar p/ exe
    cv = None
    if a.canvas:
        cv = tuple(int(x) for x in a.canvas.split(","))
    out_data, notes = normalize_to_exe(data, cv, total=a.exe_total)
    errs = validate(out_data, "exe", a.exe_total)
    dst = a.out or os.path.join(
        BASE, "output", "for_old_exe",
        os.path.splitext(os.path.basename(a.input))[0] + ".exe.json")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out_data, f)
    for n_ in notes:
        print(f"[nota] {n_}")
    if errs:
        print("[AVISO] normalizado ainda com erros:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    print(f"[ok] {a.input} -> {dst} "
          f"({len(out_data['shapes']) - 1} desenhaveis + fundo)")


if __name__ == "__main__":
    main()
