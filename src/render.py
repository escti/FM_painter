"""Preview PNG a partir do current array."""
from PIL import Image
import numpy as np


def save_preview(current, mask, path, checker=True):
    H, W, _ = current.shape
    if checker:
        # fundo quadriculado onde e transparente, para visualizar economia
        bg = np.zeros((H, W, 3), dtype=np.uint8) + 32
        s = 16
        yy, xx = np.mgrid[0:H, 0:W]
        bg[((xx // s) + (yy // s)) % 2 == 0] = 64
        out = bg.copy()
        out[mask] = current[mask]
    else:
        out = current
    Image.fromarray(out).save(path)
    return path
