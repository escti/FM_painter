"""Mapa de peso por borda (G3, item 4 — aproximacao estatica do UDF/LIVE).

Sobel 3x3 na luminancia do target -> magnitude normalizada pelo p99
(robusto a outliers) -> w = 1 + boost*e. Calculado 1x por run; o scoring
multiplica o erro por w e tira a cor otima como media PONDERADA (cura o
`color mean error`: lasca sobre borda pega a cor da borda, nao a media).
Sem dependencias novas (só numpy + Pillow, já usados).
"""
import numpy as np


def _erode(mask, px):
    """Erosao binaria via MinFilter (sem scipy). Retorna bool HxW."""
    if px <= 0:
        return mask
    from PIL import Image, ImageFilter
    H, W = mask.shape
    im = Image.fromarray((mask * 255).astype(np.uint8))
    size = 2 * int(px) + 1
    return np.array(im.filter(ImageFilter.MinFilter(size))) > 0


def edge_weights(target, boost=0.0, mask=None, erode_px=8):
    """target: HxWx3 uint8. Retorna HxW float32 com media ~1 quando boost=0.

    Com mask: o boost vale só no interior erodido — a borda da silhueta
    (pixels opacos colados no transparente) NÃO é amplificada, senão o
    scoring premia shapes atravessando a fronteira (= spill).
    Fora do interior o peso é 1 (neutro, nunca 0: peso 0 daria spill grátis).
    """
    H, W, _ = target.shape
    if not boost or boost <= 0:
        return np.ones((H, W), dtype=np.float32)
    lum = (0.299 * target[:, :, 0].astype(np.float32)
           + 0.587 * target[:, :, 1].astype(np.float32)
           + 0.114 * target[:, :, 2].astype(np.float32))
    gx = np.zeros_like(lum)
    gy = np.zeros_like(lum)
    gx[:, 1:-1] = lum[:, 2:] - lum[:, :-2]
    gy[1:-1, :] = lum[2:, :] - lum[:-2, :]
    mag = np.sqrt(gx * gx + gy * gy)
    p99 = float(np.percentile(mag, 99))
    if not np.isfinite(p99) or p99 <= 0:
        return np.ones((H, W), dtype=np.float32)
    e = np.clip(mag / p99, 0.0, 1.0)
    if mask is not None:
        e = e * _erode(np.asarray(mask, dtype=bool), erode_px)
    return (1.0 + float(boost) * e).astype(np.float32)
