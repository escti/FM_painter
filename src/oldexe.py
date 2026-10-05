"""G7d — serializador EXATO do forza-painter antigo (FH5).

Reverso-engenheirado a partir dos arquivos de referencia
(`../imagens_originais/**/*.json`): reproduz o formato byte a byte, para
nao disparar "Malformed or invalid geometry file".

Formato:
  {"shapes":CRLF[  entry  ,CRLF  entry  CRLF]}
  entry = {"type":T, "data":[i,i,..],"color":[i,i,..],"score":S}
  - sem espaco depois de "data":/"color":; com espaco em 'type':N, '
  - data/color inteiros; score com 6 casas (trim); bg score 0
  - fundo = {"type":1, "data":[0,0,W-1,H-1], "color":[255,0,255,0], "score":0}
"""
import os

NL = "\r\n"
BG_COLOR = (255, 0, 255, 0)


def _num(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    fv = float(v)
    if fv == int(fv):
        return str(int(fv))
    return ("%.6f" % fv).rstrip("0").rstrip(".")


def entry_str(t, data, color, score):
    d = ",".join(_num(x) for x in data)
    c = ",".join(_num(x) for x in color)
    return '{"type":%d, "data":[%s],"color":[%s],"score":%s}' % (
        int(t), d, c, _num(score))


def serialize_entries(entries, nl=NL):
    parts = [entry_str(*e) for e in entries]
    return '{"shapes":' + nl + '[' + ("," + nl).join(parts) + nl + ']}'


def shapes_to_entries(shapes, W, H, off=(0, 0), total=None, scores=None,
                      bg="first"):
    """shapes: (cx,cy,rx,ry,ang,r,g,b,a). W,H = imagem ORIGINAL (fundo = W-1,H-1).
    total: camadas do template (entries totais; fundo conta, se houver).
    bg: 'first' (padrao), 'last' ou 'none' (testes de import do app antigo)."""
    ox, oy = off
    bg_entry = (1, [0, 0, int(W) - 1, int(H) - 1], list(BG_COLOR), 0)
    if bg == "none":
        limit = (int(total)) if total is not None else len(shapes)
    else:
        limit = (int(total) - 1) if total is not None else len(shapes)
    entries = []
    if bg == "first":
        entries.append(bg_entry)
    for i, s in enumerate(shapes[:max(0, limit)]):
        cx, cy, rx, ry, ang, r, g, b, a = s
        data = [int(round(cx + ox)), int(round(cy + oy)),
                max(1, int(round(rx))), max(1, int(round(ry))),
                int(round(ang)) % 360]
        color = [int(round(r)), int(round(g)), int(round(b)), 255]
        sc = scores[i] if (scores and i < len(scores)) else 0
        entries.append((16, data, color, sc))
    if bg == "last":
        entries.append(bg_entry)
    return entries


def write_old_exe(path, shapes, W, H, off=(0, 0), total=None, scores=None,
                  bg="first"):
    text = serialize_entries(shapes_to_entries(shapes, W, H, off, total,
                                                scores, bg))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path
