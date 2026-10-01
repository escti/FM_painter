"""Exporta variante sem shape de fundo (formato KFPS: so type:16 desenhaveis).

Uso: python tools/strip_bg.py <in.json> <out.json>
Nao altera o original. Contagem final = N desenhaveis exatos.
"""
import os
import sys
import json


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        d = json.load(f)
    shapes = d["shapes"]
    bg = [s for s in shapes if s.get("type") == 1]
    vis = [s for s in shapes if s.get("type") != 1 and not s.get("hidden")]
    # normaliza: inteiros (compat .exe antigo) — KFPS aceita float, mas int
    # e universal e evita o erro "Malformed" do parser antigo
    for s in vis:
        if "data" in s:
            s["data"] = [int(round(v)) for v in s["data"]]
        if "color" in s:
            s["color"] = [int(round(v)) for v in s["color"]]
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump({"shapes": vis}, f)
    print(f"[ok] {src}: {len(shapes)} entries "
          f"(fundo={len(bg)}) -> {dst}: {len(vis)} desenhaveis")


if __name__ == "__main__":
    main()
